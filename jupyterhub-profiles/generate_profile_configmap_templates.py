#!/usr/bin/env python3
"""Render JupyterHub profile ConfigMap templates from source JSON payloads.

This keeps profile-list JSON as the source of truth and prevents drift between
`profile-list.*.json` files and manifest template copies.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HEADER = """apiVersion: v1
kind: ConfigMap
metadata:
  name: jupyterhub-profile-list
  namespace: ${environment.namespace}
  labels:
    app: jupyterhub
    component: hub
data:
  profile-list.json: |
"""


def render_template(source_json: Path, output_tpl: Path) -> None:
    payload = json.loads(source_json.read_text())
    pretty_json = json.dumps(payload, indent=2)
    indented_json = "\n".join(f"    {line}" for line in pretty_json.splitlines())
    output_tpl.write_text(f"{HEADER}{indented_json}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Base directory containing profile JSON and manifests/",
    )
    args = parser.parse_args()

    base_dir = args.base_dir
    render_template(
        source_json=base_dir / "profile-list.local.json",
        output_tpl=base_dir / "manifests" / "jupyterhub-profile-list-local.configmap.yaml.tpl",
    )
    render_template(
        source_json=base_dir / "profile-list.remote.json",
        output_tpl=base_dir / "manifests" / "jupyterhub-profile-list-remote.configmap.yaml.tpl",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())