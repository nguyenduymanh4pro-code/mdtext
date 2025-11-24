#!/usr/bin/env python3
"""
Debug script: check braced JSON, part table, and show sample entries.

Usage:
    python core/debug_braced.py <path_to_extracted_folder>
Example:
    python core/debug_braced.py output/extracted
"""
import sys
from pathlib import Path
import json

def main(p):
    ef = Path(p)
    if not ef.exists():
        print("Path not found:", ef)
        return 2

    braced = ef / "CARD_Desc.bytes.dec.braced.json"
    desc_json = ef / "CARD_Desc.bytes.dec.json"
    part = ef / "Card_Part.bytes.dec"
    pidx = ef / "Card_Pidx.bytes.dec"
    print("Extracted folder:", ef.resolve())
    print("Exists CARD_Desc.bytes.dec.braced.json:", braced.exists())
    print("Exists CARD_Desc.bytes.dec.json:", desc_json.exists())
    print("Exists Card_Part.bytes.dec:", part.exists())
    print("Exists Card_Pidx.bytes.dec:", pidx.exists())

    if braced.exists():
        try:
            b = json.loads(braced.read_text(encoding="utf-8"))
            print("Braced entries:", len(b))
            print("Sample braced[0]:")
            print(b[0][:400])
        except Exception as e:
            print("Failed to load braced json:", e)

    # If part/pidx exist, try to parse part counts
    if part.exists() and pidx.exists():
        try:
            from core.part_parser import get_pidx_table, get_part_table
            pidx_table = get_pidx_table(pidx)
            part_table = get_part_table(part, pidx_table)
            counts = [len(x) for x in part_table]
            tot_nonzero = sum(1 for c in counts if c>0)
            print("Total cards with >0 parts:", tot_nonzero, "/", len(counts))
            # print first 10 counts
            print("First 20 part counts:", counts[:20])
            # show first card parts if any
            for i in range(min(5, len(part_table))):
                print(f"Card {i} parts:", part_table[i][:10])
        except Exception as e:
            print("Failed to parse part/pidx:", e)
    else:
        print("Skipping part table parse since part/pidx missing.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python core/debug_braced.py <extracted_folder>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))