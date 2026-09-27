#!/usr/bin/env python3
"""Identify library functions inside an analyzed firmware image.

Given a raw firmware image, a list of recovered function boundaries, and a
static library (`.a`) that was plausibly used to build the firmware, this tool
reports which firmware functions correspond to which library symbols, each with
a confidence score in the interval [0, 1].

Method (relocation-aware FLIRT-style matching)
----------------------------------------------
For every function symbol in the library, the tool reads the exact bytes of its
`.text.<name>` section and the ELF relocations that fall inside it. The 4-byte
field at each code relocation (BL/B.W targets, MOVW/MOVT address halves, ABS32
literal-pool words, ...) is *position dependent*: the linker rewrites it when it
places the function at a concrete address. Those byte ranges are therefore
masked out, leaving an invariant signature of the position-independent bytes.

For every firmware function the tool compares `N` bytes (the library symbol's
length) starting at the function entry, counting matches only over the invariant
(unmasked) positions. Applying the library's mask offsets to the firmware is
sound because the same compiler and linker produced both: identical source +
identical toolchain => identical instruction encodings and identical literal-pool
layout, differing only in the relocated fields.

    confidence = matched_invariant_bytes / total_invariant_bytes

"Non-trivial" gate
------------------
Short functions collide spuriously (a 3-instruction leaf can match dozens of
unrelated symbols). A match is only reported as confident when its function has
at least `--min-invariant` invariant bytes. Below that it is dropped (or listed
as trivial with `--keep-trivial`).

Ambiguity
---------
If several *distinct* library signatures achieve the same top score for one
firmware function, the match is flagged ambiguous and its names are all listed.
Library symbols that share byte-identical signatures are grouped and reported
together (a real match whose name cannot be resolved by bytes alone).

The tool does not modify the Ghidra project or rename anything; it emits
evidence (CSV) only.
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from dataclasses import dataclass, field

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from elftools.elf.relocation import RelocationSection

# ARM (AAELF32) relocation types whose encoded field is a single 16-bit Thumb
# instruction (2 bytes). Everything else we treat as a 4-byte field, which is
# correct for the common Thumb-2 (BL, B.W, MOVW, MOVT) and data (ABS32/REL32)
# relocations and is conservative (over-masking only reduces discrimination).
RELOC_WIDTH_2 = {
    "R_ARM_THM_JUMP11",  # 102
    "R_ARM_THM_JUMP8",   # 103
    "R_ARM_THM_ABS5",
    "R_ARM_THM_PC8",
}
DEFAULT_RELOC_WIDTH = 4


@dataclass
class LibFunc:
    name: str
    obj: str
    length: int
    data: bytes
    mask: bytearray  # 1 = invariant (compare), 0 = masked (position dependent)
    reloc_targets: list = field(default_factory=list)  # (offset, symbol_name)

    @property
    def invariant(self) -> int:
        return sum(self.mask)

    @property
    def sig_key(self):
        """Byte-identical-signature key: length + invariant bytes only."""
        return (self.length, bytes(b for b, m in zip(self.data, self.mask) if m),
                bytes(self.mask))


@dataclass
class FwFunc:
    entry: int
    length: int
    name: str


def parse_library(lib_path: str) -> list[LibFunc]:
    """Extract every FUNC symbol from every object in an `ar` archive."""
    members = subprocess.run(
        ["ar", "t", lib_path], check=True, capture_output=True, text=True
    ).stdout.split()
    funcs: list[LibFunc] = []
    for member in members:
        blob = subprocess.run(
            ["ar", "p", lib_path, member], check=True, capture_output=True
        ).stdout
        try:
            elf = ELFFile(io.BytesIO(blob))
        except Exception:
            continue
        funcs.extend(_functions_from_elf(elf, member))
    return funcs


def _functions_from_elf(elf: ELFFile, member: str) -> list[LibFunc]:
    symtab = next(
        (s for s in elf.iter_sections() if isinstance(s, SymbolTableSection)), None
    )
    if symtab is None:
        return []

    # Map "section index -> list of (reloc_offset, width, target_symbol_name)".
    relocs_by_section: dict[int, list[tuple[int, int, str]]] = {}
    for sec in elf.iter_sections():
        if not isinstance(sec, RelocationSection):
            continue
        target_idx = sec.header["sh_info"]  # section these relocs apply to
        target = elf.get_section(target_idx)
        if target is None or not target.name.startswith((".text", ".rel.text")):
            continue
        rsymtab = elf.get_section(sec.header["sh_link"])
        entries = relocs_by_section.setdefault(target_idx, [])
        for r in sec.iter_relocations():
            rtype = _reloc_type_name(elf, r)
            width = 2 if rtype in RELOC_WIDTH_2 else DEFAULT_RELOC_WIDTH
            sym = rsymtab.get_symbol(r["r_info_sym"])
            entries.append((r["r_offset"], width, sym.name if sym else ""))

    out: list[LibFunc] = []
    for sym in symtab.iter_symbols():
        if sym["st_info"]["type"] != "STT_FUNC":
            continue
        size = sym["st_size"]
        if size == 0:
            continue
        shndx = sym["st_shndx"]
        if not isinstance(shndx, int):
            continue
        sec = elf.get_section(shndx)
        if sec is None:
            continue
        start = sym["st_value"] & ~1  # clear Thumb bit
        data = sec.data()[start:start + size]
        if len(data) < size:
            continue
        mask = bytearray([1]) * size
        targets = []
        for off, width, tname in relocs_by_section.get(shndx, []):
            rel = off - start
            if 0 <= rel < size:
                for i in range(rel, min(rel + width, size)):
                    mask[i] = 0
                targets.append((rel, tname))
        out.append(LibFunc(sym.name, member, size, data, mask, targets))
    return out


def _reloc_type_name(elf: ELFFile, r) -> str:
    try:
        from elftools.elf.enums import ENUM_RELOC_TYPE_ARM
        rev = {v: k for k, v in ENUM_RELOC_TYPE_ARM.items()}
        return rev.get(r["r_info_type"], "")
    except Exception:
        return ""


def load_firmware(image_path: str, base: int, functions_csv: str):
    with open(image_path, "rb") as fh:
        image = fh.read()
    fws: list[FwFunc] = []
    with open(functions_csv, newline="") as fh:
        for row in csv.DictReader(fh):
            entry = int(row["entry"], 16)
            bmin = int(row["body_min"], 16)
            bmax = int(row["body_max_exclusive"], 16)
            fws.append(FwFunc(entry=entry, length=bmax - bmin,
                              name=row.get("name", "")))
    return image, fws


def fw_bytes(image: bytes, base: int, entry: int, n: int) -> bytes | None:
    off = entry - base
    if off < 0 or off + n > len(image):
        return None
    return image[off:off + n]


def score(lib: LibFunc, cand: bytes) -> float:
    inv = lib.invariant
    if inv == 0:
        return 0.0
    hit = sum(1 for i in range(lib.length)
              if lib.mask[i] and cand[i] == lib.data[i])
    return hit / inv


def match(image, base, fws, libs, length_tol, min_ratio):
    """For each firmware function, find its best-scoring library signature(s)."""
    # Collapse byte-identical library signatures so aliases are grouped.
    by_sig: dict = {}
    for lf in libs:
        by_sig.setdefault(lf.sig_key, []).append(lf)
    uniq = [group[0] for group in by_sig.values()]
    aliases = {group[0].name: [g.name for g in group] for group in by_sig.values()}

    results = []
    for fw in fws:
        best_ratio = 0.0
        best = []  # list of LibFunc achieving best_ratio (distinct signatures)
        for lf in uniq:
            if abs(fw.length - lf.length) > max(length_tol, int(lf.length * 0.05)):
                continue
            cand = fw_bytes(image, base, fw.entry, lf.length)
            if cand is None:
                continue
            r = score(lf, cand)
            if r > best_ratio + 1e-9:
                best_ratio, best = r, [lf]
            elif abs(r - best_ratio) <= 1e-9 and r > 0:
                best.append(lf)
        if best_ratio < min_ratio or not best:
            results.append((fw, None, 0.0, [], aliases))
            continue
        results.append((fw, best[0], best_ratio, best, aliases))
    return results, aliases


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True, help="raw firmware .bin")
    ap.add_argument("--base", default="0x08020000",
                    help="firmware load base (default 0x08020000)")
    ap.add_argument("--functions", required=True,
                    help="function_ranges.csv exported from Ghidra")
    ap.add_argument("--lib", required=True, help="static library .a")
    ap.add_argument("--min-invariant", type=int, default=48,
                    help="non-triviality gate: minimum invariant bytes (default 48)")
    ap.add_argument("--min-confidence", type=float, default=0.90,
                    help="only report matches at or above this confidence (default 0.90)")
    ap.add_argument("--length-tol", type=int, default=8,
                    help="allowed |fw_len - sym_len| in bytes (default 8)")
    ap.add_argument("--keep-trivial", action="store_true",
                    help="also report matches below the invariant-bytes gate")
    ap.add_argument("--out", help="write matches to this CSV")
    args = ap.parse_args()

    base = int(args.base, 16) if isinstance(args.base, str) else args.base
    libs = parse_library(args.lib)
    image, fws = load_firmware(args.image, base, args.functions)
    sys.stderr.write(
        f"library: {len(libs)} FUNC symbols; firmware: {len(fws)} functions\n")

    results, aliases = match(image, base, fws, libs, args.length_tol,
                             args.min_confidence)

    rows = []
    for fw, lf, ratio, best, _ in results:
        if lf is None:
            continue
        trivial = lf.invariant < args.min_invariant
        if trivial and not args.keep_trivial:
            continue
        names = sorted({b.name for b in best})
        alias_names = sorted(set(sum((aliases.get(b.name, [b.name]) for b in best), [])))
        ambiguous = len(names) > 1
        confidence = ratio * (0.5 if ambiguous else 1.0)  # halve ambiguous ties
        rows.append({
            "fw_addr": f"0x{fw.entry:08x}",
            "fw_name": fw.name,
            "symbol": names[0] if len(names) == 1 else "|".join(names),
            "aliases": ";".join(a for a in alias_names if a not in names),
            "confidence": f"{confidence:.4f}",
            "raw_ratio": f"{ratio:.4f}",
            "invariant_bytes": lf.invariant,
            "masked_bytes": lf.length - lf.invariant,
            "sym_len": lf.length,
            "fw_len": fw.length,
            "lib_object": lf.obj,
            "flags": ",".join(f for f, on in
                              (("ambiguous", ambiguous), ("trivial", trivial)) if on),
        })

    rows.sort(key=lambda r: (-float(r["confidence"]), -int(r["invariant_bytes"])))
    fields = ["fw_addr", "fw_name", "symbol", "aliases", "confidence", "raw_ratio",
              "invariant_bytes", "masked_bytes", "sym_len", "fw_len", "lib_object",
              "flags"]
    if args.out:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    w = csv.DictWriter(sys.stdout, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    matched = len({r["fw_addr"] for r in rows})
    sys.stderr.write(
        f"reported {len(rows)} matches covering {matched}/{len(fws)} firmware functions "
        f"(min_confidence={args.min_confidence}, min_invariant={args.min_invariant})\n")


if __name__ == "__main__":
    main()
