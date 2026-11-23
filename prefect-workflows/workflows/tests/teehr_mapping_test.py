"""teehr mappings of source variables: resolving them, stamping them as attributes, and GEFS names by interval."""
import pytest

pytest.importorskip("teehr")
from teehr import Variable  # noqa: E402

from workflows.models import gridded_sources as gs  # noqa: E402
from workflows.models.mean_areal_inputs import MeanArealValuesInput  # noqa: E402
from workflows.utils.teehr_mapping import (  # noqa: E402
    MM, MM_PER_S, SWE_DAILY_INST, TeehrMapping, lead_variable_names, mapping_from_attrs, resolve_teehr_mapping,
    teehr_attrs,
)

CU_SWE = TeehrMapping(MM, SWE_DAILY_INST, scale=1000.0, source_units="m")
GEFS = TeehrMapping(MM_PER_S, source_units="kg m-2 s-1", variables_by_interval={
    3: Variable(name="r_3hr", long_name="3-Hour"), 6: Variable(name="r_6hr", long_name="6-Hour"),
})


def _args(**kwargs):
    return MeanArealValuesInput(
        configuration_name="c", temp_dir_path="/tmp", location_id_prefix="huc10", dest_bucket="b", base_prefix="p",
        grid_variable_name="SWE", **kwargs,
    )


def test_prefect_form_defaults_still_use_the_mapping():
    """Prefect's run form sends every field, defaults included, so defaults mustn't count as overrides."""
    form = _args(variable_name=None, unit_name=None, value_scale=1.0, value_offset=0.0)
    assert resolve_teehr_mapping(form, CU_SWE, {"units": "m"}) is CU_SWE


def test_explicit_names_override_the_mapping():
    args = _args(variable_name="swe", unit_name="cm", value_scale=100.0)
    mapping = resolve_teehr_mapping(args, CU_SWE, {"units": "m", "long_name": "Snow water"})
    assert (mapping.variable.name, mapping.variable.long_name, mapping.unit.name, mapping.scale) == (
        "swe", "Snow water", "cm", 100.0
    )


@pytest.mark.parametrize("kwargs, mapping, units, match", [
    ({"variable_name": "v"}, CU_SWE, "m", "unit_name"),
    ({"unit_name": "mm"}, CU_SWE, "m", "variable_name"),
    ({"value_scale": 2.0}, CU_SWE, "m", "variable_name"),
    ({}, None, "m", "no teehr mapping"),
    ({}, CU_SWE, "millimeters h20", "is for 'm'"),  # stored in other units than the mapping is for
])
def test_incomplete_unknown_or_mismatched_names_raise(kwargs, mapping, units, match):
    with pytest.raises(ValueError, match=match):
        resolve_teehr_mapping(_args(**kwargs), mapping, {"units": units})


def test_attrs_round_trip_and_skip_per_interval_names():
    attrs = teehr_attrs(CU_SWE)
    assert attrs["teehr:variable_name"] == "swe_daily_inst" and attrs["teehr:scale"] == 1000.0
    back = mapping_from_attrs({"units": "m", **attrs})
    assert (back.variable, back.unit, back.scale, back.offset) == (SWE_DAILY_INST, MM, 1000.0, 0.0)
    assert mapping_from_attrs({"units": "m"}) is None
    assert teehr_attrs(GEFS) == {} and teehr_attrs(None) == {}


def test_gefs_leads_are_named_by_the_interval_they_cover():
    """3-hourly leads to 240 h, then 6-hourly; lead 0 covers no interval and gets no name."""
    leads = [*range(0, 241, 3), *range(246, 841, 6)]
    names = lead_variable_names(leads, GEFS)
    assert 0 not in names and len(names) == len(leads) - 1
    assert {names[3], names[240]} == {"r_3hr"} and {names[246], names[840]} == {"r_6hr"}
    with pytest.raises(ValueError, match="12-hour"):
        lead_variable_names([3, 6, 18], GEFS)


# Built without validation: required settings (e.g. iSnobal's domain) don't affect mappings or packing
@pytest.mark.parametrize("source", [
    cls.model_construct() for cls in vars(gs).values()
    if isinstance(cls, type) and issubclass(cls, gs.GriddedSource) and cls is not gs.GriddedSource
], ids=lambda source: type(source).__name__)
def test_each_sources_mappings_and_packing_agree_on_units(source):
    """A source's mapping and overview packing of a variable must be for the same stored units."""
    for name, packing in source.overview_encoding().items():
        mapping = source.teehr_mappings().get(name)
        assert mapping is None or mapping.source_units == packing.units, name


def test_write_teehr_attrs_stamps_every_group_and_drops_stale_ones():
    zarr = pytest.importorskip("zarr")
    from workflows.utils.teehr_mapping import write_teehr_attrs

    store = zarr.storage.MemoryStore()
    root = zarr.open_group(store, mode="w", zarr_format=3)
    for group in ("references", "data", "overviews/2"):
        root.create_array(f"{group}/SWE", shape=(2,), dtype="float32", attributes={"units": "m"})
    # Without a mapping now, so its teehr attributes are stale
    root.create_array("data/other", shape=(2,), dtype="float32", attributes={"units": "m", "teehr:variable_name": "x"})

    assert write_teehr_attrs(store, {"SWE": CU_SWE})
    root = zarr.open_group(store, mode="r", zarr_format=3)
    for group in ("references", "data", "overviews/2"):
        attrs = root[f"{group}/SWE"].attrs
        assert (attrs["units"], attrs["teehr:variable_name"], attrs["teehr:scale"]) == ("m", "swe_daily_inst", 1000.0)
    assert dict(root["data/other"].attrs) == {"units": "m"}
    assert not write_teehr_attrs(store, {"SWE": CU_SWE})  # nothing left to change

    # A variable stored in other units than its mapping is for is refused, not misnamed
    with pytest.raises(ValueError, match="is for 'millimeters h20'"):
        write_teehr_attrs(store, {"SWE": TeehrMapping(MM, SWE_DAILY_INST, source_units="millimeters h20")})
