#!/usr/bin/env python3
"""
Inspect braced JSON, original descs and part table for debugging.

Usage (from project root):
  python -m core.inspect_braced output/extracted

This prints:
- whether braced JSON exists and its length
- whether CARD_Desc.bytes.dec.json exists and its length
- whether Card_Part.bytes.dec and Card_Pidx.bytes.dec exist
- for a few sample indices (0,1,10,100), prints:
    - original desc (truncated)
    - braced desc (truncated)
    - number of parts and sample part ranges
"""
import sys
from pathlib import Path
import json

def truncate(s, n=250):
    if s is None:
        return "<None>"
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + "…[truncated]"

def main(argv):
    if len(argv) < 2:
        print("Usage: python -m core.inspect_braced <extracted_folder>")
        return 2
    ef = Path(argv[1])
    if not ef.exists():
        print("Path not found:", ef)
        return 2

    braced_p = ef / "CARD_Desc.bytes.dec.braced.json"
    desc_json_p = ef / "CARD_Desc.bytes.dec.json"
    part_p = ef / "Card_Part.bytes.dec"
    pidx_p = ef / "Card_Pidx.bytes.dec"

    print("Extracted folder:", ef.resolve())
    print("braced json exists:", braced_p.exists())
    print("desc json exists:", desc_json_p.exists())
    print("Card_Part.bytes.dec exists:", part_p.exists())
    print("Card_Pidx.bytes.dec exists:", pidx_p.exists())

    braced = []
    descs = []
    try:
        if braced_p.exists():
            braced = json.loads(braced_p.read_text(encoding="utf-8"))
            print("Braced entries:", len(braced))
        else:
            print("No braced JSON found.")
    except Exception as e:
        print("Failed to read braced JSON:", e)

    try:
        if desc_json_p.exists():
            descs = json.loads(desc_json_p.read_text(encoding="utf-8"))
            print("Desc json entries:", len(descs))
        else:
            print("No desc json found.")
    except Exception as e:
        print("Failed to read desc json:", e)

    # Try parse part/pidx if present
    part_table = None
    if part_p.exists() and pidx_p.exists():
        try:
            from core.part_parser import get_pidx_table, get_part_table
            pidx_table = get_pidx_table(pidx_p)
            part_table = get_part_table(part_p, pidx_table)
            print("Parsed part_table: cards =", len(part_table))
            counts = [len(x) for x in part_table]
            nonzero = sum(1 for c in counts if c>0)
            print("Cards with >0 parts:", nonzero, "/", len(counts))
            print("First 30 part counts:", counts[:30])
        except Exception as e:
            print("Failed to parse part/pidx (import or parse error):", e)
    else:
        print("Skipping part_table parse (missing files).")

    # Show samples
    sample_ids = [0, 1, 10, 100, 500, 1000]
    maxid = max(len(descs), len(braced)) - 1
    print("Max index available (desc/braced):", maxid)
    for idx in sample_ids:
        if idx > maxid:
            continue
        d = descs[idx] if idx < len(descs) else "<missing>"
        b = braced[idx] if idx < len(braced) else "<missing>"
        parts = part_table[idx] if part_table and idx < len(part_table) else []
        print(f"\n--- Card {idx} ---")
        print("orig desc:", truncate(d, 400))
        print("braced  :", truncate(b, 400))
        print("parts count:", len(parts))
        if parts:
            print("first parts (up to 10):", parts[:10])
            # show byte ranges and a small slice of desc bytes if possible
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))