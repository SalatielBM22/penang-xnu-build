#!/usr/bin/env python3
"""Write build-report.json for one XNU build: identity of the inputs, the toolchain and the output kernel."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path


def kv(path):
    out = {}
    p = Path(path)
    if p.is_file():
        for line in p.read_text(errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out.setdefault(k.strip(), v.strip())
    return out


def macho_header(kernel):
    try:
        return subprocess.run(["otool", "-hv", str(kernel)], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    ap = argparse.ArgumentParser()
    for a in ("kernel", "xnu-tag", "macos-version", "machine-config", "kernel-config", "dxb-commit",
              "build-seconds", "runner-facts", "kdk-provenance", "out"):
        ap.add_argument(f"--{a}", required=True)
    a = ap.parse_args()
    k = Path(a.kernel)
    if not k.is_file():
        raise SystemExit(f"kernel not found: {k}")
    data = k.read_bytes()
    m = re.search(rb"Darwin Kernel Version [ -~]+", data)
    report = {
        "schema_version": 1,
        "kind": "REFERENCE_BUILD_UNMODIFIED_APPLE_XNU",
        "inputs": {"xnu_tag": a.xnu_tag, "macos_version": a.macos_version, "machine_config": a.machine_config,
                   "kernel_config": a.kernel_config, "darwin_xnu_build_commit": a.dxb_commit},
        "kdk": kv(a.kdk_provenance),
        "runner": kv(a.runner_facts),
        "build_seconds": int(a.build_seconds),
        "kernel": {"file": k.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                   "darwin_version_string": m.group().decode() if m else None, "macho_header": macho_header(k)},
        "not_claimed": ["boots on any device", "equivalence with a shipped Apple kernelcache"],
    }
    Path(a.out).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
