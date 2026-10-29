#!/usr/bin/env bash
# Place a clean, pinned public XNU clone where darwin-xnu-build's get_xnu() expects it and
# apply the QEMU_VIRT platform patch. build.sh then skips its own clone and runs its usual
# patches() on top. The clone is complete (not shallow) because dxb's restore_files.sh
# checks files out of older tags.
# Usage: prepare_qemu_virt_source.sh <tag> <commit> <patch> <patch sha256> <dest> <provenance out>
set -euo pipefail
tag="$1"; commit="$2"; patch="$3"; patch_sha="$4"; dest="$5"; out="$6"
[ ! -e "$dest" ] || { echo "REFUSED: $dest already exists (stale or reused source)"; exit 2; }
got=$(shasum -a 256 "$patch" | cut -d' ' -f1)
[ "$got" = "$patch_sha" ] || { echo "REFUSED: patch sha256 $got != pinned $patch_sha"; exit 3; }
git clone -q --branch "$tag" https://github.com/apple-oss-distributions/xnu.git "$dest"
head=$(git -C "$dest" rev-parse HEAD)
[ "$head" = "$commit" ] || { echo "REFUSED: $tag resolves to $head, pinned $commit"; exit 4; }
[ -z "$(git -C "$dest" status --porcelain)" ] || { echo "REFUSED: fresh clone is not clean"; exit 5; }
git -C "$dest" apply --check "$patch"
git -C "$dest" apply "$patch"
{
  echo "xnu_tag=$tag"
  echo "xnu_commit=$head"
  echo "platform_patch=$(basename "$patch")"
  echo "platform_patch_sha256=$got"
  git -C "$dest" status --porcelain | sed 's/^/changed: /'
  git -C "$dest" status --porcelain | awk '{print $2}' | while read -r f; do
    echo "patched_sha256 $f=$(shasum -a 256 "$dest/$f" | cut -d' ' -f1)"
  done
} | tee "$out"
