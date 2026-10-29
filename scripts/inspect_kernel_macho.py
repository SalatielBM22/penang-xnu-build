#!/usr/bin/env python3
"""Inspect an XNU kernel Mach-O for the P0.1D QEMU_VIRT acceptance gates.

Pure Python, no Apple tools, so the same check runs on the macOS runner and again,
independently, on the downloaded artifact under Linux. Whole-image instruction counts
are encoding matches inside instruction sections (literal pools can inflate them) and
are informational. The gates use the bounded initial path: breadth-first static
exploration of direct control flow (B, B.cond, CBZ/CBNZ, TBZ/TBNZ, BL callees) from the
LC_UNIXTHREAD entry, ending at indirect branches/returns, up to --window instructions.
Register values come only from MOVZ/MOVK/MOVN along one path, so they are approximate.
"""
import argparse, hashlib, json, struct, sys
from collections import deque
from pathlib import Path

CPU_TYPE_ARM64 = 0x0100000C
SUBTYPES = {0: "ARM64_ALL", 1: "ARM64_V8", 2: "ARM64E"}
ARM64E_CHAINED = {1: "ARM64E", 7: "ARM64E_KERNEL", 9: "ARM64E_USERLAND", 10: "ARM64E_FIRMWARE",
                  12: "ARM64E_USERLAND24", 13: "ARM64E_SHARED_CACHE", 14: "ARM64E_SEGMENTED"}
INSTRUCTION_ATTRS = 0x80000000 | 0x00000400
HINT_PAC = {0xD503201F | n << 5 for n in (7, 8, 10, 12, 14, 24, 25, 26, 27, 28, 29, 30, 31)}
HINT_BTI = {0xD503201F | n << 5 for n in (32, 34, 36, 38)}
NAMED = {(3, 0, 1, 0, 0): "SCTLR_EL1", (3, 0, 1, 0, 2): "CPACR_EL1", (3, 0, 2, 0, 0): "TTBR0_EL1",
         (3, 0, 2, 0, 1): "TTBR1_EL1", (3, 0, 2, 0, 2): "TCR_EL1", (3, 0, 10, 2, 0): "MAIR_EL1",
         (3, 0, 12, 0, 0): "VBAR_EL1", (3, 3, 4, 2, 2): "SVCR", (3, 0, 1, 2, 6): "SMCR_EL1"}
GATED = ("pac_dp1", "pacga", "pac_branch", "pac_load", "pac_key_sysreg")
PARAVIRT_PAC = {0xC1000000 | n for n in (0, 1, 2, 3, 4, 5, 6, 0xF0)}


def fail(reason):
    raise ValueError(reason)


def classify(w):
    """Classes of one A64 word that matter for a non-PAuth Cortex-A76 (FEAT_PAuth absent)."""
    if w in HINT_PAC:
        return "pac_hint"  # HINT space: executes as NOP without FEAT_PAuth
    if w in HINT_BTI:
        return "bti_hint"
    if (w & 0xFFFF0000) == 0xDAC10000 and ((w >> 10) & 0x3F) <= 0x11:
        return "pac_dp1"  # PACIA..AUTDZB, XPACI/XPACD: UNDEFINED without FEAT_PAuth
    if (w & 0xFFE0FC00) == 0x9AC03000:
        return "pacga"
    if ((w & 0xFFFFF81F) in (0xD61F081F, 0xD63F081F) or (w & 0xFFFFF800) in (0xD71F0800, 0xD73F0800)
            or (w & 0xFFFFFBFF) in (0xD65F0BFF, 0xD69F0BFF)):
        return "pac_branch"  # BRAA*/BLRAA*/RETAA/ERETAA families
    if (w & 0xFF200400) == 0xF8200400:
        return "pac_load"  # LDRAA/LDRAB
    if (w & 0xFFFFF0FF) == 0xD503407F:
        return "sme_pstate"  # SMSTART/SMSTOP
    if (w & 0xFFE0001F) == 0xD4000002:
        return "hvc"
    if (w & 0xFFE0001F) == 0xD4000003:
        return "smc"
    if (w & 0xFFD00000) == 0xD5100000:  # MSR/MRS (register)
        reg = sysreg(w)
        if reg[0] == 3 and reg[1] == 0 and reg[2] == 2 and reg[3] in (1, 2, 3):
            return "pac_key_sysreg"
        if reg in ((3, 3, 4, 2, 2), (3, 0, 1, 2, 6)):
            return "sme_sysreg"
        if reg[0] == 3 and reg[2] in (11, 15):
            return "impl_defined_sysreg"
    return None


