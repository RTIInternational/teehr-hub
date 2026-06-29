"""
Xpublish data provider plugin for icechunk repos.

Each configured repo is exposed as two dataset IDs:
  - ``<name>``           -> /pyramids group (DataTree for TilesPlugin)
  - ``<name>_raw_data``  -> /raw_data group (Dataset for CfEdrPlugin)

Datasets are loaded lazily on the first request and cached for
``cache_ttl_seconds``.  After the TTL expires the next request re-opens a
fresh icechunk readonly session so that new data written by Prefect ingest
workflows becomes visible without restarting the pod.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import icechunk as ic
import xarray as xr
from pydantic import PrivateAttr
from xpublish import Plugin, hookimpl
from xpublish_tiles.multiscale import assign_leaf_xpublish_ids

logger = logging.getLogger(__name__)


@dataclass
class RepoConfig:
    name: str
    bucket: str
    prefix: str


@dataclass
class _CacheEntry:
    datatree: xr.DataTree
    # Keep the icechunk session alive for the lifetime of this cache entry.
    # The DataTree's zarr backend holds a reference to session.store; if the
    # Python session object is GC'd before the entry expires, the underlying
    # Rust session could be dropped, causing a dangling pointer on next access.
    session: Any
    loaded_at: float = field(default_factory=time.monotonic)

    def is_fresh(self, ttl: float) -> bool:
        return (time.monotonic() - self.loaded_at) < ttl


def _ensure_repo_initialized(storage, branch: str) -> None:
    """Create an empty icechunk repo if one does not already exist.

    On first deployment the repo may not yet exist, which would cause
    ``ic.Repository.open()`` to raise ``icechunk.IcechunkError``.  This
    function guards against that by creating the repo and writing empty
    placeholder zarr groups for ``/pyramids`` and ``/raw_data`` so that
    ``xr.open_datatree`` and ``xr.open_zarr`` succeed at startup.  The
    Prefect ingest workflow will subsequently overwrite both groups with
    real data using ``mode="w"``.
    """
    if ic.Repository.exists(storage):
        logger.info("Icechunk repo already exists, skipping initialization")
        return

    logger.info("Icechunk repo not found — creating empty repo with placeholder groups")
    repo = ic.Repository.create(storage)
    session = repo.writable_session(branch)
    empty_ds = xr.Dataset()
    empty_ds.to_zarr(session.store, group="/pyramids", mode="w", zarr_format=3, consolidated=False)
    empty_ds.to_zarr(session.store, group="/raw_data", mode="w", zarr_format=3, consolidated=False)
    session.commit("Initialize empty repo placeholder")
    logger.info("Empty icechunk repo initialized on branch '%s'", branch)


class IcechunkDatasetProvider(Plugin):
    """Xpublish data provider plugin for icechunk repos.

    Implements ``get_datasets`` and ``get_datatree`` hookimpls so that
    xpublish resolves dataset IDs dynamically on each request.  Repository
    objects are cached for the lifetime of the plugin; DataTree/Dataset
    objects are cached for ``cache_ttl_seconds`` and refreshed automatically
    so new icechunk snapshots become visible without a pod restart.
    """

    name: str = "icechunk-dataset-provider"
    branch: str = "main"
    cache_ttl_seconds: float = 60.0

    _repo_configs: list = PrivateAttr()
    _storage_kwargs: dict = PrivateAttr()
    _repos: dict = PrivateAttr(default_factory=dict)
    _cache: dict = PrivateAttr(default_factory=dict)
    _lock: threading.Lock = PrivateAttr(default_factory=threading.Lock)

    def __init__(
        self,
        repo_configs: list[RepoConfig],
        storage_kwargs: dict,
        branch: str = "main",
        cache_ttl_seconds: float = 60.0,
    ):
        super().__init__(branch=branch, cache_ttl_seconds=cache_ttl_seconds)
        self._repo_configs = repo_configs
        self._storage_kwargs = storage_kwargs
        self._repos = {}
        self._cache = {}
        self._lock = threading.Lock()

    def dataset_ids(self) -> list[str]:
        """Return all dataset IDs served by this provider (pyramid + raw_data pairs)."""
        ids = []
        for cfg in self._repo_configs:
            ids.append(cfg.name)
            ids.append(f"{cfg.name}_raw_data")
        return ids

    def _cfg_for_dataset_id(self, dataset_id: str) -> tuple[RepoConfig | None, str]:
        for cfg in self._repo_configs:
            if dataset_id == cfg.name:
                return cfg, "/pyramids"
            if dataset_id == f"{cfg.name}_raw_data":
                return cfg, "/raw_data"
        return None, ""

    def _open_repo(self, cfg: RepoConfig) -> ic.Repository:
        if cfg.name not in self._repos:
            with self._lock:
                # Double-checked locking: re-test after acquiring to avoid
                # redundant opens when multiple threads race on a cold cache.
                if cfg.name not in self._repos:
                    storage = ic.s3_storage(bucket=cfg.bucket, prefix=cfg.prefix, **self._storage_kwargs)
                    _ensure_repo_initialized(storage, self.branch)
                    self._repos[cfg.name] = ic.Repository.open(storage)
        return self._repos[cfg.name]

    def _load_datatree(self, dataset_id: str, cfg: RepoConfig, zarr_group: str) -> _CacheEntry:
        repo = self._open_repo(cfg)
        session = repo.readonly_session(self.branch)
        if zarr_group == "/pyramids":
            dt = xr.open_datatree(
                session.store,
                group="/pyramids",
                engine="zarr",
                decode_coords="all",
                consolidated=False,
            )
            dt.attrs["_xpublish_id"] = dataset_id
            assign_leaf_xpublish_ids(dt)
        else:
            ds = xr.open_zarr(session.store, group="/raw_data", consolidated=False)
            dt = xr.DataTree(dataset=ds)
            dt.attrs["_xpublish_id"] = dataset_id
        return _CacheEntry(datatree=dt, session=session)

    def get_datatree_for_dataset(self, dataset_id: str) -> xr.DataTree | None:
        """Return a (possibly cached) DataTree for the given dataset_id.

        Called by the custom discovery endpoints in addition to the
        ``get_datatree`` hookimpl so that endpoints can reuse the same
        cached object without going through the pluggy hook machinery.
        """
        cfg, zarr_group = self._cfg_for_dataset_id(dataset_id)
        if cfg is None:
            return None
        entry = self._cache.get(dataset_id)
        if entry is None or not entry.is_fresh(self.cache_ttl_seconds):
            logger.info("Loading dataset '%s' from icechunk (cache miss or TTL expired)", dataset_id)
            self._cache[dataset_id] = self._load_datatree(dataset_id, cfg, zarr_group)
        return self._cache[dataset_id].datatree

    @hookimpl
    def get_datasets(self) -> list[str]:
        return self.dataset_ids()

    @hookimpl
    def get_datatree(self, dataset_id: str, group: str) -> xr.DataTree | None:
        dt = self.get_datatree_for_dataset(dataset_id)
        if dt is None:
            return None
        if not group:
            return dt
        return dt[group] if group in dt.children else None
