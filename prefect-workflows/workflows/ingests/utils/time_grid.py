"""Fixed time grid for gridded IceChunk repos.

Every step has a slot on a regular axis that starts at the source's ``time_origin``; writes go to
their slots (region writes), so steps can be written in any order and rewritten (upsert). Slots
not yet written hold no chunks. Per-step metadata coordinates record each slot's state.

Forecast repos add fixed axes after the append axis (``reference_time``), e.g. ``member`` and
``lead_time``, set when the repo is created and never appended. Each (cycle, member, lead) step is
a slot with its own metadata, and ``value_time`` (reference + lead) is a 2-D coordinate.
"""
from typing import Literal

import icechunk as ic
import numpy as np
import pandas as pd
import xarray as xr
import zarr
from icechunk.xarray import to_icechunk
from virtualizarr.manifests import ChunkManifest, ManifestArray

from workflows.utils.repo_const import (
    APPEND_DIM_ATTR,
    AUDIT_COORDS,
    FORECAST_COORD_ATTRS,
    GRID_ATTRS,
    GRID_NAME_ATTR,
    LEAD_TIME,
    REFERENCE_TIME,
    FORECAST_STATUS_ATTRS,
    STATUS_ATTRS,
    STATUS_COORD,
    STATUS_MEANINGS,
    STEP_COORDS,
    TIME_ORIGIN_ATTR,
    TIME_STEP_ATTR,
    UNWRITTEN,
    VALUE_TIME,
)

# 1-D step coordinates are small; one chunk covers decades of daily or hourly steps
_STEP_COORD_CHUNK = 100_000
_NAT_INT = np.iinfo("int64").min

WriteMode = Literal["append", "upsert"]


def utc_now() -> np.datetime64:
    return np.datetime64(pd.Timestamp.now(tz="UTC").tz_localize(None), "ms")


def _time_units(time_step: pd.Timedelta) -> str:
    for unit, size in (("days", "1D"), ("hours", "1h"), ("minutes", "1min")):
        if time_step % pd.Timedelta(size) == pd.Timedelta(0):
            return unit
    return "seconds"


