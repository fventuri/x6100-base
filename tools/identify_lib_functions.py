#!/usr/bin/env python3
"""Identify library functions inside an analyzed firmware image.

Given a raw firmware image, a list of recovered function boundaries, and one or
more static libraries (`.a`) that were plausibly used to build the firmware, this
tool reports which firmware functions correspond to which library symbols, each
with a confidence score in the interval [0, 1], and can classify every firmware
function as library / likely-library / application.

Method (relocation-aware FLIRT-style matching)
----------------------------------------------
For every function symbol in each library the tool reads the exact bytes of its
`.text.<name>` section and the ELF relocations that fall inside it. The field at
each code relocation (BL/B.W targets, MOVW/MOVT address halves, ABS32
literal-pool words, ...) is position dependent: the linker rewrites it when it
places the function at a concrete address. Those byte ranges are masked out,
leaving an invariant signature. For every firmware function the tool compares
`N` bytes (the symbol's length) from the function entry, counting matches only
over the invariant (unmasked) positions:

    confidence = matched_invariant_bytes / total_invariant_bytes

Applying the library's mask offsets to the firmware is sound because the same
compiler and linker produced both.

Locality (--locality)
---------------------
A linker places each pulled-in archive's objects contiguously, so byte-exact,
non-trivial matches of a library cluster into address regions. With --locality
the tool derives those regions from the confident matches and uses them to:
  * PROMOTE trivial / ambiguous byte-exact matches that fall inside the matching
    library's region (a 12-byte exact match is meaningless alone, but decisive
    inside the newlib block);
  * classify unmatched functions that sit inside a region as `likely-library`
    (version-variant library code, not application code);
  * DEMOTE trivial byte-exact matches that fall outside every region (untrusted).

Non-trivial gate and length tolerance
-------------------------------------
Short functions collide spuriously, so a match counts as confident only with at
least --min-invariant invariant bytes (unless promoted by locality). A candidate
is only compared when its length is within --length-tol (plus 5% of the symbol
length) of the firmware function, which rejects a short function matching a much
longer symbol by overrun.

The tool does not modify the Ghidra project or rename anything; it emits
evidence (CSV) only.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
import sys
from dataclasses import dataclass, field

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.elf.relocation import RelocationSection

RELOC_WIDTH_2 = {"R_ARM_THM_JUMP11", "R_ARM_THM_JUMP8",
                 "R_ARM_THM_ABS5", "R_ARM_THM_PC8"}
DEFAULT_RELOC_WIDTH = 4


@dataclass
class LibFunc:
    name: str
    obj: str
    libtag: str
    length: int
    data: bytes
    mask: bytearray  # 1 = invariant (compare), 0 = masked (position dependent)

    @property
    def invariant(self) -> int:
        return sum(self.mask)

    @property
    def sig_key(self):
        return (self.libtag, self.length,
                bytes(b for b, m in zip(self.data, self.mask) if m), bytes(self.mask))


@dataclass
class FwFunc:
    entry: int
    length: int
    name: str


@dataclass
class Result:
    fw: FwFunc
    ratio: float = 0.0
    best: list = field(default_factory=list)   # LibFunc achieving ratio (distinct sigs)


# --------------------------------------------------------------------------- #
# Library parsing
# --------------------------------------------------------------------------- #
def parse_library(lib_path: str, libtag: str) -> list[LibFunc]:
    members = subprocess.run(["ar", "t", lib_path], check=True,
                             capture_output=True, text=True).stdout.split()
    funcs: list[LibFunc] = []
    for member in members:
        blob = subprocess.run(["ar", "p", lib_path, member], check=True,
                              capture_output=True).stdout
        try:
            elf = ELFFile(io.BytesIO(blob))
        except Exception:
            continue
        funcs.extend(_functions_from_elf(elf, member, libtag))
    return funcs


def _functions_from_elf(elf, member, libtag) -> list[LibFunc]:
    symtab = next((s for s in elf.iter_sections()
                   if isinstance(s, SymbolTableSection)), None)
    if symtab is None:
        return []
    relocs_by_section: dict[int, list[tuple[int, int]]] = {}
    for sec in elf.iter_sections():
        if not isinstance(sec, RelocationSection):
            continue
        target = elf.get_section(sec.header["sh_info"])
        if target is None or not target.name.startswith(".text"):
            continue
        entries = relocs_by_section.setdefault(sec.header["sh_info"], [])
        for r in sec.iter_relocations():
            rtype = _reloc_type_name(elf, r)
            width = 2 if rtype in RELOC_WIDTH_2 else DEFAULT_RELOC_WIDTH
            entries.append((r["r_offset"], width))

    out: list[LibFunc] = []
    for sym in symtab.iter_symbols():
        if sym["st_info"]["type"] != "STT_FUNC" or sym["st_size"] == 0:
            continue
        shndx = sym["st_shndx"]
        if not isinstance(shndx, int):
            continue
        sec = elf.get_section(shndx)
        if sec is None:
            continue
        size = sym["st_size"]
        start = sym["st_value"] & ~1
        data = sec.data()[start:start + size]
        if len(data) < size:
            continue
        mask = bytearray([1]) * size
        for off, width in relocs_by_section.get(shndx, []):
            rel = off - start
            if 0 <= rel < size:
                for i in range(rel, min(rel + width, size)):
                    mask[i] = 0
        out.append(LibFunc(sym.name, member, libtag, size, data, mask))
    return out


def _reloc_type_name(elf, r) -> str:
    try:
        from elftools.elf.enums import ENUM_RELOC_TYPE_ARM
        rev = {v: k for k, v in ENUM_RELOC_TYPE_ARM.items()}
        return rev.get(r["r_info_type"], "")
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# Firmware
# --------------------------------------------------------------------------- #
def load_firmware(image_path, functions_csv):
    image = open(image_path, "rb").read()
    fws = []
    with open(functions_csv, newline="") as fh:
        for row in csv.DictReader(fh):
            entry = int(row["entry"], 16)
            length = int(row["body_max_exclusive"], 16) - int(row["body_min"], 16)
            fws.append(FwFunc(entry, length, row.get("name", "")))
    return image, fws


def fw_bytes(image, base, entry, n):
    off = entry - base
    if off < 0 or off + n > len(image):
        return None
    return image[off:off + n]


def score(lib: LibFunc, cand: bytes) -> float:
    inv = lib.invariant
    if inv == 0:
        return 0.0
    hit = sum(1 for i in range(lib.length) if lib.mask[i] and cand[i] == lib.data[i])
    return hit / inv


def match(image, base, fws, libs, length_tol):
    """Best-scoring library signature(s) for each firmware function."""
    by_sig = {}
    for lf in libs:
        by_sig.setdefault(lf.sig_key, []).append(lf)
    uniq = [g[0] for g in by_sig.values()]
    aliases = {g[0].name: sorted({x.name for x in g}) for g in by_sig.values()}

    results = []
    for fw in fws:
        r = Result(fw)
        for lf in uniq:
            if abs(fw.length - lf.length) > max(length_tol, int(lf.length * 0.05)):
                continue
            cand = fw_bytes(image, base, fw.entry, lf.length)
            if cand is None:
                continue
            s = score(lf, cand)
            if s > r.ratio + 1e-9:
                r.ratio, r.best = s, [lf]
            elif abs(s - r.ratio) <= 1e-9 and s > 0:
                r.best.append(lf)
        results.append(r)
    return results, aliases


# --------------------------------------------------------------------------- #
# Locality: derive library address regions from confident anchors
# --------------------------------------------------------------------------- #
def derive_regions(results, anchor_min_invariant, merge_gap):
    """Derive contiguous library blocks from confident anchors.

    Returns (blocks, anchors):
      blocks  = [(lo, hi), ...] merged across all libraries, using each anchor's
                extent [entry, entry+len) and merging intervals whose gap is
                <= merge_gap;
      anchors = [(addr, libtag), ...] sorted, for naming an in-block function by
                its nearest confident library match.
    """
    anchors = []       # (addr, libtag)
    extents = []       # (lo, hi)
    for r in results:
        if r.ratio < 0.999 or not r.best:
            continue
        lf = r.best[0]
        if lf.invariant < anchor_min_invariant:
            continue
        anchors.append((r.fw.entry, lf.libtag))
        extents.append((r.fw.entry, r.fw.entry + max(r.fw.length, lf.length)))
    if not extents:
        return [], []
    extents.sort()
    blocks = [list(extents[0])]
    for lo, hi in extents[1:]:
        if lo - blocks[-1][1] <= merge_gap:
            blocks[-1][1] = max(blocks[-1][1], hi)
        else:
            blocks.append([lo, hi])
    anchors.sort()
    return [(lo, hi) for lo, hi in blocks], anchors


def in_block(addr, blocks):
    return any(lo <= addr <= hi for lo, hi in blocks)


def nearest_lib(addr, anchors):
    """libtag of the confident anchor closest to addr."""
    best, bestd = None, None
    for a, tag in anchors:
        d = abs(a - addr)
        if bestd is None or d < bestd:
            bestd, best = d, tag
    return best


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classify(results, blocks, anchors, aliases, min_invariant, locality):
    rows = []
    for r in results:
        fw = r.fw
        addr = fw.entry
        inblk = in_block(addr, blocks) if locality else False
        reg = nearest_lib(addr, anchors) if (locality and inblk) else None
        exact = r.ratio >= 0.999 and bool(r.best)
        lf = r.best[0] if r.best else None
        names = sorted({b.name for b in r.best}) if r.best else []
        alias_all = sorted(set(sum((aliases.get(n, [n]) for n in names), [])))
        symbol = "|".join(names) if names else ""
        inv = lf.invariant if lf else 0
        libtag = lf.libtag if lf else ""
        note = ""

        if exact and inv >= min_invariant:
            cls, conf = "library", "VERIFIED"
            if len(names) > 1:
                note = "name ambiguous (byte-identical variants)"
        elif exact and inblk and reg == libtag:
            cls, conf = "library", "HIGH"
            note = "trivial match, corroborated by locality"
        elif exact and inblk:
            cls, conf = "library", "MEDIUM"
            note = f"trivial match; located in {reg} block (name uncertain)"
            libtag = f"{libtag}?/{reg}"
        elif exact and inv >= max(16, min_invariant // 2):
            # decent exact match, no locality support requested/available
            cls, conf = "library", "HIGH"
        elif inblk:
            cls, conf = "likely-library", "MEDIUM"
            libtag, symbol, inv = reg, "", 0
            note = "in library block, no byte-exact match (version variant?)"
        else:
            cls, conf = "application", ""
            if exact:  # trivial exact match, unsupported by locality -> untrusted
                note = "trivial byte match only; treated as application"
                libtag, symbol = "", ""

        rows.append({
            "fw_addr": f"0x{addr:08x}", "fw_name": fw.name, "fw_len": fw.length,
            "classification": cls, "confidence": conf, "library": libtag,
            "symbol": symbol,
            "aliases": ";".join(a for a in alias_all if a not in names),
            "match_ratio": f"{r.ratio:.4f}", "invariant_bytes": inv, "note": note,
        })
    return rows


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True)
    ap.add_argument("--base", default="0x08020000")
    ap.add_argument("--functions", required=True,
                    help="function_ranges.csv exported from Ghidra")
    ap.add_argument("--lib", required=True, action="append", metavar="[LABEL=]PATH",
                    help="static library; repeatable. Optional LABEL= prefix.")
    ap.add_argument("--min-invariant", type=int, default=32,
                    help="non-triviality gate: minimum invariant bytes (default 32)")
    ap.add_argument("--min-confidence", type=float, default=0.90,
                    help="only report matches at or above this ratio (default 0.90)")
    ap.add_argument("--length-tol", type=int, default=4,
                    help="allowed |fw_len - sym_len| in bytes, plus 5%% (default 4)")
    ap.add_argument("--keep-trivial", action="store_true",
                    help="in the matches CSV, also report matches below the invariant gate")
    ap.add_argument("--locality", action="store_true",
                    help="use derived library address regions to promote/demote matches")
    ap.add_argument("--anchor-min-invariant", type=int, default=48,
                    help="min invariant bytes for a match to anchor a region (default 48)")
    ap.add_argument("--merge-gap", type=lambda x: int(x, 0), default=2048,
                    help="merge anchor addresses within this gap into one region")
    ap.add_argument("--out", help="write per-function matches CSV")
    ap.add_argument("--classify", help="write full library/application classification CSV")
    args = ap.parse_args()

    base = int(args.base, 16)
    libs = []
    for spec in args.lib:
        if "=" in spec and not os.path.exists(spec):
            label, path = spec.split("=", 1)
        else:
            label, path = os.path.basename(spec), spec
        libs.extend(parse_library(path, label))
    image, fws = load_firmware(args.image, args.functions)
    sys.stderr.write(f"libraries: {len(libs)} FUNC symbols "
                     f"({len({l.libtag for l in libs})} archives); "
                     f"firmware: {len(fws)} functions\n")

    results, aliases = match(image, base, fws, libs, args.length_tol)
    blocks, anchors = derive_regions(results, args.anchor_min_invariant, args.merge_gap) \
        if args.locality else ([], [])
    if args.locality:
        sys.stderr.write("  library blocks: " +
                         ", ".join(f"0x{lo:08x}-0x{hi:08x}" for lo, hi in blocks) + "\n")

    # matches CSV (best match per fw function, above threshold)
    match_rows = []
    for r in results:
        if r.ratio < args.min_confidence or not r.best:
            continue
        lf = r.best[0]
        if lf.invariant < args.min_invariant and not args.keep_trivial:
            continue
        names = sorted({b.name for b in r.best})
        match_rows.append({
            "fw_addr": f"0x{r.fw.entry:08x}", "fw_name": r.fw.name,
            "symbol": "|".join(names), "library": lf.libtag,
            "confidence": f"{r.ratio:.4f}", "invariant_bytes": lf.invariant,
            "sym_len": lf.length, "fw_len": r.fw.length,
            "ambiguous": "yes" if len(names) > 1 else "",
        })
    match_rows.sort(key=lambda x: (-float(x["confidence"]), -int(x["invariant_bytes"])))
    mfields = ["fw_addr", "fw_name", "symbol", "library", "confidence",
               "invariant_bytes", "sym_len", "fw_len", "ambiguous"]
    if args.out:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=mfields); w.writeheader(); w.writerows(match_rows)
    if not args.classify:
        w = csv.DictWriter(sys.stdout, fieldnames=mfields); w.writeheader(); w.writerows(match_rows)

    # classification CSV (all functions)
    if args.classify:
        crows = classify(results, blocks, anchors, aliases, args.min_invariant, args.locality)
        crows.sort(key=lambda x: int(x["fw_addr"], 16))
        cfields = ["fw_addr", "fw_name", "fw_len", "classification", "confidence",
                   "library", "symbol", "aliases", "match_ratio", "invariant_bytes", "note"]
        with open(args.classify, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cfields); w.writeheader(); w.writerows(crows)
        from collections import Counter
        c = Counter(r["classification"] for r in crows)
        sys.stderr.write("classification: " +
                         "  ".join(f"{k}={v}" for k, v in sorted(c.items())) + "\n")

    sys.stderr.write(f"reported {len(match_rows)} matches "
                     f"(min_confidence={args.min_confidence}, min_invariant={args.min_invariant}, "
                     f"locality={'on' if args.locality else 'off'})\n")


if __name__ == "__main__":
    main()
