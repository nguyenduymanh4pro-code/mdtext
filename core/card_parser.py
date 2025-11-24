"""
CARD_* parsing and merging helpers.

Provides:
- load_names(path_to_CARD_Name.bytes.dec.json) -> list[str]
- load_descs(path_to_CARD_Desc.bytes.dec.json) -> list[str]
- build_and_encrypt(...) -> merges names+descs into bytes and encrypts them using decryptor key/algorithm
"""
from pathlib import Path
import json
from core import decryptor
from typing import Union
import struct
import os

def load_names(path: Union[str, Path]):
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        arr = json.load(f)
    return arr

def load_descs(path: Union[str, Path]):
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        arr = json.load(f)
    return arr

def get_string_len_utf8(s: str):
    return len(s.encode("utf-8"))

def _pack_index_list(ints):
    # Write little-endian 4-byte values for each int
    b = bytearray()
    for v in ints:
        b.extend((v & 0xFF).to_bytes(1, "little"))
        b.extend(((v >> 8) & 0xFF).to_bytes(1, "little"))
        b.extend(((v >> 16) & 0xFF).to_bytes(1, "little"))
        b.extend(((v >> 24) & 0xFF).to_bytes(1, "little"))
    return bytes(b)

def build_and_encrypt(CARD_Name_json: Path, CARD_Desc_json: Path, CARD_Indx_template: Path, out_folder: Path, logger=print):
    """
    Merge name/desc JSONs back to the binary format and encrypt them using the same crypto key
    as the existing CARD_Indx_template (if a key exists; otherwise tries brute-forcing from template).
    The CARD_Indx_template is used to get index structure and the !CryptoKey.txt if present.
    """
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    names = load_names(CARD_Name_json)
    descs = load_descs(CARD_Desc_json)

    # Build merged strings with 8 NUL bytes prefix (community tool used \x00*8 start)
    name_merge = "\x00" * 8
    desc_merge = "\x00" * 8
    name_indx = [0]
    desc_indx = [0]

    def helper(sentence, indx_list, merge_buf):
        length = get_string_len_utf8(sentence)
        if len(indx_list) == 1:
            length += 8
        space_len = (4 - (length % 4)) % 4
        indx_list.append(indx_list[-1] + length + space_len)
        return sentence + ("\x00" * space_len)

    for i in range(max(len(names), len(descs))):
        n = names[i] if i < len(names) else ""
        d = descs[i] if i < len(descs) else ""
        name_merge += helper(n, name_indx, name_merge)
        desc_merge += helper(d, desc_indx, desc_merge)

    # prefix indexes as community script did
    name_indx = [4, 8] + name_indx[1:]
    desc_indx = [4, 8] + desc_indx[1:]

    # Compose card_indx interleaved
    card_indx = []
    for a, b in zip(name_indx, desc_indx):
        card_indx.append(a)
        card_indx.append(b)

    # Build binary representation
    # card_indx becomes list of little-endian 4-bytes numbers
    indx_binary = bytearray()
    for num in card_indx:
        indx_binary.extend(int.to_bytes(num, 4, "little"))

    # Now find crypto key: check template folder for !CryptoKey.txt
    template_folder = CARD_Indx_template.parent
    key = decryptor.get_crypto_key_from_file(template_folder)
    if key is None:
        # try brute forcing using template file if provided
        try:
            key = decryptor.find_crypto_key_for_file(CARD_Indx_template)
        except Exception:
            key = 0

    # Encrypt payloads
    name_bytes = name_merge.encode("utf-8")
    desc_bytes = desc_merge.encode("utf-8")
    card_indx_bytes = bytes(indx_binary)

    enc_name = decryptor.encrypt_bytes(name_bytes, key)
    enc_desc = decryptor.encrypt_bytes(desc_bytes, key)
    enc_indx = decryptor.encrypt_bytes(card_indx_bytes, key)

    # Write to out_folder with same names (these are .bytes files ready to be placed into the bundle)
    (out_folder / "CARD_Name.bytes").write_bytes(enc_name)
    (out_folder / "CARD_Desc.bytes").write_bytes(enc_desc)
    (out_folder / "CARD_Indx.bytes").write_bytes(enc_indx)

    logger(f"Wrote encrypted CARD_Name.bytes, CARD_Desc.bytes, CARD_Indx.bytes to {out_folder}")