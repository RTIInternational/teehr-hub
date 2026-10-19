#!/usr/bin/env bash
set -euo pipefail

# Copies the metadata that 02_rewrite_table_paths staged in the us-east-2 bucket
# to its final paths in the us-east-1 bucket, and checks that every other file
# the rewritten metadata references (the data files) is already there from
# 01_sync_buckets.sh. Part of RTIInternational/teehr-hub#465.
#
# Usage: AWS_PROFILE=ciroh_mdenno ./03_copy_staged_metadata.sh rewrite_manifest.json
#
# Get rewrite_manifest.json from /data/region_move/<run id>/ on the us-east-2
# JupyterHub (copy it to your home folder there, then download it).

MANIFEST="${1:?usage: $0 rewrite_manifest.json}"
SRC_REGION=us-east-2
DST_REGION=us-east-1
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Reads a file list (one "source,target" per line). Spark may write it as one
# CSV or as a folder of part files, so handle both.
read_file_list() {
  local loc="$1"
  if aws s3 ls "$loc" --region "$SRC_REGION" | grep -qE " PRE |part-"; then
    aws s3 cp "${loc%/}/" "$WORK/fl" --recursive --region "$SRC_REGION" --only-show-errors
    cat "$WORK"/fl/* 2>/dev/null
    rm -rf "$WORK/fl"
  else
    aws s3 cp "$loc" - --region "$SRC_REGION"
  fi
}

failures=0
n_tables=$(jq '.tables | length' "$MANIFEST")
echo "$n_tables tables in $MANIFEST"

for i in $(seq 0 $((n_tables - 1))); do
  table=$(jq -r ".tables[$i].table" "$MANIFEST")
  staging=$(jq -r ".tables[$i].staging_location" "$MANIFEST")
  target=$(jq -r ".tables[$i].target_location" "$MANIFEST")
  file_list=$(jq -r ".tables[$i].file_list_location" "$MANIFEST")
  echo "== $table"

  read_file_list "$file_list" | sed '/^[[:space:]]*$/d' > "$WORK/list.csv"
  grep -F "$staging" "$WORK/list.csv" > "$WORK/staged.csv" || true
  grep -vF "$staging" "$WORK/list.csv" > "$WORK/data.csv" || true
  echo "   $(wc -l < "$WORK/staged.csv" | tr -d ' ') staged metadata files, $(wc -l < "$WORK/data.csv" | tr -d ' ') other files"

  # Fast path: every staged file goes to <target>/metadata/<same name>.
  if awk -F, -v t="$target/metadata/" '{n=split($1,p,"/"); if ($2 != t p[n]) bad=1} END {exit bad}' "$WORK/staged.csv"; then
    aws s3 sync "$staging" "$target/metadata/" \
      --source-region "$SRC_REGION" --region "$DST_REGION" --only-show-errors
  else
    echo "   staged files don't all map to metadata/; copying one by one"
    while IFS=, read -r src dst; do
      aws s3 cp "$src" "$dst" --source-region "$SRC_REGION" --region "$DST_REGION" --only-show-errors
    done < "$WORK/staged.csv"
  fi

  # Everything the rewritten metadata references must now exist in us-east-1.
  bucket_root=$(echo "$target" | cut -d/ -f1-3)
  aws s3 ls "$target/" --recursive --region "$DST_REGION" \
    | awk -v b="$bucket_root" '{print b "/" $4}' | sort > "$WORK/present.txt"
  cut -d, -f2 "$WORK/list.csv" | sort > "$WORK/needed.txt"
  missing=$(comm -23 "$WORK/needed.txt" "$WORK/present.txt" | wc -l | tr -d ' ')
  if [[ "$missing" -gt 0 ]]; then
    echo "   FAIL: $missing referenced files missing in us-east-1, e.g.:"
    comm -23 "$WORK/needed.txt" "$WORK/present.txt" | head -3 | sed 's/^/     /'
    failures=$((failures + 1))
  else
    echo "   ok: all referenced files present"
  fi
done

if [[ "$failures" -gt 0 ]]; then
  echo ""
  echo "$failures table(s) incomplete. Re-run 01_sync_buckets.sh, then this script."
  exit 1
fi
echo ""
echo "All tables ready to register (04_register_tables on the us-east-1 JupyterHub)."
