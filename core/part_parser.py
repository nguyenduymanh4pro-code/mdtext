"""
Parse Card_Pidx.bytes.dec and Card_Part.bytes.dec into Python structures and provide
helpers for brace indices similar to community tool.

Functions:
- get_pidx_table(pidx_dec_path)
- get_part_table(part_dec_path, pidx_table)
- unbraced_brace_indices(text)  (to compute indices of sub-effects)
"""
from pathlib import Path

nul = b'\x00'

def get_pidx_table(pidx_dec_path: Path):
    pidx = pidx_dec_path.read_bytes()
    pidx_table = [None] * (len(pidx) // 4)
    pidx_table[0] = (0, 0, 0)
    for i in range(4, len(pidx), 4):
        index_in_Card_Part_file = pidx[i] + pidx[i+1] * 256
        main_effect_part_count, sub_n_pend_effect_part_count = divmod(pidx[i+3], 16)
        pidx_table[i // 4] = (index_in_Card_Part_file, main_effect_part_count, sub_n_pend_effect_part_count)
    return pidx_table[1:]

def get_part_table(part_dec_path: Path, pidx_table):
    part = part_dec_path.read_bytes()
    part_table = [[] for _ in range(len(pidx_table))]
    for i, (a, b, c) in enumerate(pidx_table):
        if a == b == c == 0:
            continue
        for j in range(a, a + b + c):
            k = 4 * j
            lo = part[k + 0] + part[k + 1] * 256
            hi = part[k + 2] + part[k + 3] * 256
            part_table[i].append((lo, hi))
    return part_table

def unbraced_brace_indices(in_str: str):
    """
    For a string WITHOUT braces return list mapping each unbraced char
    to positions of braces as in the original community tool.
    Implementation replicates logic used in common_defs.unbraced_brace_indices.
    """
    ans = []
    j = -1
    b = in_str.encode()
    for i, c in enumerate(b):
        is_L = c == 123
        is_R = c == 125
        if is_L:
            ans.append(-1)
        elif is_R:
            ans.append(j)
        else:
            j += 1
            for k in range(len(ans) - 1, -1, -1):
                if ans[k] != -1:
                    break
                ans[k] = j
    return ans