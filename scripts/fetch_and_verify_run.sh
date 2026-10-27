#!/usr/bin/env bash
# Download a run's artifacts and verify them independently: Sigstore attestation, report hash vs file hash.
# Usage: fetch_and_verify_run.sh <run-id> <dest-dir>
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
run="$1"; dest="$2"; R=SalatielBM22/penang-xnu-build
mkdir -p "$dest"
gh run download "$run" -R "$R" -D "$dest"
cd "$dest"/*/
ls -la
python3 - <<'EOF'
import json, hashlib, glob
r = json.load(open("build-report.json"))
k = r["kernel"]
got = hashlib.sha256(open(glob.glob("dxb/build/xnu.obj/" + k["file"])[0] if glob.glob("dxb/build/xnu.obj/" + k["file"]) else k["file"], "rb").read()).hexdigest()
print("REPORT_SHA_MATCHES_FILE:", "PASS" if got == k["sha256"] else f"FAIL {got}")
print(json.dumps({"build_seconds": r["build_seconds"], "build_minutes": round(r["build_seconds"] / 60, 1),
                  "kernel": k, "kdk": {x: r["kdk"].get(x) for x in ("kdk_name", "kdk_pkg_sha256", "kdk_dmg_sha256")},
                  "runner": {x: r["runner"].get(x) for x in ("os", "hw_model", "cpu", "ncpu", "xcode_version", "clang")}}, indent=1))
EOF
kernel=$(ls dxb/build/xnu.obj/kernel.* 2>/dev/null || ls kernel.* | head -1)
gh attestation verify "$kernel" --repo "$R" 2>&1 | tail -4
gh attestation verify build-report.json --repo "$R" 2>&1 | tail -2
