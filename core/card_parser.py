"""core/card_parser.py
Helpers for card name/desc loading, producing braced descriptions from part tables,
saving changed braced/unbraced JSONs and producing changed Card_Part bytes
(similar logic to the community tool's step_3 routines).
"""
from pathlib import Path
from typing import List
import json
from core import part_parser, utils

nul = b'\x00'

def load_names(path: Path) -> List[str]:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_descs(path: Path) -> List[str]:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# --- Braces utilities (port of common_defs.insert_braces / unbraced logic) ---
def string_insert(orig_bytes: bytes, insert_bytes: bytes, index: int) -> bytes:
    return orig_bytes[:index] + insert_bytes + orig_bytes[index:]

def insert_braces(effect_text: str, parts_arr: List[tuple]) -> str:
    # filter invalid
    parts_arr = [(a, b) for (a, b) in parts_arr if a < b]

    L, R = '{', '}'
    insertion_dict = {}
    for (a, b) in parts_arr:
        if a not in insertion_dict:
            insertion_dict[a] = {L: 0, R: 0}
        if (b + 1) not in insertion_dict:
            insertion_dict[b + 1] = {L: 0, R: 0}
        insertion_dict[a][L] += 1
        insertion_dict[b + 1][R] += 1

    ans = effect_text.encode()
    indices_list = sorted(list(insertion_dict.keys()), reverse=True)
    for index in indices_list:
        inserted_braces = insertion_dict[index][R] * b'}' + insertion_dict[index][L] * b'{'
        ans = string_insert(ans, inserted_braces, index)
    return ans.decode()

# Build braced descriptions from unbraced descs + part table
def build_braced_descs(descs: List[str], pidx_dec_path: Path, part_dec_path: Path) -> List[str]:
    # load pidx and part table via part_parser
    pidx_table = part_parser.get_pidx_table(Path(pidx_dec_path))
    part_table = part_parser.get_part_table(Path(part_dec_path), pidx_table)
    braced = []
    for i in range(len(descs)):
        part_arr = part_table[i] if i < len(part_table) else []
        braced.append(insert_braces(descs[i], part_arr))
    return braced

# Save braced changed file into changed folder (mimic community naming)
def save_changed_braced(changed_folder: Path, braced_descs: List[str]):
    changed_folder.mkdir(parents=True, exist_ok=True)
    out = Path(changed_folder) / "!Changed !Braced CARD_Desc.bytes.dec.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(braced_descs, f, ensure_ascii=False, indent=2)
    return out

def make_unbraced_from_braced(braced_descs: List[str]) -> List[str]:
    return [s.replace('{', '').replace('}', '') for s in braced_descs]

def save_unbraced_changed(changed_folder: Path, unbraced_descs: List[str]):
    changed_folder.mkdir(parents=True, exist_ok=True)
    out = Path(changed_folder) / "!Unbraced !Changed CARD_Desc.bytes.dec.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(unbraced_descs, f, ensure_ascii=False, indent=2)
    return out

# --- PART table adjustment (port of step_3 logic) ---
def concated_pairs(pairs_list: List[tuple]) -> List[int]:
    ans = []
    for a, b in pairs_list:
        if a == b:
            continue
        ans.extend([a, b])
    ans.sort()
    return ans

def get_diff(arr_old: List[int], arr_new: List[int]):
    if arr_old == arr_new:
        return None
    # create differences; align lengths
    L = max(len(arr_old), len(arr_new))
    dif = []
    for i in range(L):
        a = arr_old[i] if i < len(arr_old) else 0
        b = arr_new[i] if i < len(arr_new) else 0
        dif.append(a - b)
    return dif

def make_map(i: int, part_table: List[List[tuple]], braced_descs: List[str], changed_braced_descs: List[str]):
    unbraced_arr = concated_pairs(part_table[i])
    braced_arr = part_parser.unbraced_brace_indices(braced_descs[i])
    arr_dif = None
    try:
        arr_dif = get_diff(unbraced_arr, braced_arr)
    except Exception:
        arr_dif = None
    changed_braced_arr = part_parser.unbraced_brace_indices(changed_braced_descs[i])
    ans = {}
    if arr_dif:
        for j in range(max(len(arr_dif), len(changed_braced_arr))):
            if j < len(changed_braced_arr):
                changed_braced_arr[j] += arr_dif[j] if j < len(arr_dif) else 0
    for j in range(max(len(unbraced_arr), len(changed_braced_arr))):
        a = unbraced_arr[j] if j < len(unbraced_arr) else 0
        b = changed_braced_arr[j] if j < len(changed_braced_arr) else 0
        ans[a] = b
    return ans

def apply_map(part_arr: List[tuple], part_map: dict):
    ans = []
    f = part_map
    for (a, b) in part_arr:
        if a >= b:
            ans.append((a, b))
            continue
        if a in f and b in f:
            ans.append((f[a], f[b]))
        else:
            ans.append((a, b))
    return ans

def adjust_part_table(part_table: List[List[tuple]], braced_descs: List[str], changed_braced_descs: List[str]) -> List[List[tuple]]:
    new_table = [list(arr) for arr in part_table]
    for i in range(len(part_table)):
        part_map = make_map(i, part_table, braced_descs, changed_braced_descs)
        new_table[i] = apply_map(part_table[i], part_map)
    return new_table

def write_part_file(part_file_path: Path, part_table: List[List[tuple]]):
    part_file_path.parent.mkdir(parents=True, exist_ok=True)
    indices = [None for _ in part_table]
    with open(part_file_path, "wb") as f:
        f.write(4 * nul)
        index = 1
        for j, changed_part_arr in enumerate(part_table):
            indices[j] = index
            for part in changed_part_arr:
                a, b = part
                f.write(a.to_bytes(2, "little"))
                f.write(b.to_bytes(2, "little"))
                index += 1
    return indices

def make_changed_part_file(changed_part_path: Path, pidx_dec_path: Path, part_dec_path: Path, braced_descs: List[str], changed_braced_descs: List[str]):
    pidx_table = part_parser.get_pidx_table(Path(pidx_dec_path))
    part_table = part_parser.get_part_table(Path(part_dec_path), pidx_table)
    adjusted = adjust_part_table(part_table, braced_descs, changed_braced_descs)
    write_part_file(Path(changed_part_path), adjusted)
    return Path(changed_part_path)