def step_metadata_encoding(time_origin: pd.Timestamp, time_step: pd.Timedelta, dim: str, fixed: dict | None = None) -> dict:
    """Encoding for the time axis and per-step coordinates; the only place it is defined.

    Explicit units and fill values, or xarray infers units from the first data (e.g. days,
    truncating milliseconds) and stores NaT without a fill. With ``fixed`` axes (name -> values),
    each chunk of per-step coordinates holds whole cycles and about as many steps as an analysis chunk.
    """
    sizes = tuple(len(values) for values in (fixed or {}).values())
    chunks = {"chunks": (max(1, _STEP_COORD_CHUNK // int(np.prod(sizes))), *sizes)}
    units = f"{_time_units(time_step)} since {time_origin.isoformat()}"
    encoding = {
        dim: {"units": units, "dtype": "int64", "chunks": (_STEP_COORD_CHUNK,)},
        STATUS_COORD: {"dtype": "int8", **chunks},
    }
    for name in AUDIT_COORDS:
        encoding[name] = {"units": "milliseconds since 1970-01-01", "dtype": "int64", "_FillValue": _NAT_INT, **chunks}
    for name in fixed or {}:
        encoding[name] = {"dtype": "int32"}
    if LEAD_TIME in (fixed or {}):
        lead_step = min(time_step, pd.Timedelta(1, FORECAST_COORD_ATTRS[LEAD_TIME]["units"]))
        encoding[VALUE_TIME] = {
            "units": f"{_time_units(lead_step)} since {time_origin.isoformat()}", "dtype": "int64",
            "chunks": (chunks["chunks"][0], len(fixed[LEAD_TIME])),
        }
    return encoding


def empty_step_metadata(times: pd.DatetimeIndex, dim: str, fixed: dict | None = None) -> dict:
    """Per-step coordinates for slots not yet written; one per step with ``fixed`` axes."""
    dims = (dim, *(fixed or {}))
    shape = (len(times), *(len(values) for values in (fixed or {}).values()))
    nat = np.full(shape, np.datetime64("NaT", "ms"), "datetime64[ms]")
    return {
        STATUS_COORD: (dims, np.full(shape, UNWRITTEN, "int8"), FORECAST_STATUS_ATTRS if fixed else STATUS_ATTRS),
        **{name: (dims, nat) for name in AUDIT_COORDS},
    }


def value_times(reference_times, lead_hours) -> np.ndarray:
    """Valid time of each (cycle, lead): reference time plus lead."""
    refs = np.asarray(reference_times, "datetime64[ns]")
    return refs[:, None] + np.asarray(lead_hours).astype("timedelta64[h]")[None, :]


def append_dim_attrs(template_attrs: dict, forecast: bool) -> dict:
    """CF attrs of the append axis: analysis time is the T axis, a forecast's reference time isn't."""
    attrs = {k: v for k, v in template_attrs.items() if k not in ("units", "calendar")}
    if forecast:
        attrs = {k: v for k, v in attrs.items() if k not in ("standard_name", "axis")}
        return {**attrs, **FORECAST_COORD_ATTRS[REFERENCE_TIME]}
    return {"standard_name": "time", "axis": "T", **attrs}


def write_grid_attrs(store: ic.IcechunkStore, attrs: dict) -> None:
    """Record the grid and teehr mapping on the repo's root group."""
    zarr.open_group(store, mode="a", zarr_format=3).attrs.update(attrs)


def read_root_attrs(store: ic.IcechunkStore) -> dict:
    try:
        return dict(zarr.open_group(store, mode="r", zarr_format=3).attrs)
    except (zarr.errors.GroupNotFoundError, FileNotFoundError):
        return {}


def read_grid(store: ic.IcechunkStore) -> tuple[str, pd.Timestamp, pd.Timedelta] | None:
    """(append_dim, time_origin, time_step) from the root group, or None for a repo without a grid."""
    attrs = read_root_attrs(store)
    if not all(name in attrs for name in GRID_ATTRS):
        return None
    return attrs[APPEND_DIM_ATTR], pd.Timestamp(attrs[TIME_ORIGIN_ATTR]), pd.Timedelta(attrs[TIME_STEP_ATTR])


def read_grid_name(store: ic.IcechunkStore) -> str | None:
    """The grid (CRS, pixel size, extent) the repo's data is on, or None for a repo without one."""
    return read_root_attrs(store).get(GRID_NAME_ATTR)


def ensure_grid_name(store: ic.IcechunkStore, grid_name: str) -> bool:
    """Record ``grid_name`` on a repo that lacks it, so existing repos gain it; True if recorded."""
    stored = read_grid_name(store)
    if stored == grid_name:
        return False
    if stored is not None:
        raise ValueError(f"The repo is on grid '{stored}', not '{grid_name}'.")
    write_grid_attrs(store, {GRID_NAME_ATTR: grid_name})
    return True


def check_on_grid(times: pd.DatetimeIndex, time_origin: pd.Timestamp, time_step: pd.Timedelta) -> None:
    """Raise if any timestamp is before the origin or between grid steps."""
    offsets = pd.DatetimeIndex(times) - time_origin
    bad = times[(offsets < pd.Timedelta(0)) | (offsets % time_step != pd.Timedelta(0))]
    if len(bad):
        raise ValueError(f"{len(bad)} timestamp(s) are off the time grid ({time_origin} + k * {time_step}): {list(bad[:5])}")


def check_fixed_axes(store: ic.IcechunkStore, group: str, fixed: dict) -> None:
    """Raise if ``group``'s fixed axes don't hold exactly the source's values (e.g. its lead times)."""
    ds = xr.open_zarr(store, group=group, consolidated=False, chunks=None)
    for name, values in fixed.items():
        stored = ds[name].values if name in ds.coords else None
        if stored is None or not np.array_equal(stored, np.asarray(values)):
            raise ValueError(f"{group} has {name} {stored}, but the source has {list(values)}.")


def read_step_metadata(store: ic.IcechunkStore, group: str, dim: str) -> pd.DataFrame | None:
    """Per-step metadata of ``group``, or None if the group doesn't exist.

    Indexed by the time axis, or for forecast groups by (time axis, *fixed axes), one row per step.
    """
    try:
        ds = xr.open_zarr(store, group=group, consolidated=False, chunks=None, decode_coords="all")
    except (zarr.errors.GroupNotFoundError, FileNotFoundError, KeyError):
        return None
    if dim not in ds.dims:
        return None
    names = [name for name in STEP_COORDS if name in ds.variables]
    step_dims = ds[STATUS_COORD].dims if STATUS_COORD in ds.variables else (dim,)
    if len(step_dims) == 1:
        return pd.DataFrame({name: ds[name].values for name in names}, index=pd.DatetimeIndex(ds[dim].values, name=dim))
    index = pd.MultiIndex.from_product([ds[d].to_index() for d in step_dims], names=step_dims)
    return pd.DataFrame({name: ds[name].values.reshape(-1) for name in names}, index=index)


def ensure_axis(session: ic.Session, group: str, end: pd.Timestamp, time_step: pd.Timedelta, dim: str) -> int:
    """Grow every ``dim`` array of ``group`` so the axis reaches ``end``; returns the number of slots added.

    New slots get their timestamps and unwritten per-step metadata; data arrays only change shape.
    Timestamps are encoded with the units already stored on the axis.
    """
    g = zarr.open_group(session.store, path=group.strip("/"), mode="a", zarr_format=3)
    times = xr.open_zarr(session.store, group=group, consolidated=False, chunks=None)[dim].to_index()
    if end <= times[-1]:
        return 0
    new = pd.date_range(times[-1] + time_step, end, freq=time_step)
    old_n = len(times)
    for name, arr in g.arrays():
        dims = arr.metadata.dimension_names or ()
        if dim in dims:
            axis = dims.index(dim)
            arr.resize(tuple(old_n + len(new) if i == axis else s for i, s in enumerate(arr.shape)))
    encoded, _, _ = xr.coding.times.encode_cf_datetime(new, g[dim].attrs["units"], g[dim].attrs.get("calendar"))
    g[dim][old_n:] = encoded
    if STATUS_COORD in g:
        g[STATUS_COORD][old_n:] = UNWRITTEN
    for name in AUDIT_COORDS:
        if name in g:
            g[name][old_n:] = _NAT_INT
    if VALUE_TIME in g:
        g[VALUE_TIME][old_n:] = _encode_value_times(g, new)
    return len(new)


def _encode_value_times(g: zarr.Group, reference_times: pd.DatetimeIndex) -> np.ndarray:
    """Stored values of ``value_time`` for these cycles, in the units already on the array."""
    vt = value_times(reference_times, g[LEAD_TIME][:])
    encoded, _, _ = xr.coding.times.encode_cf_datetime(vt, g[VALUE_TIME].attrs["units"], g[VALUE_TIME].attrs.get("calendar"))
    return encoded


def _grow_fixed_axes(session: ic.Session, group: str, fixed: dict, reference_times: pd.DatetimeIndex) -> None:
    """Resize a one-step group's fixed axes to their full values; data arrays only change shape."""
    g = zarr.open_group(session.store, path=group.strip("/"), mode="a", zarr_format=3)
    for _, arr in g.arrays():
        dims = arr.metadata.dimension_names or ()
        if any(d in fixed for d in dims):
            arr.resize(tuple(len(fixed[d]) if d in fixed else s for d, s in zip(dims, arr.shape)))
    for name, values in fixed.items():
        g[name][:] = np.asarray(values)
    g[STATUS_COORD][...] = UNWRITTEN
    for name in AUDIT_COORDS:
        g[name][...] = _NAT_INT
    if VALUE_TIME in g:
        g[VALUE_TIME][...] = _encode_value_times(g, reference_times)


def _empty_virtual(var: xr.Variable) -> xr.Variable:
    """The same virtual variable with no chunk references, for a template that stores nothing."""
    ma = var.data
    empty = ManifestArray(metadata=ma.metadata, chunkmanifest=ChunkManifest(entries={}, shape=ma.manifest.shape_chunk_grid))
    return var.copy(data=empty)


def create_group(
    session: ic.Session,
    group: str,
    template: xr.Dataset,
    time_origin: pd.Timestamp,
    time_step: pd.Timedelta,
    dim: str,
    end: pd.Timestamp,
    encoding: dict | None = None,
    virtual: bool = False,
    fixed: dict | None = None,
) -> None:
    """Create ``group`` with its axis from ``time_origin`` to ``end``, storing no data.

    ``template`` supplies variables, attrs and (for materialized groups) dtypes; one step of it is
    written at the origin with every value missing, so xarray or VirtualiZarr set up the arrays,
    then the axis is grown to ``end``. ``fixed`` (name -> values, e.g. ``{"lead_time": [1, 2]}``)
    adds forecast axes after ``dim``: one step is written, then they're resized to their full values.
    """
    fixed = fixed or {}
    first = {name: np.asarray(values)[:1] for name, values in fixed.items()}
    step_meta = empty_step_metadata(pd.DatetimeIndex([time_origin]), dim, first)
    # cf_xarray (e.g. xpublish-edr) finds the time axis by these; later writes in mode "a" don't add attrs
    time_attrs = append_dim_attrs(template[dim].attrs, forecast=bool(fixed))
    coords = {dim: (dim, [time_origin], time_attrs), **step_meta}
    coords.update({name: (name, values, FORECAST_COORD_ATTRS.get(name, {})) for name, values in first.items()})
    if LEAD_TIME in fixed:
        coords[VALUE_TIME] = ((dim, LEAD_TIME), value_times([time_origin], first[LEAD_TIME]), FORECAST_COORD_ATTRS[VALUE_TIME])
    # The axis and step coords go first, with their explicit encoding; later writes keep a stored encoding
    xr.Dataset(coords=coords).to_zarr(
        session.store, group=group, mode="w", zarr_format=3, consolidated=False,
        encoding=step_metadata_encoding(time_origin, time_step, dim, fixed),
    )
    drop = [n for n in (*STEP_COORDS, VALUE_TIME) if n in template.variables]
    one = template.isel({dim: [0], **{name: [0] for name in fixed}}).drop_vars(drop)
    one = one.assign_coords({dim: [time_origin], **{k: v for k, v in coords.items() if k != dim}})
    if virtual:
        for name, var in list(one.variables.items()):
            if isinstance(var.data, ManifestArray):
                one[name] = _empty_virtual(var)
        one.vz.to_icechunk(session.store, group=group, mode="a")
    else:
        for name in one.data_vars:
            fill = np.nan if np.issubdtype(one[name].dtype, np.floating) else (encoding or {}).get(name, {}).get("_FillValue", 0)
            one[name] = one[name].copy(data=np.full(one[name].shape, fill, one[name].dtype))
        to_icechunk(one, session, group=group, mode="a", encoding=encoding)
    if fixed:
        _grow_fixed_axes(session, group, fixed, pd.DatetimeIndex([time_origin]))
    ensure_axis(session, group, end, time_step, dim)


def block_steps(ds: xr.Dataset, dim: str, fixed_dims: tuple[str, ...] = ()) -> pd.Index:
    """The steps of ``ds``: its times, or with ``fixed_dims`` its (``dim``, *``fixed_dims``) steps in C order."""
    if not fixed_dims:
        return pd.DatetimeIndex(ds[dim].values, name=dim)
    step_dims = (dim, *fixed_dims)
    return pd.MultiIndex.from_product([ds[d].to_index() for d in step_dims], names=step_dims)


def step_blocks(steps: pd.MultiIndex, fixed: dict) -> list[pd.MultiIndex]:
    """Group forecast steps into rectangular blocks for region writes.

    A block is the cycles that share one member (if any) and one contiguous run of leads on the
    repo's lead axis, so complete cycles fall into one block whatever their number.
    """
    dim, *fixed_dims = steps.names
    lead_dim = fixed_dims[-1]
    member_dims = fixed_dims[:-1]
    lead_pos = {lead: i for i, lead in enumerate(fixed[lead_dim])}
    runs: dict[tuple, list] = {}
    for key, group in pd.Series(0, index=steps).groupby(level=[dim, *member_dims] if member_dims else dim):
        cycle, members = (key[0], tuple(key[1:])) if member_dims else (key, ())
        leads = sorted(group.index.get_level_values(lead_dim), key=lead_pos.__getitem__)
        pos = [lead_pos[lead] for lead in leads]
        for run in np.split(np.arange(len(leads)), np.flatnonzero(np.diff(pos) != 1) + 1):
            runs.setdefault((members, tuple(leads[i] for i in run)), []).append(cycle)
    return [
        pd.MultiIndex.from_product([cycles, *([m] for m in members), list(leads)], names=steps.names)
        for (members, leads), cycles in runs.items()
    ]


def with_step_metadata(
    ds: xr.Dataset,
    dim: str,
    status: np.ndarray,
    source_last_modified: np.ndarray,
    updated_at: np.ndarray | np.datetime64,
    existing: pd.DataFrame | None,
    fixed_dims: tuple[str, ...] = (),
) -> xr.Dataset:
    """Attach per-step metadata to ``ds`` for a region write; ``created_at`` is kept where already set.

    With ``fixed_dims``, ``ds`` is a block of steps and the arrays hold one value per step, in the
    block's (``dim``, *``fixed_dims``) order. A forecast block also gets its ``value_time``: a virtual
    region write records the group's coordinates from the block, so a block without it would turn
    ``value_time`` into a data variable.
    """
    step_dims = (dim, *fixed_dims)
    shape = tuple(ds.sizes[d] for d in step_dims)
    steps = block_steps(ds, dim, fixed_dims)
    created = np.full(len(steps), np.datetime64("NaT", "ms"), "datetime64[ms]")
    if existing is not None:
        created = existing["created_at"].reindex(steps).to_numpy("datetime64[ms]")
    now = utc_now()
    created = np.where(np.isnat(created), now, created).astype("datetime64[ms]")
    coords = {
        STATUS_COORD: (step_dims, np.asarray(status, "int8").reshape(shape), FORECAST_STATUS_ATTRS if fixed_dims else STATUS_ATTRS),
        "created_at": (step_dims, created.reshape(shape)),
        "updated_at": (step_dims, np.broadcast_to(np.asarray(updated_at, "datetime64[ms]"), len(steps)).reshape(shape).copy()),
        "source_last_modified": (step_dims, np.asarray(source_last_modified, "datetime64[ms]").reshape(shape)),
    }
    if LEAD_TIME in fixed_dims:
        coords[VALUE_TIME] = (
            (dim, LEAD_TIME), value_times(ds[dim].values, ds[LEAD_TIME].values), FORECAST_COORD_ATTRS[VALUE_TIME]
        )
    return ds.assign_coords(coords)


def region_write(
    session: ic.Session, group: str, ds: xr.Dataset, dim: str, virtual: bool = False, fixed_dims: tuple[str, ...] = ()
) -> None:
    """Write ``ds`` into the slots of its timestamps, one contiguous run of slots per write.

    With ``fixed_dims``, ``ds`` is a block of steps: its values along each fixed axis must be a
    contiguous run of the stored ones (e.g. leads 3-6 of a cycle).
    """
    stored = xr.open_zarr(session.store, group=group, consolidated=False, chunks=None)
    region = {}
    for name in fixed_dims:
        pos = stored[name].to_index().get_indexer(ds[name].values)
        if (pos < 0).any() or (np.diff(pos) != 1).any():
            raise ValueError(f"{name} {list(ds[name].values)} isn't a contiguous run of {group}'s {list(stored[name].values)}.")
        region[name] = slice(int(pos[0]), int(pos[-1]) + 1)
    times = pd.DatetimeIndex(ds[dim].values)
    pos = stored[dim].to_index().get_indexer(times)
    if (pos < 0).any():
        raise ValueError(f"{(pos < 0).sum()} step(s) are not on {group}'s time axis, e.g. {times[pos < 0][0]}.")
    order = np.argsort(pos)
    ds, pos = ds.isel({dim: order}), pos[order]
    # Region writes take only variables along dim; the rest were written when the group was created
    ds = ds.drop_vars([n for n, v in ds.variables.items() if dim not in v.dims])
    for run in np.split(np.arange(len(pos)), np.flatnonzero(np.diff(pos) != 1) + 1):
        part = ds.isel({dim: run})
        if virtual:
            part.vz.to_icechunk(session.store, group=group, region={dim: "auto", **region})
        else:
            to_icechunk(part, session, group=group, region={dim: "auto", **region})


def select_source_steps(listing: pd.DataFrame, stored: pd.DataFrame | None, mode: WriteMode) -> pd.DataFrame:
    """Rows of ``listing`` (indexed like ``stored``: by time, or by forecast step; ``status``, ``last_modified``) to write.

    ``append`` takes steps not yet written. ``upsert`` also takes steps whose source status is more
    final, or whose source file is newer, than what's stored.
    """
    if stored is None:
        return listing
    st = stored.reindex(listing.index)
    # A not-expected step that the source does publish is written like an unwritten one
    unwritten = st[STATUS_COORD].isna() | (st[STATUS_COORD] < 0)
    if mode == "append":
        return listing[unwritten.to_numpy()]
    rank = listing[STATUS_COORD].map(STATUS_MEANINGS.index)
    more_final = rank.to_numpy() > st[STATUS_COORD].fillna(UNWRITTEN).to_numpy()
    newer = (listing["last_modified"] > st["source_last_modified"]).fillna(False).to_numpy()
    return listing[unwritten.to_numpy() | more_final | newer]


def stale_steps(source: pd.DataFrame, dest: pd.DataFrame | None) -> pd.Index:
    """Steps written in ``source`` that ``dest`` lacks or holds from an older ``source`` write."""
    written = source[source[STATUS_COORD] >= 0]
    if dest is None:
        return written.index
    dest_updated = dest["updated_at"].reindex(written.index)
    return written.index[(dest_updated != written["updated_at"]).to_numpy() | dest_updated.isna().to_numpy()]


def shard_batches(times: pd.DatetimeIndex, axis: pd.DatetimeIndex, shard_steps: int) -> list[pd.DatetimeIndex]:
    """Group ``times`` by the shard holding their slot, so each batch writes whole shards once."""
    shard = axis.get_indexer(times) // shard_steps
    return [times[shard == s] for s in np.unique(shard)]


def step_batches(steps: pd.MultiIndex, fixed: dict, shard_leads: int, max_steps: int) -> list[pd.MultiIndex]:
    """Group forecast steps by the shard holding them, and whole shards into batches.

    A shard is one cycle and member and a block of ``shard_leads`` leads on the repo's lead axis.
    Batches hold up to ``max_steps`` steps (at least one shard), so memory is bounded by the batch
    whatever the cycle's length, and each batch writes its shards once.
    """
    dim, *fixed_dims = steps.names
    lead_dim = fixed_dims[-1]
    lead_pos = pd.Index(fixed[lead_dim]).get_indexer(steps.get_level_values(lead_dim))
    shards = pd.MultiIndex.from_arrays([*(steps.get_level_values(d) for d in (dim, *fixed_dims[:-1])), lead_pos // shard_leads])
    batches, current = [], []
    for _, positions in pd.Series(np.arange(len(steps)), index=shards).groupby(level=list(range(shards.nlevels))):
        if current and sum(map(len, current)) + len(positions) > max_steps:
            batches.append(steps[np.concatenate(current)])
            current = []
        current.append(positions.to_numpy())
    if current:
        batches.append(steps[np.concatenate(current)])
    return batches


def block_selection(block: pd.Index, dim: str) -> dict:
    """``.sel`` arguments for a block of steps (one value list per dim)."""
    if isinstance(block, pd.MultiIndex):
        return {name: block.get_level_values(name).unique() for name in block.names}
    return {dim: block}
