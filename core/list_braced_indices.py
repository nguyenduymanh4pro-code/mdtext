#!/usr/bin/env python3
"""
List card indices that have parts (i.e. will get braces) in extracted folder.

Usage (from project root):
  python -m core.list_braced_indices output/extracted

Prints first N indices with parts and sample braced text.
"""
import sys
from pathlib import Path
import json

def main(argv):
    if len(argv) < 2:
        print("Usage: python -m core.list_braced_indices <extracted_folder>")
        return 2
    ef = Path(argv[1])
    braced_p = ef / "CARD_Desc.bytes.dec.braced.json"
    desc_json_p = ef / "CARD_Desc.bytes.dec.json"
    part_p = ef / "Card_Part.bytes.dec"
    pidx_p = ef / "Card_Pidx.bytes.dec"
    if not braced_p.exists() or not desc_json_p.exists() or not part_p.exists() or not pidx_p.exists():
        print("Required extracted files missing in", ef)
        return 2

    braced = json.loads(braced_p.read_text(encoding="utf-8"))
    descs = json.loads(desc_json_p.read_text(encoding="utf-8"))

    from core.part_parser import get_pidx_table, get_part_table
    pidx_table = get_pidx_table(pidx_p)
    part_table = get_part_table(part_p, pidx_table)

    indices = [i for i, parts in enumerate(part_table) if parts and len(parts) > 0]
    print("Total cards:", len(descs))
    print("Cards with parts:", len(indices))
    N = 30
    print(f"First {min(N, len(indices))} indices with parts:")
    for i in indices[:N]:
        print(f"  {i}  parts={len(part_table[i])}  sample_braced_snippet='{braced[i][:120].replace(chr(10),'\\n')}'")
    if len(indices) > N:
        print(f"... more (total {len(indices)})")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))