"""
Parser for Card_Part & Card_Pidx
- get_pidx_table
- get_part_table
- write_part_file for updated part_table
"""
from pathlib import Path
from core.utils import write_json
from typing import List

def get_pidx_table(pidx_dec_path: Path):
    with open(pidx_dec_path, 'rb') as pidx_bytes:
        pidx = pidx_bytes.read()

    pidx_table = [None]*(len(pidx)//4)
    pidx_table[0] = (0,0,0) #First 4 bytes are just zero
    for i in range(4, len(pidx), 4):
        index_in_Card_Part_file = pidx[i+0] + pidx[i+1]*256 #Little-Endian
        main_effect_part_count, sub_n_pend_effect_part_count = divmod(pidx[i+3], 16)
        pidx_table[i//4] = (index_in_Card_Part_file, main_effect_part_count, sub_n_pend_effect_part_count)
    return pidx_table[1:]

def get_part_table(part_dec_path: Path, pidx_table):
    with open(part_dec_path, 'rb') as part_bytes:
        part = part_bytes.read()

    part_table = [[] for _ in range(len(pidx_table))]
    for i,(a,b,c) in enumerate(pidx_table):
        if a == b == c == 0: continue
        for j in range(a, a+b+c):
            k = 4*j
            part_table[i].append((part[k+0]+part[k+1]*256, part[k+2]+part[k+3]*256)) #inclusive bounds
    return part_table

def part_to_4_bytes(part):
    a,b = part
    return a.to_bytes(2, 'little') + b.to_bytes(2, 'little')

def write_part_file(part_file_path: Path, part_table):
    indices = [None for _ in part_table]
    with open(part_file_path, 'wb') as file:
        file.write(b'\x00\x00\x00\x00')
        index = 1
        for j,changed_part_arr in enumerate(part_table):
            indices[j] = index
            for part in changed_part_arr:
                file.write(part_to_4_bytes(part))
                index += 1
    return indices