"""Import paths as Prefect sets them: ``workflows.*`` from prefect-workflows, ``utils.*`` from workflows/ingests."""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for path in (_ROOT, _ROOT / "workflows" / "ingests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# A Prefect flow run against the cluster, not a pytest test
collect_ignore = ["distributed_rw_auth_test.py"]


@pytest.fixture
def batch_means():
    """One batch's mean areal values as a DataFrame, computed as a segment's worker processes compute them."""
    import pandas as pd
    from teehr_icechunk.mean_areal_kernel import mean_areal_block
    from teehr_icechunk.mean_areal_plan import MAX_SLICE_STEPS
    from teehr_icechunk.zonal import block_tasks

    def compute(batch, da, args, weights, fixed=None):
        fixed = fixed or {}
        da = da.transpose(args.append_dim, *fixed, args.y_dim, args.x_dim)
        return pd.concat([
            mean_areal_block(da.isel(t.selection), weights, args.y_dim, args.x_dim, t.step_columns,
                             max_slice_steps=MAX_SLICE_STEPS, min_coverage=args.min_valid_coverage).to_pandas()
            for t in block_tasks(batch, da, args.append_dim, fixed)
        ], ignore_index=True)
    return compute
