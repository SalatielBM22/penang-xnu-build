// Diagnostic-tool tests with explicit fixtures; never a pmap compiler test.
import test from 'node:test';
import assert from 'node:assert/strict';
const api = await import('./c04_capture_pmap.mjs').catch(() => null);
const root = '/Users/runner/work/penang-xnu-build/penang-xnu-build/dxb';
const compiler = '/Applications/Xcode_16.4.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang';
const source = root + '/xnu/osfmk/arm/pmap/pmap.c';
function entry() {
  return { directory: root + '/build/xnu.obj/RELEASE_ARM64_QEMU_VIRT/osfmk/RELEASE', file: source,
    arguments: [compiler, '-xc', source, '-c', '-DARM64_BOARD_CONFIG_QEMU_VIRT', '-mcpu=cortex-a76',
      '-arch', 'arm64', '-DCONFIG_PMAP_PPL', '-DXNU_KERNEL_PRIVATE', '-include', 'meta_features.h',
      '-I.', '-DCONFIG_NMBCLUSTERS=((1024 * 512) / MCLBYTES)', '-MD', '-MF', 'pmap.d',
      '-MJ', 'pmap.o.json', '-MP', '-o', 'pmap.o'] };
}
function getApi() { assert.ok(api, 'C04 macro capture tool is not implemented'); return api; }

test('preprocessing preserves argv values and removes all compile side outputs', () => {
  const plan = getApi().planPreprocess(entry(), root);
  assert.deepEqual(plan.args, ['-xc', source, '-DARM64_BOARD_CONFIG_QEMU_VIRT', '-mcpu=cortex-a76',
    '-arch', 'arm64', '-DCONFIG_PMAP_PPL', '-DXNU_KERNEL_PRIVATE', '-include', 'meta_features.h',
    '-I.', '-DCONFIG_NMBCLUSTERS=((1024 * 512) / MCLBYTES)', '-E', '-dM']);
  assert.equal(plan.compiler, compiler);
});
test('compiler substitution is rejected before any execution', () => {
  const item = entry(); item.arguments[0] = '/tmp/clang';
  assert.throws(() => getApi().planPreprocess(item, root), /COMPILER/);
});
test('later CPU and ABI overrides cannot pass the recipe check', () => {
  for (const flags of [['-mcpu=apple-m1'], ['--target=arm64e-apple-macos15.5'], ['-arch', 'arm64e']]) {
    const item = entry(); item.arguments.push(...flags);
    assert.throws(() => getApi().planPreprocess(item, root), /RECIPE/);
  }
});
test('Clang database separate -D operands and an explicit target are preserved', () => {
  const item = entry();
  item.arguments = [compiler, '-xc', source, '-c', '-D', 'ARM64_BOARD_CONFIG_QEMU_VIRT',
    '-mcpu=cortex-a76', '--target=arm64-apple-macosx15.5.0', '-D', 'CONFIG_PMAP_PPL',
    '-D', 'XNU_KERNEL_PRIVATE', '-include', 'meta_features.h', '-o', 'pmap.o'];
  assert.deepEqual(getApi().planPreprocess(item, root).args,
    ['-xc', source, '-D', 'ARM64_BOARD_CONFIG_QEMU_VIRT', '-mcpu=cortex-a76',
      '--target=arm64-apple-macosx15.5.0', '-D', 'CONFIG_PMAP_PPL', '-D', 'XNU_KERNEL_PRIVATE',
      '-include', 'meta_features.h', '-E', '-dM']);
});
test('joined dependency and output options cannot write over an object during preprocessing', () => {
  const item = entry(); item.arguments.push('-MFother.d', '-MJother.json', '-opmap-new.o');
  const plan = getApi().planPreprocess(item, root);
  assert.equal(plan.args.some(a => ['-MFother.d', '-MJother.json', '-opmap-new.o'].includes(a)), false);
});
test('a compilation database for another source cannot be replayed', () => {
  const item = entry(); item.file = root + '/xnu/osfmk/arm64/pcb.c';
  assert.throws(() => getApi().planPreprocess(item, root), /SOURCE/);
});
test('an output directory outside QEMU build is rejected', () => {
  const item = entry(); item.directory = root + '/xnu';
  assert.throws(() => getApi().planPreprocess(item, root), /DIRECTORY/);
});
test('injected range TLBI and diagnostic suppression are rejected', () => {
  for (const flag of ['-D__ARM_RANGE_TLBI__=1', '-DXNU_MONITOR=1', '-Wno-implicit-function-declaration']) {
    const item = entry(); item.arguments.push(flag);
    assert.throws(() => getApi().planPreprocess(item, root), /RECIPE/);
  }
});
test('defined zero, undefined, and expression-valued macros stay distinct', () => {
  const macros = getApi().selectMacros('#define XNU_MONITOR 0\n#define NO_MONITOR 1\n#define PVH_FLAG_IOMMU 0x4UL\n');
  assert.deepEqual(macros.XNU_MONITOR, { defined: true, value: '0' });
  assert.deepEqual(macros.CONFIG_SPTM, { defined: false, value: null });
  assert.deepEqual(macros.PVH_FLAG_IOMMU, { defined: true, value: '0x4UL' });
});
test('unrelated SDK macro text is excluded from the artifact', () => {
  const macros = getApi().selectMacros('#define UNRELATED_SDK_MACRO opaque_text\n#define __ARM_MIXED_PAGE_SIZE__ 1\n');
  assert.equal(JSON.stringify(macros).includes('opaque_text'), false);
  assert.deepEqual(macros.__ARM_MIXED_PAGE_SIZE__, { defined: true, value: '1' });
});
test('failed preprocessing cannot produce a valid matrix or a compile pass', () => {
  const report = getApi().preprocessResult({ status: 1, stdout: '#define NO_MONITOR 1\n', stderr: 'missing header' });
  assert.equal(report.status, 'PREPROCESS_FAILED');
  assert.equal(report.macros_valid, false);
  assert.equal(report.macros, null);
  assert.equal(report.pmap_compile_pass, false);
  assert.equal(report.C04, 'BLOCKED');
});
test('empty compiler output cannot be called a captured ARM64 matrix', () => {
  const report = getApi().preprocessResult({ status: 0, stdout: '', stderr: '' });
  assert.equal(report.macros_valid, false);
  assert.equal(report.macros, null);
});
test('a successful capture still cannot claim a pmap compile pass', () => {
  const report = getApi().preprocessResult({ status: 0, stdout: '#define __arm64__ 1\n#define NO_MONITOR 1\n', stderr: '' });
  assert.equal(report.status, 'PREPROCESS_CAPTURED');
  assert.equal(report.macros_valid, true);
  assert.equal(report.pmap_compile_pass, false);
  assert.equal(report.C04, 'BLOCKED');
});
