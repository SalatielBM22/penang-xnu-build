// SPDX-License-Identifier: MIT
// Audits the recorded C03 CI failure. It does not compile or emulate pmap.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const expected = [
  [37866, 4740, 32, "call to undeclared function 'generate_rtlbi_param'"],
  [37871, 4742, 3, "call to undeclared function 'flush_core_tlb_allrange_async'"],
  [37880, 4928, 16, "call to undeclared function 'ptep_get_iommu'"],
  [37911, 6601, 3, "call to undeclared function 'pmap_phys_write_disable'"],
  [37929, 12199, 2, "call to undeclared function 'pmap_ppl_lockdown_pages'"],
  [37945, 12209, 2, "call to undeclared function 'pmap_ppl_unlockdown_pages'"],
  [37959, 12511, 1, "static declaration of 'pmap_phys_write_disable' follows non-static declaration"],
];
export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

export function inspectLog(log) {
  const lines = log.split(/\r?\n/);
  const commands = lines.flatMap((text, i) => text.includes('/clang -c ') &&
    text.endsWith('/osfmk/arm/pmap/pmap.c') ? [{ line: i + 1, text }] : []);
  if (commands.length !== 1) throw Error('C04_COMMAND: require one actual pmap clang command');
  const command = commands[0];
  for (const flag of ['-DARM64_BOARD_CONFIG_QEMU_VIRT', '-mcpu=cortex-a76', '-arch arm64',
    '-DCONFIG_PMAP_PPL', '-DNOS_ARM_PMAP', '-include meta_features.h', '-DXNU_KERNEL_PRIVATE']) {
    if (!command.text.includes(' ' + flag + ' ')) throw Error('C04_RECIPE: missing ' + flag);
  }
  if (/-D(?:__ARM_RANGE_TLBI__|XNU_MONITOR|CONFIG_SPTM)(?:[=\s]|$)|-Wno-(?:error=)?implicit-function-declaration/.test(command.text)) {
    throw Error('C04_RECIPE: unrecorded monitor, range TLBI or diagnostic suppression flag');
  }
  const errors = lines.flatMap((text, i) => {
    const match = /^(.+\/osfmk\/arm\/pmap\/pmap\.c):(\d+):(\d+): (?:fatal )?error: (.*)$/.exec(text);
    return match ? [{ line: i + 1, source_line: +match[2], column: +match[3], diagnostic: match[4] }] : [];
  });
  if (errors.length !== expected.length || errors.some((e, i) =>
    e.line !== expected[i][0] || e.source_line !== expected[i][1] || e.column !== expected[i][2] ||
    !e.diagnostic.startsWith(expected[i][3]))) {
    throw Error('C04_DIAGNOSTICS: not the seven recorded clang errors, with original locations and symbols');
  }
  const failures = lines.flatMap((text, i) => text === 'make[7]: *** [pmap.o] Error 1' ? [{ line: i + 1, text }] : []);
  if (failures.length !== 1 || failures[0].line !== 37968) {
    throw Error('C04_OBJECT_FAILURE: the real failed pmap.o target is required');
  }
  return { status: 'RECORDED_CI_RED', command, errors, failure: failures[0],
    preprocessing: 'NOT_CAPTURED', new_pmap_object: false };
}

export function verifySources(manifest, root) {
  return manifest.files.map(file => {
    const bytes = readFileSync(resolve(root, file.path));
    const blob = createHash('sha1').update(Buffer.from('blob ' + bytes.length + '\0')).update(bytes).digest('hex');
    if (blob !== file.git_blob_sha1) throw Error('C04_SOURCE_HASH: ' + file.path);
    return { ...file, bytes: bytes.length, git_blob_verified: true, sha256: sha256(bytes) };
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const [logPath, manifestPath, sourceRoot, outputPath] = process.argv.slice(2);
    if (!logPath || !manifestPath || !sourceRoot || !outputPath) {
      throw Error('Usage: node c04_ci_evidence.mjs build.log source-manifest.json source-root output.json');
    }
    const bytes = readFileSync(logPath);
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    const report = { scope: 'C04_FIRST_CHECKPOINT_ONLY', ci_run: 40982551507, attempt: 1,
      build_commit: '791d289cabb7706c1e281377f4eba321ea3a8a9b', xnu_commit: manifest.commit,
      build_log_sha256: sha256(bytes), ...inspectLog(bytes.toString('utf8')),
      sources: verifySources(manifest, sourceRoot),
      pmap_compile_red_local: 'NOT_RUN', pmap_compile_green_local: 'NOT_RUN',
      macos_pmap_object: 'NOT_PRODUCED', gate_C04: 'BLOCKED', gate_P02: 'BLOCKED' };
    writeFileSync(outputPath, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ output: outputPath, status: report.status,
      errors: report.errors.length, source_files_verified: report.sources.length }));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 2;
  }
}
