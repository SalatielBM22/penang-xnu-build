// Tests the historical CI evidence reader, never pmap compilation or enforcement.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const api = await import('./c04_ci_evidence.mjs').catch(() => null);
const log = readFileSync(new URL('../build/c04-inputs/build.log', import.meta.url), 'utf8');
function inspect(text) {
  assert.ok(api, 'C04 historical evidence reader is not implemented');
  return api.inspectLog(text);
}
const command = log.split(/\r?\n/).find(l => l.includes('/clang -c ') && l.endsWith('/arm/pmap/pmap.c'));
assert.ok(command, 'The real CI log input is required');

test('real CI input records seven errors and pmap failure without claiming GREEN', () => {
  const result = inspect(log);
  assert.equal(result.status, 'RECORDED_CI_RED');
  assert.equal(result.command.line, 37806);
  assert.equal(result.errors.length, 7);
  assert.equal(result.failure.line, 37968);
  assert.deepEqual(result.errors.map(e => [e.source_line, e.column]),
    [[4740,32], [4742,3], [4928,16], [6601,3], [12199,2], [12209,2], [12511,1]]);
  assert.equal(result.preprocessing, 'NOT_CAPTURED');
  assert.equal(result.new_pmap_object, false);
});
test('missing range diagnostic cannot pass', () => {
  assert.throws(() => inspect(log.replace(/^.*pmap\.c:4740:32: error:.*\r?\n/m, '')), /C04_DIAGNOSTICS/);
});
test('missing final static declaration diagnostic cannot pass', () => {
  assert.throws(() => inspect(log.replace(/^.*pmap\.c:12511:1: error:.*\r?\n/m, '')), /C04_DIAGNOSTICS/);
});
test('unexpected eighth pmap error cannot pass', () => {
  assert.throws(() => inspect(log + '\n/xnu/osfmk/arm/pmap/pmap.c:1:1: error: unexpected error\n'), /C04_DIAGNOSTICS/);
});
test('wrong symbol at the expected location cannot pass', () => {
  assert.throws(() => inspect(log.replace("function 'generate_rtlbi_param'", "function 'invented_stub'")), /C04_DIAGNOSTICS/);
});
test('absent compiler invocation cannot pass', () => {
  assert.throws(() => inspect(log.replace(command, '')), /C04_COMMAND/);
});
test('duplicate compiler invocation cannot pass', () => {
  assert.throws(() => inspect(log + '\n' + command + '\n'), /C04_COMMAND/);
});
test('Apple CPU substituted for Cortex-A76 cannot pass', () => {
  assert.throws(() => inspect(log.replace(command, command.replace('-mcpu=cortex-a76', '-mcpu=apple-m1'))), /C04_RECIPE/);
});
test('injected range-TLBI define cannot pass as the recorded recipe', () => {
  assert.throws(() => inspect(log.replace(command, command.replace(' -arch arm64 ', ' -D__ARM_RANGE_TLBI__=1 -arch arm64 '))), /C04_RECIPE/);
});
test('implicit declaration suppression cannot pass as the recorded recipe', () => {
  assert.throws(() => inspect(log.replace(command, command.replace(' -arch arm64 ', ' -Wno-implicit-function-declaration -arch arm64 '))), /C04_RECIPE/);
});
test('collector success cannot replace the failed object marker', () => {
  assert.throws(() => inspect(log.replace('make[7]: *** [pmap.o] Error 1', 'collector=PASS')), /C04_OBJECT_FAILURE/);
});
