"""How gridded source variables map to teehr's variables and units.

Our Icechunk repos and outside grids keep each source's own variable names, units and values. Each source declares
a ``TeehrMapping`` per variable (gridded sources in ``teehr_mappings()``; the outside-grid flows in their own
modules). Ingest stamps a repo's mappings as ``teehr:*`` attributes, which the dashboard and mean areal values read.
"""
from dataclasses import dataclass, field
from typing import Optional

import icechunk as ic
import zarr
from prefect import get_run_logger
from teehr import Unit, Variable
from teehr_icechunk.grid_spec import window_hours


@dataclass(frozen=True)
class TeehrMapping:
    """A source variable's teehr variable and unit, and the conversion into that unit: ``value * scale + offset``.

    ``source_units`` is the units the mapping is for; a variable stored in others is refused rather than misnamed.
    ``variables_by_interval`` names a forecast variable by the hours each value covers, which can change with lead
    time (e.g. GEFS: 3-hourly to 240 h, then 6-hourly; or 3 h and 6 h windows, see ``lead_variable_names``).
    """

    unit: Unit
    variable: Optional[Variable] = None
    variables_by_interval: dict[int, Variable] = field(default_factory=dict)
    scale: float = 1.0
    offset: float = 0.0
    source_units: Optional[str] = None

    @property
    def variables(self) -> list[Variable]:
        return [self.variable] if self.variable is not None else list(self.variables_by_interval.values())

    def check_units(self, name: str, units: Optional[str]) -> None:
        """Fail if ``name`` is stored in other units than the mapping is for."""
        if self.source_units is not None and units != self.source_units:
            raise ValueError(
                f"'{name}' is stored in '{units}', but its teehr mapping is for '{self.source_units}'."
            )


# teehr variables and units the sources share
MM = Unit(name="mm", long_name="Millimeters")
MM_PER_S = Unit(name="mm/s", long_name="Millimeters per Second")
# teehr's name for Celsius (its NWM fetch converts Kelvin to "C")
CELSIUS = Unit(name="C", long_name="Degrees Celsius")
RAINRATE_HOURLY_MEAN = Variable(name="rainrate_hourly_mean", long_name="Hourly Mean Rainfall Rate")
SWE_DAILY_INST = Variable(name="swe_daily_inst", long_name="Snow Water Equivalent")
DEPTH_DAILY_INST = Variable(name="depth_daily_inst", long_name="Snow Depth")

TEEHR_ATTR_PREFIX = "teehr:"


def teehr_attrs(mapping: Optional[TeehrMapping]) -> dict:
    """``teehr:*`` attributes naming a stored variable the teehr way, for readers such as the dashboard.

    Values stay as the source stores them; ``teehr:scale``/``teehr:offset`` convert them to ``teehr:unit_name``.
    A variable named per interval gets ``teehr:variables_by_interval`` ({hours: {name, long_name}}) instead of
    ``teehr:variable_name``.
    """
    if mapping is None:
        return {}
    if mapping.variable is not None:
        names = {
            f"{TEEHR_ATTR_PREFIX}variable_name": mapping.variable.name,
            f"{TEEHR_ATTR_PREFIX}variable_long_name": mapping.variable.long_name,
        }
    else:
        names = {f"{TEEHR_ATTR_PREFIX}variables_by_interval": {
            str(hours): {"name": v.name, "long_name": v.long_name} for hours, v in mapping.variables_by_interval.items()
        }}
    return {
        **names,
        f"{TEEHR_ATTR_PREFIX}unit_name": mapping.unit.name,
        f"{TEEHR_ATTR_PREFIX}unit_long_name": mapping.unit.long_name,
        f"{TEEHR_ATTR_PREFIX}scale": mapping.scale,
        f"{TEEHR_ATTR_PREFIX}offset": mapping.offset,
    }


