from pathlib import Path
import json
from typing import Tuple
from core.part_parser import get_pidx_table, get_part_table
from core.brace_utils import insert_braces

def build_braced(extracted_folder: str) -> Tuple[bool, str]:
    ef = Path(extracted_folder)
    desc_json = ef / "CARD_Desc.bytes.dec.json"
    desc_dec = ef / "CARD_Desc.bytes.dec"
    pidx_dec = ef / "Card_Pidx.bytes.dec"
    part_dec = ef / "Card_Part.bytes.dec"
    out_path = ef / "CARD_Desc.bytes.dec.braced.json"

    missing = []
    if not desc_json.exists() and not desc_dec.exists():
        missing.append("CARD_Desc.bytes.dec or CARD_Desc.bytes.dec.json")
    if not pidx_dec.exists():
        missing.append("Card_Pidx.bytes.dec")
    if not part_dec.exists():
        missing.append("Card_Part.bytes.dec")
    if missing:
        return False, "Missing files: " + ", ".join(missing)

    try:
        if desc_json.exists():
            descs = json.loads(desc_json.read_text(encoding="utf-8"))
        else:
            raw = desc_dec.read_bytes().decode("utf-8", errors="replace")
            descs = [s for s in raw.split("\x00\x00") if s]
    except Exception as e:
        return False, f"Failed to read descriptions: {e}"

    try:
        pidx_table = get_pidx_table(pidx_dec)
        part_table = get_part_table(part_dec, pidx_table)
    except Exception as e:
        return False, f"Failed to build part/pidx tables: {e}"

    braced = []
    for i, desc in enumerate(descs):
        parts = part_table[i] if i < len(part_table) else []
        try:
            braced_desc = insert_braces(desc, parts)
        except Exception:
            braced_desc = desc
        braced.append(braced_desc)

    try:
        out_path.write_text(json.dumps(braced, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        return False, f"Failed to write braced JSON: {e}"

    return True, f"Wrote braced JSON: {out_path}"