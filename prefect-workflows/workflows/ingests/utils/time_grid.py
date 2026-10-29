"""Fixed time grid for gridded IceChunk repos.

Every step has a slot on a regular axis that starts at the source's ``time_origin``; writes go to
their slots (region writes), so steps can be written in any order and rewritten (upsert). Slots
not yet written hold no chunks. Per-step metadata coordinates record each slot's state.
"""
from typing import Literal

import icechunk as ic
import numpy as np
import pandas as pd
import xarray as xr
import zarr
from icechunk.xarray import to_icechunk
from virtualizarr.manifests import ChunkManifest, ManifestArray

from workflows.utils.data_status import STATUS_ATTRS, STATUS_COORD, STATUS_MEANINGS

UNWRITTEN = -1
AUDIT_COORDS = ("created_at", "updated_at", "source_last_modified")
STEP_COORDS = (STATUS_COORD, *AUDIT_COORDS)
GRID_ATTRS = ("append_dim", "time_origin", "time_step")
# Repos with the same grid_name are pixel-aligned; it keys the pixel coverage weights
GRID_NAME_ATTR = "grid_name"
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


def step_metadata_encoding(time_origin: pd.Timestamp, time_step: pd.Timedelta, dim: str) -> dict:
    """Encoding for the time axis and per-step coordinates; the only place it is defined.

    Explicit units and fill values, or xarray infers units from the first data (e.g. days,
    truncating milliseconds) and stores NaT without a fill.
    """
    chunks = {"chunks": (_STEP_COORD_CHUNK,)}
    encoding = {
        dim: {"units": f"{_time_units(time_step)} since {time_origin.isoformat()}", "dtype": "int64", **chunks},
        STATUS_COORD: {"dtype": "int8", **chunks},
    }
    for name in AUDIT_COORDS:
        encoding[name] = {"units": "milliseconds since 1970-01-01", "dtype": "int64", "_FillValue": _NAT_INT, **chunks}
    return encoding


def empty_step_metadata(times: pd.DatetimeIndex, dim: str) -> dict:
    """Per-step coordinates for slots not yet written."""
    nat = np.full(len(times), np.datetime64("NaT", "ms"), "datetime64[ms]")
    return {
        STATUS_COORD: (dim, np.full(len(times), UNWRITTEN, "int8"), STATUS_ATTRS),
        **{name: (dim, nat) for name in AUDIT_COORDS},
    }


def write_grid_attrs(store: ic.IcechunkStore, attrs: dict) -> None:
    """Record the grid and teehr mapping on the repo's root group."""
    zarr.open_group(store, mode="a", zarr_format=3).attrs.update(attrs)


def _root_attrs(store: ic.IcechunkStore) -> dict:
    try:
        return dict(zarr.open_group(store, mode="r", zarr_format=3).attrs)
    except (zarr.errors.GroupNotFoundError, FileNotFoundError):
        return {}


def read_grid(store: ic.IcechunkStore) -> tuple[str, pd.Timestamp, pd.Timedelta] | None:
    """(append_dim, time_origin, time_step) from the root group, or None for a repo without a grid."""
    attrs = _root_attrs(store)
    if not all(name in attrs for name in GRID_ATTRS):
        return None
    return attrs["append_dim"], pd.Timestamp(attrs["time_origin"]), pd.Timedelta(attrs["time_step"])


def read_grid_name(store: ic.IcechunkStore) -> str | None:
    """The grid (CRS, pixel size, extent) the repo's data is on, or None for a repo without one."""
    return _root_attrs(store).get(GRID_NAME_ATTR)


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


def read_step_metadata(store: ic.IcechunkStore, group: str, dim: str) -> pd.DataFrame | None:
    """Per-step metadata of ``group`` indexed by its time axis, or None if the group doesn't exist."""
    try:
        ds = xr.open_zarr(store, group=group, consolidated=False, chunks=None, decode_coords="all")
    except (zarr.errors.GroupNotFoundError, FileNotFoundError, KeyError):
        return None
    if dim not in ds.dims:
        return None
    return pd.DataFrame(
        {name: ds[name].values for name in STEP_COORDS if name in ds.variables},
        index=pd.DatetimeIndex(ds[dim].values, name=dim),
    )


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
    return len(new)


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
) -> None:
    """Create ``group`` with its axis from ``time_origin`` to ``end``, storing no data.

    ``template`` supplies variables, attrs and (for materialized groups) dtypes; one step of it is
    written at the origin with every value missing, so xarray or VirtualiZarr set up the arrays,
    then the axis is grown to ``end``.
    """
    step_meta = empty_step_metadata(pd.DatetimeIndex([time_origin]), dim)
    # cf_xarray (e.g. xpublish-edr) finds the time axis by these; later writes in mode "a" don't add attrs
    time_attrs = {k: v for k, v in template[dim].attrs.items() if k not in ("units", "calendar")}
    time_attrs = {"standard_name": "time", "axis": "T", **time_attrs}
    # The axis and step coords go first, with their explicit encoding; later writes keep a stored encoding
    xr.Dataset(coords={dim: (dim, [time_origin], time_attrs), **step_meta}).to_zarr(
        session.store, group=group, mode="w", zarr_format=3, consolidated=False,
        encoding=step_metadata_encoding(time_origin, time_step, dim),
    )
    one = template.isel({dim: [0]}).drop_vars([n for n in STEP_COORDS if n in template.variables])
    one = one.assign_coords({dim: [time_origin], **step_meta})
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
    ensure_axis(session, group, end, time_step, dim)


