#!/usr/bin/env bash
# Qualify the XNU typed-allocator builtins of the selected Xcode clang by real compilation,
# never by version: __builtin_xnu_type_signature, __builtin_xnu_type_summary and
# __builtin_xnu_types_compatible. Expected values come from the contract documented in
# xnu-11417.140.69 osfmk/kern/kalloc.h (granule encodings; summary bit 1<<G; types are
# compatible when identical or of equal signature). Every check runs and is recorded;
# the script exits non-zero if any failed.
# Usage: probe_xnu_builtins.sh <output key=value file>
set -uo pipefail
out="$1"
work=$(mktemp -d)
cc=$(xcrun --sdk macosx --find clang) || { echo "BUILTINS_QUALIFIED=FAIL (no clang)" | tee "$out"; exit 1; }
sdk=$(xcrun --sdk macosx --show-sdk-path)
status=0
record() { echo "$1=$2" | tee -a "$out"; [ "$2" = PASS ] || status=1; }
: > "$out"
echo "clang_path=$cc" | tee -a "$out"
echo "clang_version=$("$cc" --version | head -1)" | tee -a "$out"
echo "sdk=$sdk" | tee -a "$out"

cat > "$work/types.h" <<'EOF'
struct p01d_mixed { void *pointer; unsigned long data; };
struct p01d_data { unsigned long a, b; };
struct p01d_data_twin { unsigned long x, y; };
struct p01d_ptrs { void *a, *b; };
EOF
# 1. Presence, with a negative control proving __has_builtin discriminates.
cat > "$work/presence.c" <<'EOF'
#include "types.h"
#if !__has_builtin(__builtin_xnu_type_signature)
#error __builtin_xnu_type_signature unavailable
#endif
#if !__has_builtin(__builtin_xnu_type_summary)
#error __builtin_xnu_type_summary unavailable
#endif
#if !__has_builtin(__builtin_xnu_types_compatible)
#error __builtin_xnu_types_compatible unavailable
#endif
#if __has_builtin(__builtin_p01d_nonexistent_probe)
#error __has_builtin does not discriminate
#endif
const char *const p01d_sig = __builtin_xnu_type_signature(struct p01d_mixed);
const unsigned int p01d_summary = __builtin_xnu_type_summary(struct p01d_mixed);
const int p01d_compatible = __builtin_xnu_types_compatible(struct p01d_mixed, struct p01d_mixed);
EOF
# 2. Documented contract, evaluated by the compiler at compile time (as kalloc.h does).
cat > "$work/contract.c" <<'EOF'
#include "types.h"
#define GRANULES(t) (__builtin_xnu_type_summary(t) & 0xffff)
_Static_assert(GRANULES(struct p01d_ptrs) == (1u << 1), "pointer granules -> KT_GRANULE_POINTER");
_Static_assert(GRANULES(struct p01d_data) == (1u << 2), "scalar granules -> KT_GRANULE_DATA");
_Static_assert(GRANULES(struct p01d_mixed) == ((1u << 1) | (1u << 2)), "mixed record");
_Static_assert(__builtin_xnu_types_compatible(struct p01d_mixed, struct p01d_mixed), "reflexive");
_Static_assert(__builtin_xnu_types_compatible(struct p01d_data, struct p01d_data_twin), "equal signature");
_Static_assert(!__builtin_xnu_types_compatible(struct p01d_data, struct p01d_ptrs), "data vs pointers");
int p01d_contract_anchor;
EOF
# arm64 uses the QEMU_VIRT machine flag (-mcpu=cortex-a76); arm64e is the VMAPPLE baseline ABI.
for arch in arm64 arm64e; do
  cpu=""; [ "$arch" = arm64 ] && cpu="-mcpu=cortex-a76"  # no arrays: macOS /bin/bash is 3.2
  for unit in presence contract; do
    if "$cc" -arch "$arch" ${cpu:+"$cpu"} -isysroot "$sdk" -mkernel -ffreestanding -nostdinc -std=gnu11 \
         -Wall -Werror -c "$work/$unit.c" -o "$work/$unit-$arch.o" 2> "$work/$unit-$arch.err"; then
      record "kernel_${unit}_${arch}" PASS
      echo "kernel_${unit}_${arch}_object=$(otool -hv "$work/$unit-$arch.o" | tail -1 | tr -s ' ')" | tee -a "$out"
    else
      record "kernel_${unit}_${arch}" FAIL
      sed 's/^/  /' "$work/$unit-$arch.err" | head -20 | tee -a "$out"
    fi
  done
done
# 3. Record the actual values on the arm64 runner (informational, hex-encoded signatures).
cat > "$work/values.c" <<'EOF'
#include <stdio.h>
#include "types.h"
static void sig(const char *name, const char *s) {
  printf("signature_%s_hex=", name);
  for (; *s; s++) printf("%02x", (unsigned char)*s);
  printf("\n");
}
int main(void) {
  sig("mixed", __builtin_xnu_type_signature(struct p01d_mixed));
  sig("data", __builtin_xnu_type_signature(struct p01d_data));
  sig("ptrs", __builtin_xnu_type_signature(struct p01d_ptrs));
  printf("summary_mixed=0x%x\n", (unsigned)__builtin_xnu_type_summary(struct p01d_mixed));
  printf("summary_data=0x%x\n", (unsigned)__builtin_xnu_type_summary(struct p01d_data));
  printf("summary_ptrs=0x%x\n", (unsigned)__builtin_xnu_type_summary(struct p01d_ptrs));
  return 0;
}
EOF
if "$cc" -arch arm64 -isysroot "$sdk" -std=gnu11 -Wall -Werror "$work/values.c" -o "$work/values" \
     2> "$work/values.err" && "$work/values" > "$work/values.txt"; then
  tee -a "$out" < "$work/values.txt"
  record host_values_arm64 PASS
else
  record host_values_arm64 FAIL
  sed 's/^/  /' "$work/values.err" | head -20 | tee -a "$out"
fi
if [ "$status" -eq 0 ]; then echo "BUILTINS_QUALIFIED=PASS" | tee -a "$out"; else echo "BUILTINS_QUALIFIED=FAIL" | tee -a "$out"; fi
rm -rf "$work"
exit "$status"
