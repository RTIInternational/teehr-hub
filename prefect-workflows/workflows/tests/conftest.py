"""Import paths as Prefect sets them: ``workflows.*`` from prefect-workflows, ``utils.*`` from workflows/ingests."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for path in (_ROOT, _ROOT / "workflows" / "ingests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# A Prefect flow run against the cluster, not a pytest test
collect_ignore = ["distributed_rw_auth_test.py"]
