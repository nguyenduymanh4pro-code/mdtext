"""
Unpacks Unity asset files using UnityPy.

For each Unity asset file:
 - For TextAsset objects: saves .bytes with the asset's m_Name (raw bytes).
 - For MonoBehaviour objects with a typetree: dumps JSON of typetree as <m_Name>.json.

Outputs are placed into an output directory.
"""
from pathlib import Path
import UnityPy
import json
from core.decryptor import try_decrypt_with_key, find_crypto_key_for_file, get_crypto_key_from_file
import os

def unpack_single_asset(asset_path: Path, output_folder: Path, logger=print):
    """
    Load a single Unity asset file and extract TextAsset and MonoBehaviour objects.
    """
    output_folder.mkdir(parents=True, exist_ok=True)
    env = UnityPy.load(str(asset_path))
    for obj in env.objects:
        try:
            if obj.type.name == "TextAsset":
                data = obj.read()
                # m_Script is usually a str
                raw = data.m_Script
                # When UnityPy returns str, encode with surrogateescape to preserve bytes
                if isinstance(raw, str):
                    out_path = output_folder / f"{data.m_Name}.bytes"
                    with open(out_path, "wb") as f:
                        f.write(raw.encode("utf-8", "surrogateescape"))
                else:
                    out_path = output_folder / f"{data.m_Name}.bytes"
                    with open(out_path, "wb") as f:
                        f.write(bytes(raw))
            elif obj.type.name == "MonoBehaviour":
                # write typetree json if available
                if not obj.serialized_type.node:
                    continue
                tree = obj.read_typetree()
                out_path = output_folder / f"{tree['m_Name']}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(tree, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger(f"Skipping object {obj} due to error: {e}")

    # After extracting TextAsset/MonoBehaviour raw files, try to decrypt any .bytes that are compressed/encrypted:
    for p in output_folder.glob("*.bytes"):
        with open(p, "rb") as f:
            raw = f.read()
        # First try decompress directly (maybe it is compressed only)
        try:
            dec = try_decrypt_with_key(raw, 0)
            # If key==0 works, save .bytes.dec
            out = p.with_suffix(p.suffix + ".dec")
            out.write_bytes(dec)
            logger(f"Wrote decompressed {out.name}")
            continue
        except Exception:
            pass
        # Next, if there's a crypto key file in the same folder (unlikely here), try it
        key = get_crypto_key_from_file(output_folder)
        if key is not None:
            try:
                dec = try_decrypt_with_key(raw, key)
                out = p.with_suffix(p.suffix + ".dec")
                out.write_bytes(dec)
                logger(f"Wrote decrypted {out.name} with key {hex(key)}")
                continue
            except Exception:
                pass
        # Last resort: try to find key by brute force for this file (may be slow)
        # We will only attempt for CARD_Indx and related large files
        if p.name.startswith("CARD_Indx") or p.name.startswith("CARD_Desc") or p.name.startswith("CARD_Name"):
            try:
                key = find_crypto_key_for_file(p)
                if key is not None:
                    dec = try_decrypt_with_key(raw, key)
                    out = p.with_suffix(p.suffix + ".dec")
                    out.write_bytes(dec)
                    logger(f"Brute-forced key {hex(key)} and wrote {out.name}")
            except Exception as e:
                logger(f"Failed to brute-force {p.name}: {e}")

    return