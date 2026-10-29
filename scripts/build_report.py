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
    # Optional, for experimental variants only; the VMAPPLE reference report is unchanged without them.
    ap.add_argument("--kind", default="REFERENCE_BUILD_UNMODIFIED_APPLE_XNU")
    ap.add_argument("--patch", help="platform patch applied to the public XNU source")
    ap.add_argument("--evidence", action="append", default=[], metavar="NAME=PATH",
                    help="evidence file recorded by sha256 (repeatable)")
    a = ap.parse_args()
    if a.kind != "REFERENCE_BUILD_UNMODIFIED_APPLE_XNU" and not a.patch:
        raise SystemExit("an experimental kind requires --patch")
    if a.patch and a.kind == "REFERENCE_BUILD_UNMODIFIED_APPLE_XNU":
        raise SystemExit("a patched source cannot be reported as unmodified")
    k = Path(a.kernel)
    if not k.is_file():
        raise SystemExit(f"kernel not found: {k}")
    data = k.read_bytes()
    m = re.search(rb"Darwin Kernel Version [ -~]+", data)
    report = {
        "schema_version": 1,
        "kind": a.kind,
        "inputs": {"xnu_tag": a.xnu_tag, "macos_version": a.macos_version, "machine_config": a.machine_config,
                   "kernel_config": a.kernel_config, "darwin_xnu_build_commit": a.dxb_commit},
        "kdk": kv(a.kdk_provenance),
        "runner": kv(a.runner_facts),
        "build_seconds": int(a.build_seconds),
        "kernel": {"file": k.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                   "darwin_version_string": m.group().decode() if m else None, "macho_header": macho_header(k)},
        "not_claimed": ["boots on any device", "equivalence with a shipped Apple kernelcache"],
    }
    if a.patch:
        p = Path(a.patch)
        report["modifications"] = {"platform_patch": p.name,
                                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        report["not_claimed"] += ["boots under QEMU", "Apple support for this machine config"]
    evidence = {}
    for item in a.evidence:
        name, _, path = item.partition("=")
        if not name or not Path(path).is_file():
            raise SystemExit(f"evidence file missing: {item}")
        evidence[name] = {"file": Path(path).name, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    if evidence:
        report["evidence"] = evidence
    Path(a.out).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
