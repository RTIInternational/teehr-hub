"""How gridded source variables map to teehr's variables and units.

Our Icechunk repos and outside grids keep each source's own variable names, units and values. Each source declares
a ``TeehrMapping`` per variable (gridded sources in ``teehr_mappings()``; the outside-grid flows in their own
modules). Ingest stamps a repo's mappings as ``teehr:*`` attributes, which the dashboard and mean areal values read.
"""
from dataclasses import dataclass, field
from typing import Optional

from teehr import Unit, Variable


@dataclass(frozen=True)
class TeehrMapping:
    """A source variable's teehr variable and unit, and the conversion into that unit: ``value * scale + offset``.

    ``source_units`` is the units the mapping is for; a variable stored in others is refused rather than misnamed.
    ``variables_by_interval`` names a forecast variable whose step changes with lead time (e.g. GEFS: 3-hourly to
    240 h, then 6-hourly), by the hours each value covers.
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
RAINRATE_HOURLY_MEAN = Variable(name="rainrate_hourly_mean", long_name="Hourly Mean Rainfall Rate")
SWE_DAILY_INST = Variable(name="swe_daily_inst", long_name="Snow Water Equivalent")
DEPTH_DAILY_INST = Variable(name="depth_daily_inst", long_name="Snow Depth")

TEEHR_ATTR_PREFIX = "teehr:"


def teehr_attrs(mapping: Optional[TeehrMapping]) -> dict:
    """``teehr:*`` attributes naming a stored variable the teehr way, for readers such as the dashboard.

    Values stay as the source stores them; ``teehr:scale``/``teehr:offset`` convert them to ``teehr:unit_name``.
    Empty without a single teehr variable (e.g. GEFS, named per interval).
    """
    if mapping is None or mapping.variable is None:
        return {}
    return {
        f"{TEEHR_ATTR_PREFIX}variable_name": mapping.variable.name,
        f"{TEEHR_ATTR_PREFIX}variable_long_name": mapping.variable.long_name,
        f"{TEEHR_ATTR_PREFIX}unit_name": mapping.unit.name,
        f"{TEEHR_ATTR_PREFIX}unit_long_name": mapping.unit.long_name,
        f"{TEEHR_ATTR_PREFIX}scale": mapping.scale,
        f"{TEEHR_ATTR_PREFIX}offset": mapping.offset,
    }


def mapping_from_attrs(attrs: dict) -> Optional[TeehrMapping]:
    """The mapping a variable's ``teehr:*`` attributes record; None without them."""
    name = attrs.get(f"{TEEHR_ATTR_PREFIX}variable_name")
    if name is None:
        return None
    unit_name = attrs[f"{TEEHR_ATTR_PREFIX}unit_name"]
    return TeehrMapping(
        unit=Unit(name=unit_name, long_name=attrs.get(f"{TEEHR_ATTR_PREFIX}unit_long_name", unit_name)),
        variable=Variable(name=name, long_name=attrs.get(f"{TEEHR_ATTR_PREFIX}variable_long_name", name)),
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


def lead_variable_names(leads, mapping: TeehrMapping) -> dict:
    """Each lead's teehr variable name, by the interval since the lead before it (the first lead's, since 0).

    A lead of 0 covers no interval, so it has no name and is skipped. An interval with no name raises.
    """
    names, previous = {}, 0
    for lead in leads:
        interval = int(lead) - previous
        previous = int(lead)
        if interval == 0:
            continue
        if interval not in mapping.variables_by_interval:
            known = sorted(mapping.variables_by_interval)
            raise ValueError(f"No teehr variable for {interval}-hour steps (lead {lead}); known: {known}.")
        names[lead] = mapping.variables_by_interval[interval].name
    return names
