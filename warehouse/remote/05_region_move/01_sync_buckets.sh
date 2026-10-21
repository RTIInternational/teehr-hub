#!/usr/bin/env bash
set -euo pipefail

# Copies the us-east-2 warehouse buckets into the us-east-1 ones for the region
# move (RTIInternational/teehr-hub#462, #465). Incremental: Iceberg never
# rewrites a file in place, so a re-run copies only files written since the last
# one. Run it once ahead of cutover, then again at cutover after Prefect is
# paused on us-east-2. Nothing is deleted on either side.
#
# Don't run it after 03_copy_staged_metadata.sh: the rewritten metadata keeps
# the original file names, so this would copy the old-path originals back.
#
# The copy is server-side (S3 to S3), so local bandwidth doesn't matter.
# Iceberg metadata in the copy still points at the old bucket until
# 02_migrate_tables rewrites it and registers the tables.
#
# Usage: AWS_PROFILE=ciroh_mdenno ./01_sync_buckets.sh [--dryrun]
# Logs go to sync-<timestamp>.log next to this script.

cd "$(dirname "$0")"
LOG="sync-$(date -u +%Y%m%dT%H%M%SZ).log"

# Folders not carried over, and the staging folders that 02_rewrite_table_paths
# writes inside each table (03 copies what's needed).
#
# Exclude a folder only after checking no table lives in it: a table's folder
# is its location, which can differ from its name (an Iceberg rename doesn't
# move files). The live table teehr.nwmd_metrics_by_location_v2 is stored in
# nwmd_metrics_by_location_v2_test/, so that folder must be copied. 02's
# manifest lists every table's source_location.
EXCLUDES=(
  --exclude "teehr/nwmd_metrics_by_location_v2_wy_string/*"
  --exclude "*/_region_move/*"
)

sync_bucket() {
  local src="$1" dst="$2"
  shift 2
  echo "== s3://$src -> s3://$dst ($(date -u +%H:%M:%SZ))" | tee -a "$LOG"
  aws s3 sync "s3://$src" "s3://$dst" \
    --source-region us-east-2 --region us-east-1 \
    --only-show-errors "${EXCLUDES[@]}" ${@+"$@"} 2>&1 | tee -a "$LOG"
}

sync_bucket dev-teehr-iceberg-warehouse teehr-iceberg-warehouse-use1 ${@+"$@"}
sync_bucket dev-teehr-icechunk-warehouse teehr-icechunk-warehouse-use1 ${@+"$@"}

echo "== done ($(date -u +%H:%M:%SZ)). Object counts:" | tee -a "$LOG"
for b in dev-teehr-iceberg-warehouse teehr-iceberg-warehouse-use1 dev-teehr-icechunk-warehouse teehr-icechunk-warehouse-use1; do
  echo "$b $(aws s3 ls "s3://$b" --recursive --summarize | grep -E 'Total (Objects|Size)' | tr '\n' ' ')" | tee -a "$LOG"
done