def sysreg(w):
    return (2 + ((w >> 19) & 1), (w >> 16) & 7, (w >> 12) & 15, (w >> 8) & 15, (w >> 5) & 7)


def sysreg_name(reg):
    return NAMED.get(reg, "S%d_%d_C%d_C%d_%d" % reg)


def parse(data):
    if len(data) < 32:
        fail("truncated Mach-O")
    magic, cpu, sub, kind, ncmds, cmdsize, flags, _ = struct.unpack_from("<8I", data)
    if magic != 0xFEEDFACF:
        fail("not a 64-bit little-endian Mach-O")
    end, off = 32 + cmdsize, 32
    if end > len(data):
        fail("load commands exceed file")
    segs, sects, entries, chained = [], [], [], []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", data, off)
        if size < 8 or off + size > end:
            fail("invalid load command size")
        if cmd == 0x19:
            name, va, vm, fo, fs, maxp, prot, ns, sflags = struct.unpack_from("<16sQQQQiiII", data, off + 8)
            seg = dict(name=name.rstrip(b"\0").decode(), vmaddr=va, vmsize=vm, fileoff=fo, filesize=fs,
                       maxprot=maxp, initprot=prot, nsects=ns, sections=[])
            for i in range(ns):
                s = off + 72 + 80 * i
                sname = data[s:s + 16].rstrip(b"\0").decode()
                addr, ssize, soff, align = struct.unpack_from("<QQII", data, s + 32)
                attrs = struct.unpack_from("<I", data, s + 64)[0]
                sec = dict(name=sname, addr=addr, size=ssize, offset=soff, align=1 << align, flags=attrs)
                seg["sections"].append(sname)
                sects.append(dict(sec, segment=seg["name"]))
            segs.append(seg)
        elif cmd == 0x5:
            flavor, count = struct.unpack_from("<II", data, off + 8)
            if (flavor, count) != (6, 68):
                fail("unexpected thread state flavor/count %d/%d" % (flavor, count))
            entries.append(struct.unpack_from("<Q", data, off + 16 + 32 * 8)[0])
        elif cmd == 0x80000034:
            chained.append(struct.unpack_from("<II", data, off + 8))
        off += size
    return dict(cputype=cpu, cpusubtype=sub, filetype=kind, flags=flags, segments=segs,
                sections=sects, entries=entries, chained=chained)


def chained_formats(data, chained):
    formats = set()
    for dataoff, size in chained:
        _, starts, *_ = struct.unpack_from("<7I", data, dataoff)
        base = dataoff + starts
        count = struct.unpack_from("<I", data, base)[0]
        for i in range(count):
            seg_off = struct.unpack_from("<I", data, base + 4 + 4 * i)[0]
            if seg_off:
                formats.add(struct.unpack_from("<H", data, base + seg_off + 6)[0])
    return sorted(formats)


def word_reader(data, sections):
    code = [s for s in sections if s["flags"] & INSTRUCTION_ATTRS and s["size"]]

    def read(va):
        for s in code:
            if s["addr"] <= va and va + 4 <= s["addr"] + s["size"]:
                return struct.unpack_from("<I", data, s["offset"] + va - s["addr"])[0]
        return None
    return code, read


def branch_target(pc, w, bits, shift):
    imm = (w >> shift) & ((1 << bits) - 1)
    if imm >> (bits - 1):
        imm -= 1 << bits
    return (pc + (imm << 2)) & ((1 << 64) - 1)