def mapping_from_attrs(attrs: dict) -> Optional[TeehrMapping]:
    """The mapping a variable's ``teehr:*`` attributes record; None without them."""
    name = attrs.get(f"{TEEHR_ATTR_PREFIX}variable_name")
    by_interval = attrs.get(f"{TEEHR_ATTR_PREFIX}variables_by_interval")
    if name is None and by_interval is None:
        return None
    unit_name = attrs[f"{TEEHR_ATTR_PREFIX}unit_name"]
    return TeehrMapping(
        unit=Unit(name=unit_name, long_name=attrs.get(f"{TEEHR_ATTR_PREFIX}unit_long_name", unit_name)),
        variable=None if name is None else Variable(
            name=name, long_name=attrs.get(f"{TEEHR_ATTR_PREFIX}variable_long_name", name)
        ),
        variables_by_interval={
            int(hours): Variable(name=v["name"], long_name=v["long_name"]) for hours, v in (by_interval or {}).items()
        },
        scale=float(attrs.get(f"{TEEHR_ATTR_PREFIX}scale", 1.0)),
        offset=float(attrs.get(f"{TEEHR_ATTR_PREFIX}offset", 0.0)),
    )


def resolve_teehr_mapping(args, mapping: Optional[TeehrMapping], grid_attrs: dict) -> TeehrMapping:
    """The teehr variable to write ``args.grid_variable_name`` as: from the args when they name it, else ``mapping``.

    ``variable_name`` with ``unit_name`` (and ``value_scale``/``value_offset``) override the mapping. They're judged
    by value, not by which fields were passed, since Prefect's run form sends every field, defaults included.
    """
    if args.variable_name is not None:
        if args.unit_name is None:
            raise ValueError("Set unit_name (and value_scale) with variable_name.")
        return TeehrMapping(
            unit=Unit(name=args.unit_name, long_name=args.unit_name),
            variable=Variable(name=args.variable_name, long_name=grid_attrs.get("long_name", args.variable_name)),
            scale=args.value_scale,
            offset=args.value_offset,
        )
    if args.unit_name is not None or args.value_scale != 1.0 or args.value_offset != 0.0:
        raise ValueError("Set variable_name with unit_name, value_scale or value_offset.")
    if mapping is None:
        raise ValueError(
            f"'{args.grid_variable_name}' has no teehr mapping; set variable_name, unit_name and value_scale."
        )
    mapping.check_units(args.grid_variable_name, grid_attrs.get("units"))
    return mapping


def lead_variable_names(leads, mapping: TeehrMapping, attrs: dict) -> dict:
    """Each lead's teehr variable name, by the hours its value covers (``window_hours`` of the variable's ``attrs``).

    A windowed variable (e.g. GEFS reforecast APCP) covers the hours since its window started; others the hours
    since the lead before it. A lead covering none (lead 0) has no name and is skipped. Hours with no name raise.
    """
    names = {}
    for lead, hours in window_hours(leads, attrs).items():
        if hours not in mapping.variables_by_interval:
            known = sorted(mapping.variables_by_interval)
            raise ValueError(f"No teehr variable for {hours}-hour values (lead {lead}); known: {known}.")
        names[lead] = mapping.variables_by_interval[hours].name
    return names


def write_teehr_attrs(store: ic.IcechunkStore, mappings: dict[str, TeehrMapping]) -> bool:
    """Set each stored variable's ``teehr:*`` attributes from its source's ``mappings``; True if any changed.

    Covers every group (``/references``, ``/data``, overviews). A variable without a mapping loses any it had; one
    stored in other units than its mapping is for raises.
    """
    changed = False
    for path, node in zarr.open_group(store, mode="a", zarr_format=3).members(max_depth=None):
        if not isinstance(node, zarr.Array):
            continue
        name = path.rsplit("/", 1)[-1]
        attrs = node.attrs.asdict()
        mapping = mappings.get(name)
        if mapping is not None:
            mapping.check_units(name, attrs.get("units"))
        wanted = {k: v for k, v in attrs.items() if not k.startswith(TEEHR_ATTR_PREFIX)}
        wanted.update(teehr_attrs(mapping))
        if wanted != attrs:
            node.attrs.put(wanted)
            changed = True
    return changed


def record_teehr_attrs(repo: ic.Repository, mappings: dict[str, TeehrMapping]) -> None:
    """Commit the variables' ``teehr:*`` attributes when they changed (metadata only)."""
    session = repo.writable_session("main")
    if write_teehr_attrs(session.store, mappings):
        session.commit("Updated the variables' teehr attributes")
        get_run_logger().info("Updated the variables' teehr attributes.")
