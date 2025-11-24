"""
Simple word table parser for WORD_Text + WORD_Indx pair.

This module loads WORD_Indx.dec (4-byte LE indices) and WORD_Text.dec and creates a word table list.
It also supports writing modified word table back to binary with padding to 4 bytes.
"""
from pathlib import Path
from typing import List

def load_widx_table(widx_path: Path) -> List[int]:
    b = widx_path.read_bytes()
    ints = []
    for i in range(0, len(b), 4):
        ints.append(int.from_bytes(b[i:i+4], "little"))
    return ints

def load_word_table(widx_path: Path, word_path: Path):
    widx = load_widx_table(widx_path)
    data = word_path.read_bytes()
    words = []
    for i in range(len(widx) - 1):
        a = widx[i]
        b = widx[i + 1]
        words.append(data[a:b])
    return words

def nul_pad(b: bytes):
    while len(b) % 4 != 0:
        b += b"\x00"
    return b

def write_word_table(words: List[bytes], out_word_path: Path, out_widx_path: Path):
    widx = [0]
    buf = bytearray()
    for w in words:
        buf.extend(w)
        widx.append(widx[-1] + len(w))
    out_word_path.write_bytes(bytes(buf))
    # write widx as 4byte LE
    idx_buf = bytearray()
    for i in widx:
        idx_buf.extend(i.to_bytes(4, "little"))
    out_widx_path.write_bytes(bytes(idx_buf))