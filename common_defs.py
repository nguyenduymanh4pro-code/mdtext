"""
Lightweight compatibility shim `common_defs.py` for this project.

Your environment contained an unrelated external tool that also defines a
common_defs.py. The GUI and some helper code in this project import
`common_defs`. To avoid depending on the other tool, this file provides a
minimal, safe set of paths and helper functions used by this project's code.

Place this file at the project root (next to main.py) so `import common_defs`
succeeds.
"""
from pathlib import Path
import os
import shutil
import json

# Basic helpers -------------------------------------------------------------
def script_folder() -> str:
    return str(Path(__file__).resolve().parent)

def copy_and_replace(source_path, destination_path):
    src = Path(source_path)
    dst = Path(destination_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    shutil.copy2(src, dst)

def file_walker(source_folder):
    """Yield file paths (strings) under source_folder recursively."""
    source_folder = Path(source_folder)
    for p in source_folder.rglob("*"):
        if p.is_file():
            yield str(p)

def WriteJSON(obj, json_file_path: str):
    Path(json_file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=4)

def get_and_prime_json(file_path: str):
    with open(file_path, encoding='utf-8') as f:
        arr = json.load(f)
    return arr

# Project paths (used by GUI and helper scripts)
ROOT = Path(script_folder())

# These folder names are chosen to be unobtrusive and specific to this tool.
# They will be created automatically when needed.
copied_files_folder = str(ROOT / "1_copied_game_files")
decrypt_folder      = str(ROOT / "2_decrypted_assets")
changed_folder      = str(ROOT / "3_changed_assets")
modded_folder       = str(ROOT / "4_modded_files")
output_folder       = str(ROOT / "output")          # general output (GUI also uses output/)
assets_folder       = str(ROOT / "assets")
scripts_folder      = str(ROOT / "utils")           # kept for compatibility

# Additional likely-used decrypted/changed filenames (string paths)
part_dec_path   = str(Path(decrypt_folder) / "Card_Part.bytes.dec")
pidx_dec_path   = str(Path(decrypt_folder) / "Card_Pidx.bytes.dec")
prop_dec_path   = str(Path(decrypt_folder) / "CARD_Prop.bytes.dec")
word_dec_path   = str(Path(decrypt_folder) / "WORD_Text.bytes.dec")
widx_dec_path   = str(Path(decrypt_folder) / "WORD_Indx.bytes.dec")
font_asset_path = str(Path(decrypt_folder) / "CardPictureFontSetting.json")

name_dec_path    = str(Path(decrypt_folder) / "CARD_Name.bytes.dec.json")
desc_dec_path    = str(Path(decrypt_folder) / "CARD_Desc.bytes.dec.json")
braced_save_path = str(Path(decrypt_folder) / "!Braced CARD_Desc.bytes.dec.json")

changed_braced_path   = str(Path(changed_folder) / "!Changed !Braced CARD_Desc.bytes.dec.json")
unbraced_changed_path = str(Path(changed_folder) / "!Unbraced !Changed CARD_Desc.bytes.dec.json")
changed_part_path     = str(Path(changed_folder) / "!Changed Card_Part.bytes.dec")
changed_font_path     = str(Path(changed_folder) / "!Changed CardPictureFontSetting.json")
changed_word_path     = str(Path(changed_folder) / "!Changed WORD_Text.bytes.dec")
changed_widx_path     = str(Path(changed_folder) / "!Changed WORD_Indx.bytes.dec")

# Ensure directories exist for code that expects them
for p in (copied_files_folder, decrypt_folder, changed_folder, modded_folder, output_folder, assets_folder, scripts_folder):
    try:
        Path(p).mkdir(parents=True, exist_ok=True)
    except Exception:
        # best-effort; ignore permissions errors here
        pass