// SPDX-License-Identifier: MIT
// Diagnostic-only: replay the compiler's -MJ argv for preprocessing, without a shell.
// Do not upload the full macro dump or expanded SDK/KDK header contents.
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, existsSync, writeFileSync } from 'node:fs';
import { posix, resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

const COMPILER = '/Applications/Xcode_16.4.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang';
const MACROS = ['XNU_MONITOR', 'NO_MONITOR', 'CONFIG_PMAP_PPL', 'CONFIG_SPTM',
  'PVH_FLAG_IOMMU', '__ARM_RANGE_TLBI__', '__ARM_MIXED_PAGE_SIZE__',
  'ARM_PARAMETERIZED_PMAP', '__ARM_16K_PG__', '__ARM_KERNEL_PROTECT__',
  'HAS_FEAT_XS', '__arm64__', '__arm64e__', '__ARM_FEATURE_PAUTH'];
const digest = value => createHash('sha256').update(value).digest('hex');

export function planPreprocess(entry, dxbRoot) {
  const root = posix.resolve(dxbRoot);
  const source = root + '/xnu/osfmk/arm/pmap/pmap.c';
  if (!entry || entry.file !== source || !entry.arguments?.includes(source)) {
    throw Error('C04_SOURCE: expected the absolute pmap.c source in both file and argv');
  }
  const prefix = root + '/build/xnu.obj/RELEASE_ARM64_QEMU_VIRT/';
  if (typeof entry.directory !== 'string' || !posix.resolve(entry.directory).startsWith(prefix)) {
    throw Error('C04_DIRECTORY: require the QEMU_VIRT object directory');
  }
  if (entry.arguments[0] !== COMPILER) throw Error('C04_COMPILER: unexpected compiler');
  const original = entry.arguments.slice(1);
  const normalized = original.flatMap((a, i) => a === '-D' ? [] :
    original[i - 1] === '-D' ? ['-D' + a] : [a]);
  const arm64 = original.some((a, i) => a === '-arch' && original[i + 1] === 'arm64') ||
    original.some(a => /^--target=arm64-apple-/.test(a)) ||
    original.some((a, i) => a === '-target' && /^arm64-apple-/.test(original[i + 1] ?? ''));
  const required = ['-DARM64_BOARD_CONFIG_QEMU_VIRT', '-mcpu=cortex-a76', '-DXNU_KERNEL_PRIVATE', '-DCONFIG_PMAP_PPL'];
  const wrongTarget = original.some((a, i) =>
    (a.startsWith('-mcpu=') && a !== '-mcpu=cortex-a76') ||
    (a === '-arch' && original[i + 1] !== 'arm64') ||
    (a.startsWith('--target=') && !/^--target=arm64-apple-/.test(a)) ||
    (a === '-target' && !/^arm64-apple-/.test(original[i + 1] ?? '')));
  if (!arm64 || wrongTarget || required.some(flag => !normalized.includes(flag)) || normalized.some(a =>
    /^(?:-D(?:__ARM_RANGE_TLBI__|XNU_MONITOR|CONFIG_SPTM)(?:=|$)|-Wno-(?:error=)?implicit-function-declaration)/.test(a))) {
    throw Error('C04_RECIPE: unexpected CPU, board, monitor, range feature or suppression');
  }
  const args = [];
  for (let i = 0; i < original.length; i++) {
    const arg = original[i];
    if (['-o', '-MF', '-MJ', '-MT', '-MQ'].includes(arg)) {
      if (++i >= original.length) throw Error('C04_RECIPE: missing output option argument');
    } else if (!['-c', '-MD', '-MMD', '-MP'].includes(arg) && !/^-M[FJTQ]/.test(arg) && !arg.startsWith('-o')) {
      args.push(arg);
    }
  }
  return { compiler: COMPILER, directory: entry.directory, args: [...args, '-E', '-dM'] };
}

export function selectMacros(text) {
  const values = new Map();
  for (const line of text.split(/\r?\n/)) {
    const match = /^#define ([A-Za-z_][A-Za-z_0-9]*)(?:[ \t]+(.*))?$/.exec(line);
    if (match && MACROS.includes(match[1])) values.set(match[1], match[2] ?? '');
  }
  return Object.fromEntries(MACROS.map(name => [name,
    values.has(name) ? { defined: true, value: values.get(name) } : { defined: false, value: null }]));
}

export function preprocessResult(result) {
  const ok = result.status === 0 && !result.error && /^#define __arm64__ 1\s*$/m.test(result.stdout ?? '');
  return { status: ok ? 'PREPROCESS_CAPTURED' : 'PREPROCESS_FAILED',
    compiler_exit_code: result.status, macros_valid: ok,
    macros: ok ? selectMacros(result.stdout ?? '') : null,
    macro_dump_sha256: digest(result.stdout ?? ''), diagnostics_sha256: digest(result.stderr ?? ''),
    execution_error: result.error?.code ?? null, pmap_compile_pass: false, C04: 'BLOCKED' };
}

function findDatabase(root) {
  if (!existsSync(root)) return [];
  return readdirSync(root, { withFileTypes: true }).flatMap(item =>
    item.isDirectory() ? findDatabase(join(root, item.name)) :
      item.isFile() && item.name === 'pmap.o.json' ? [join(root, item.name)] : []);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) {
    console.error('Usage: node c04_capture_pmap.mjs dxb-root report.json');
    process.exitCode = 2;
  } else {
    let report = { scope: 'C04_DIAGNOSTIC_ONLY', status: 'NOT_RUN', macros_valid: false,
      pmap_compile_pass: false, C04: 'BLOCKED', new_ci_compile_pass_claim: false };
    try {
      const root = resolve(input);
      const databases = findDatabase(join(root, 'build/xnu.obj/RELEASE_ARM64_QEMU_VIRT'));
      if (databases.length !== 1) throw Error('C04_DATABASE: require exactly one pmap.o.json');
      const bytes = readFileSync(databases[0]);
      const entry = JSON.parse(bytes.toString('utf8').trim().replace(/,\s*$/, ''));
      const plan = planPreprocess(entry, root);
      const result = spawnSync(plan.compiler, plan.args, { cwd: plan.directory, shell: false,
        encoding: 'utf8', timeout: 60000, maxBuffer: 32 * 1024 * 1024 });
      report = { ...report, compilation_database: databases[0], database_sha256: digest(bytes),
        source_sha256: digest(readFileSync(entry.file)), plan, ...preprocessResult(result) };
      if (!report.macros_valid) process.exitCode = 2;
    } catch (error) {
      report.status = 'CAPTURE_BLOCKED';
      report.reason = error.message;
      process.exitCode = 2;
    }
    writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    console.log(JSON.stringify({ status: report.status, C04: report.C04, output }));
  }
}