def initial_path(read, entry, window):
    """Bounded static exploration of direct control flow from the entry point."""
    work, seen, events, counts, calls, stops, steps = deque([(entry, {})]), set(), [], {}, set(), [], 0
    first = read(entry)
    while work and steps < window:
        pc, regs = work.popleft()
        while steps < window and pc not in seen:
            w = read(pc)
            if w is None:
                stops.append("outside code at %s" % hex(pc))
                break
            seen.add(pc)
            steps += 1
            if not step(pc, w, regs, counts, events):
                stops.append("indirect branch or return at %s" % hex(pc))
                break
            if (w & 0xFC000000) == 0x14000000 or (w & 0xFF00001F) == 0x5400000E:  # B, B.AL
                pc = branch_target(pc, w, 26, 0) if w >> 26 == 5 else branch_target(pc, w, 19, 5)
                continue
            if (w & 0xFC000000) == 0x94000000:  # BL: explore callee, x0-x18 clobbered
                target = branch_target(pc, w, 26, 0)
                calls.add(target)
                work.append((target, {}))
                for r in range(19):
                    regs.pop(r, None)
            elif (w & 0xFF000010) == 0x54000000 or (w & 0x7E000000) == 0x34000000:  # B.cond, CBZ/CBNZ
                work.append((branch_target(pc, w, 19, 5), dict(regs)))
            elif (w & 0x7E000000) == 0x36000000:  # TBZ/TBNZ
                work.append((branch_target(pc, w, 14, 5), dict(regs)))
            pc += 4
    return dict(first_word=hex(first) if first is not None else None, instructions=steps,
                window_exhausted=steps >= window, direct_calls=len(calls), stops=stops[:32],
                counts=counts, events=events[:256], events_total=len(events))


def step(pc, w, regs, counts, events):
    """Account one instruction; return False when static control flow ends here."""
    kind = classify(w)
    if kind:
        counts[kind] = counts.get(kind, 0) + 1
    if (w & 0x7F800000) in (0x52800000, 0x72800000, 0x12800000):  # MOVZ/MOVK/MOVN
        rd, sh, imm = w & 31, 16 * ((w >> 21) & 3), (w >> 5) & 0xFFFF
        mask = (1 << 64) - 1 if w >> 31 else (1 << 32) - 1
        op = (w >> 29) & 3
        if op == 2:
            regs[rd] = (imm << sh) & mask
        elif op == 0:
            regs[rd] = ~(imm << sh) & mask
        elif op == 3 and rd in regs:
            regs[rd] = (regs[rd] & ~(0xFFFF << sh) | imm << sh) & mask
    elif (w & 0xFFF00000) == 0xD5100000:  # MSR (register)
        reg = sysreg(w)
        events.append(dict(va=hex(pc), op="msr", reg=sysreg_name(reg),
                           value=hex(regs[w & 31]) if (w & 31) in regs else None, cls=kind))
    elif (w >> 26) & 7 == 4 or (w >> 25) & 7 == 5 or (w >> 25) & 5 == 4:
        # Other data-processing or any load/store: forget Rd/Rt (and Rt2) conservatively.
        regs.pop(w & 31, None)
        if (w >> 25) & 5 == 4:
            regs.pop((w >> 10) & 31, None)
    elif (w & 0xFFF00000) == 0xD5300000:
        regs.pop(w & 31, None)
        if kind:
            events.append(dict(va=hex(pc), op="mrs", reg=sysreg_name(sysreg(w)), cls=kind))
    elif kind in ("hvc", "smc"):
        events.append(dict(va=hex(pc), op=kind, imm=(w >> 5) & 0xFFFF,
                           x0=hex(regs[0]) if 0 in regs else None))
    elif kind and kind not in ("pac_hint", "bti_hint"):
        events.append(dict(va=hex(pc), op="insn", word=hex(w), cls=kind))
    return not ((w & 0xFFFFFC1F) in (0xD61F0000, 0xD63F0000, 0xD65F0000) or w == 0xD69F03E0
                or kind == "pac_branch")