def with_step_metadata(
    ds: xr.Dataset,
    dim: str,
    status: np.ndarray,
    source_last_modified: np.ndarray,
    updated_at: np.ndarray | np.datetime64,
    existing: pd.DataFrame | None,
) -> xr.Dataset:
    """Attach per-step metadata to ``ds`` for a region write; ``created_at`` is kept where already set."""
    times = pd.DatetimeIndex(ds[dim].values)
    created = np.full(len(times), np.datetime64("NaT", "ms"), "datetime64[ms]")
    if existing is not None:
        created = existing["created_at"].reindex(times).to_numpy("datetime64[ms]")
    now = utc_now()
    created = np.where(np.isnat(created), now, created).astype("datetime64[ms]")
    return ds.assign_coords({
        STATUS_COORD: (dim, np.asarray(status, "int8"), STATUS_ATTRS),
        "created_at": (dim, created),
        "updated_at": (dim, np.broadcast_to(np.asarray(updated_at, "datetime64[ms]"), len(times)).copy()),
        "source_last_modified": (dim, np.asarray(source_last_modified, "datetime64[ms]")),
    })


def region_write(
    session: ic.Session, group: str, ds: xr.Dataset, dim: str, virtual: bool = False, data_only: bool = False
) -> None:
    """Write ``ds`` into the slots of its timestamps, one contiguous run of slots per write.

    ``data_only`` skips the axis and per-step coordinates. One chunk holds them for many steps, so
    concurrent writers of different steps write only their data, and one writer then writes the coordinates.
    """
    stored = xr.open_zarr(session.store, group=group, consolidated=False, chunks=None)[dim].to_index()
    times = pd.DatetimeIndex(ds[dim].values)
    pos = stored.get_indexer(times)
    if (pos < 0).any():
        raise ValueError(f"{(pos < 0).sum()} step(s) are not on {group}'s time axis, e.g. {times[pos < 0][0]}.")
    order = np.argsort(pos)
    ds, pos = ds.isel({dim: order}), pos[order]
    # Region writes take only variables along dim; the rest were written when the group was created
    ds = ds.drop_vars([n for n, v in ds.variables.items() if dim not in v.dims])
    for run in np.split(np.arange(len(pos)), np.flatnonzero(np.diff(pos) != 1) + 1):
        part = ds.isel({dim: run})
        if virtual:
            part.vz.to_icechunk(session.store, group=group, region={dim: "auto"})
        elif data_only:
            part = part.drop_vars([n for n in (dim, *STEP_COORDS) if n in part.variables])
            to_icechunk(part, session, group=group, region={dim: slice(pos[run[0]], pos[run[-1]] + 1)})
        else:
            to_icechunk(part, session, group=group, region={dim: "auto"})


def select_source_steps(listing: pd.DataFrame, stored: pd.DataFrame | None, mode: WriteMode) -> pd.DataFrame:
    """Rows of ``listing`` (indexed by time; ``status``, ``last_modified``) to write.

    ``append`` takes steps not yet written. ``upsert`` also takes steps whose source status is more
    final, or whose source file is newer, than what's stored.
    """
    if stored is None:
        return listing
    st = stored.reindex(listing.index)
    unwritten = st[STATUS_COORD].isna() | (st[STATUS_COORD] == UNWRITTEN)
    if mode == "append":
        return listing[unwritten.to_numpy()]
    rank = listing[STATUS_COORD].map(STATUS_MEANINGS.index)
    more_final = rank.to_numpy() > st[STATUS_COORD].fillna(UNWRITTEN).to_numpy()
    newer = (listing["last_modified"] > st["source_last_modified"]).fillna(False).to_numpy()
    return listing[unwritten.to_numpy() | more_final | newer]


def stale_steps(source: pd.DataFrame, dest: pd.DataFrame | None) -> pd.DatetimeIndex:
    """Steps written in ``source`` that ``dest`` lacks or holds from an older ``source`` write."""
    written = source[source[STATUS_COORD] != UNWRITTEN]
    if dest is None:
        return written.index
    dest_updated = dest["updated_at"].reindex(written.index)
    return written.index[(dest_updated != written["updated_at"]).to_numpy() | dest_updated.isna().to_numpy()]


def shard_batches(times: pd.DatetimeIndex, axis: pd.DatetimeIndex, shard_steps: int) -> list[pd.DatetimeIndex]:
    """Group ``times`` by the shard holding their slot, so each batch writes whole shards once."""
    shard = axis.get_indexer(times) // shard_steps
    return [times[shard == s] for s in np.unique(shard)]
