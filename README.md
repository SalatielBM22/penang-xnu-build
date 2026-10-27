# penang-xnu-build

Reproducible, provenance-tracked builds of Apple's **public open-source XNU kernel**, for research on running
Darwin/XNU on Qualcomm Snapdragon hardware (pilot: Moto G53 5G, `penang`, SM4350).

This repository contains **only build automation**: workflows, scripts and, later, our own patches to the public
XNU sources. It contains no Apple binary, no iOS/iPadOS file, no IPSW content, no device firmware and no keys.

## What exists today

| Workflow | What it builds | Status |
|---|---|---|
| `measure-xnu-baseline` | Unmodified `xnu-11417.140.69` (macOS 15.6 source drop), `RELEASE ARM64 VMAPPLE`, with Xcode on a GitHub-hosted Apple-silicon runner | reference build: measures build time and validates provenance |

A reference build is **not** a kernel for any phone. It proves the toolchain, the inputs and the output hash.

## Provenance rules

- Upstream inputs are pinned: `blacktop/darwin-xnu-build` by commit, XNU by the tag that Apple's
  `distribution-macOS` `release.json` assigns to the macOS version (the job fails on any other tag).
- The Kernel Debug Kit is fetched from a third-party mirror but installed **only if** `pkgutil --check-signature`
  shows a trusted chain to Apple Root CA. Its SHA-256 and signature are recorded.
- Every run publishes `build-report.json` (inputs, runner, Xcode, KDK, kernel SHA-256, `Darwin Kernel Version`)
  and a Sigstore build-provenance attestation for the kernel and the report.
- Build classes: `OFFICIAL` = this CI; `DEV` = local developer builds (never used as evidence).

## Run

Actions → `measure-xnu-baseline` → *Run workflow* (defaults build `xnu-11417.140.69`).
Verify an artifact: `gh attestation verify <file> --repo SalatielBM22/penang-xnu-build`.

## Related

Analysis, ABI matrices and decisions live in a separate research repository. Community work this builds on:
[blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build),
[oosexgang/hackios-xnu-kernel](https://github.com/oosexgang/hackios-xnu-kernel),
[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet).

See [LEGAL.md](LEGAL.md). Not affiliated with or endorsed by Apple Inc. or Qualcomm.
