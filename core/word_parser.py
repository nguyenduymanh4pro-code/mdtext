"""
Parser for WORD_Indx & WORD_Text to produce word table and write changed word files.
"""
from pathlib import Path
from core.utils import write_json, read_json
from typing import List

def get_widx_table(widx_dec_path: Path) -> List[int]:
    with open(widx_dec_path, 'rb') as widx_bytes:
        widx = widx_bytes.read()
    widx_table = [None]*(len(widx)//4)
    for i in range(0, len(widx), 4):
        widx_table[i//4] = int.from_bytes(widx[i:i+4], 'little')
    return widx_table

def get_word_table(widx_dec_path: Path, word_dec_path: Path) -> List[bytes]:
    widx = get_widx_table(widx_dec_path)
    with open(word_dec_path, 'rb') as word_bytes:
        word = word_bytes.read()
    word_table = [None]*(len(widx)-1)
    for j in range(len(widx)-1):
        a = widx[j]
        b = widx[j+1]
        word_table[j] = word[a:b]
    return word_table