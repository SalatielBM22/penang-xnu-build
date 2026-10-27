#!/usr/bin/env bash
# Host-side self-test of the parts that do not need macOS: syntax, YAML, tag resolution and KDK lookup.
set -euo pipefail
cd "$(dirname "$0")/.."
for s in scripts/*.sh; do bash -n "$s"; done; echo "SHELL_SYNTAX: PASS"
python3 -m py_compile scripts/build_report.py scripts/check_pkg_signature.py; echo "PY_SYNTAX: PASS"
bash scripts/test_pkg_signature.sh
python3 - <<'EOF'
import yaml, sys
w = yaml.safe_load(open(".github/workflows/measure-xnu-baseline.yml"))
on = w.get(True, w.get("on"))
assert "workflow_dispatch" in on and w["jobs"]["build"]["runs-on"] == "macos-15"
print("WORKFLOW_YAML: PASS")
EOF
DXB_COMMIT=$(sed -nE 's/^  DXB_COMMIT: ([0-9a-f]{40})$/\1/p' .github/workflows/measure-xnu-baseline.yml)
tmp=$(mktemp -d); git init -q "$tmp"
git -C "$tmp" fetch -q --depth 1 https://github.com/blacktop/darwin-xnu-build.git "$DXB_COMMIT"; git -C "$tmp" checkout -q FETCH_HEAD
bash scripts/check_xnu_tag.sh 15.6 xnu-11417.140.69 "$tmp/build.sh"; echo "XNU_TAG_15.6: PASS"
if bash scripts/check_xnu_tag.sh 15.6 xnu-0.0.0 "$tmp/build.sh" >/dev/null 2>&1; then echo "NEGATIVE_TAG: FAIL"; exit 1; else echo "NEGATIVE_TAG: REJECTED"; fi
ver=15.6
block=$(awk -v v="'${ver}')" '{ t = $0; sub(/^[[:space:]]+/, "", t) } t == v { f = 1 } f { print } f && /;;/ { exit }' "$tmp/build.sh")
printf '%s\n' "$block" | grep -q "KDK_NAME='Kernel Debug Kit 15.6 build 24G84'" && echo "KDK_LOOKUP_15.6: PASS"
curl -fsSL https://raw.githubusercontent.com/dortania/KdkSupportPkg/gh-pages/manifest.json \
 | python3 -c 'import json,sys; n="Kernel Debug Kit 15.6 build 24G84"; e=[x for x in json.load(sys.stdin) if x["name"]==n]; assert e, "not in manifest"; print("KDK_IN_MIRROR_MANIFEST: PASS", e[0]["url"].split("/")[2])'
rm -rf "$tmp"