def decode_tcr(v):
    tg0 = {0: "4K", 1: "64K", 2: "16K"}.get((v >> 14) & 3)
    tg1 = {1: "16K", 2: "4K", 3: "64K"}.get((v >> 30) & 3)
    return dict(T0SZ=v & 63, TG0=tg0, T1SZ=(v >> 16) & 63, TG1=tg1, IPS=(v >> 32) & 7,
                TBI0=(v >> 37) & 1, TBI1=(v >> 38) & 1)


def inspect(path, window):
    data = Path(path).read_bytes()
    m = parse(data)
    base_sub = m["cpusubtype"] & 0x00FFFFFF
    code, read = word_reader(data, m["sections"])
    totals = {}
    for s in code:
        for (w,) in struct.iter_unpack("<I", data[s["offset"]:s["offset"] + (s["size"] & ~3)]):
            kind = classify(w)
            if kind:
                totals[kind] = totals.get(kind, 0) + 1
    report = dict(file=Path(path).name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                  cputype=hex(m["cputype"]), cpusubtype=hex(m["cpusubtype"]),
                  subtype=SUBTYPES.get(base_sub, "UNKNOWN_%d" % base_sub), filetype=m["filetype"],
                  flags=hex(m["flags"]),
                  segments=[dict(s, vmaddr=hex(s["vmaddr"]), vmsize=hex(s["vmsize"]),
                                 fileoff=hex(s["fileoff"]), filesize=hex(s["filesize"]))
                            for s in m["segments"]],
                  entries=[hex(e) for e in m["entries"]],
                  chained_pointer_formats=chained_formats(data, m["chained"]),
                  whole_image_counts=totals)
    loaded = [s for s in m["segments"] if s["vmsize"]]
    report["vm_span"] = [hex(min(s["vmaddr"] for s in loaded)), hex(max(s["vmaddr"] + s["vmsize"] for s in loaded))]
    report["segments_16k_aligned"] = all(s["vmaddr"] % 0x4000 == 0 for s in loaded)
    if len(m["entries"]) == 1:
        path_info = initial_path(read, m["entries"][0], window)
        for ev in path_info["events"]:
            if ev.get("reg") == "TCR_EL1" and ev.get("value"):
                ev["decoded"] = decode_tcr(int(ev["value"], 16))
        report["initial_path"] = path_info
    gates = {
        "cputype_arm64": m["cputype"] == CPU_TYPE_ARM64,
        "native_arm64_not_arm64e": base_sub in (0, 1),
        "mh_execute": m["filetype"] == 2,
        "single_entry_in_code": len(m["entries"]) == 1 and read(m["entries"][0]) is not None,
        "no_arm64e_chained_fixups": not set(report["chained_pointer_formats"]) & set(ARM64E_CHAINED),
        "initial_path_without_pauth": "initial_path" in report and
            not any(report["initial_path"]["counts"].get(k) for k in GATED),
        # osfmk/arm64/hv_hvc.h: VMAPPLE_PAC_* = HVC_CPU_SERVICE (0xc1000000) | {0..6, 0xf0}.
        # An HVC whose x0 cannot be reconstructed cannot be cleared, so it also fails.
        "initial_path_without_paravirt_pac_hvc": "initial_path" in report and not any(
            ev["op"] == "hvc" and (ev["x0"] is None or int(ev["x0"], 16) in PARAVIRT_PAC)
            for ev in report["initial_path"]["events"]),
    }
    report["gates"] = gates
    report["passed"] = all(gates.values())
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("kernel")
    ap.add_argument("--window", type=int, default=4096)
    ap.add_argument("--out")
    ap.add_argument("--require-gates", action="store_true", help="exit 1 unless every gate passes")
    a = ap.parse_args()
    try:
        report = inspect(a.kernel, a.window)
    except (ValueError, struct.error) as exc:
        report = dict(file=a.kernel, error=str(exc), passed=False)
    text = json.dumps(report, indent=1) + "\n"
    if a.out:
        Path(a.out).write_text(text)
    print(json.dumps({k: report.get(k) for k in ("file", "sha256", "subtype", "entries", "gates", "passed", "error")
                      if k in report}, indent=1))
    if a.require_gates and not report.get("passed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
