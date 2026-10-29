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

P0.1E selects the public NOS_ARM_ASM/NOS_ARM_PMAP sources only for QEMU_VIRT
and omits its KDK machine archive from the link. The non-SPTM pmap source family
is selected by CONFIG_PMAP_PPL; this does not enable XNU_MONITOR or claim PPL
hardware isolation. Apple monitor, AMCC/KTRR/CTRR, and GPU/storage IOMMU hardware
are absent on this platform. Compilation and native linking remain unverified
until a separately authorized macOS run. The inventory and handoff are in the
integration repository reports/P0.1E-*; no KDK objects are vendored here.
