# QEMU_VIRT platform patch (experimental)

`qemu-virt-arm64.patch` adds an experimental `QEMU_VIRT` machine config (QEMU `virt`,
Cortex-A76, native arm64 ABI, no Apple PAC) to the public XNU source
`apple-oss-distributions/xnu` tag `xnu-11417.140.69`, commit
`43a90889846e00bfb5cf1d255cdc0a701a1e05a4`. It is used only by
`.github/workflows/build-xnu-qemu-virt.yml`; the VMAPPLE reference workflow does not apply it.

- Upstream of record: `penang-xnu-integration` `tools/p0-boot-contract/qemu-virt-arm64.patch`
  (byte-identical copy; the workflow pins its SHA-256).
- Changes to Apple files remain under Apple's license (APSL 2.0, see `LEGAL.md`);
  the new header `pexpert/pexpert/arm64/QEMU_VIRT.h` is MIT.
- Not claimed: that the kernel boots under QEMU or on any device, or that Apple supports
  this machine config.
