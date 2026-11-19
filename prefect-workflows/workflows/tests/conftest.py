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
    """One batch's mean areal values as a DataFrame, computed as the flow's Spark tasks compute them."""
    import pandas as pd
    from mean_areal_values import _block_tasks, _kernel_kwargs
    from utils.mean_areal_kernel import run_block_task

    def compute(batch, da, args, weights, fixed=None):
        fixed = fixed or {}
        da = da.transpose(args.append_dim, *fixed, args.y_dim, args.x_dim)
        kwargs = _kernel_kwargs(args, [int(weights.rows.min()), int(weights.rows.max()) + 1])
        tasks = _block_tasks(batch, da, args.append_dim, fixed)
        return pd.concat([run_block_task(t, da, weights, **kwargs).to_pandas() for t in tasks], ignore_index=True)
    return compute
