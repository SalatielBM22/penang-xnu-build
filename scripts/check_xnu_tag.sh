#!/usr/bin/env bash
# Resolve the XNU tag that Apple's distribution-macOS release.json assigns to a macOS version and
# fail unless it equals the expected tag. Also checks that the pinned build.sh uses the same URL.
# Usage: check_xnu_tag.sh <macos_version e.g. 15.6> <expected tag e.g. xnu-11417.140.69> <path to build.sh>
set -euo pipefail
ver="$1"; expected="$2"; buildsh="$3"
key="macos-$(echo "$ver" | tr -d '.')"
url="https://raw.githubusercontent.com/apple-oss-distributions/distribution-macOS/${key}/release.json"
grep -qF "$url" "$buildsh" || { echo "build.sh does not use $url for $ver"; exit 2; }
got=$(curl -fsSL --retry 3 "$url" | python3 -c 'import json,sys; print(next(p["tag"] for p in json.load(sys.stdin)["projects"] if p["project"]=="xnu"))')
echo "release.json ${key}: xnu tag = ${got}"
[ "$got" = "$expected" ] || { echo "XNU tag mismatch: expected ${expected}, got ${got}"; exit 3; }
