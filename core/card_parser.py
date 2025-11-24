"""
Parse CARD_Indx, CARD_Name, CARD_Desc extracted files into Python lists and JSON.
Implements logic similar to _CARD_decrypt_Desc+Indx+Name_and_split_Desc+Name.py
- ProgressiveProcessing to split CARD_Name & CARD_Desc by indices in CARD_Indx
- Provide read/write changed jsons for the GUI
"""
from pathlib import Path
from core.utils import write_json, read_json
from typing import List
import os

class CardParser:
    def __init__(self):
        self.names: List[str] = []
        self.descs: List[str] = []
        self.indx = []

    def FourToOne(self, x: List[int]) -> int:
        res = 0
        for i in range(3, -1, -1):
            res *= 16 * 16
            res += x[i]
        return res

    def _read_bytes_dec_to_int_list(self, path):
        with open(path, "rb") as f:
            hex_str_list = ("{:02X}".format(int(c)) for c in f.read())
        dec_list = [int(s, 16) for s in hex_str_list]
        return dec_list

    def progressive_processing(self, card_indx_dec_path: Path, filename: Path, start: int):
        dec_list = self._read_bytes_dec_to_int_list(card_indx_dec_path)
        indx = []
        for i in range(start, len(dec_list), 8):
            tmp = []
            for j in range(4):
                tmp.append(dec_list[i + j])
            indx.append(tmp)
        indx = [self.FourToOne(i) for i in indx]
        indx = indx[1:]
        # Read target file .bytes.dec
        with open(f"{filename}", "rb") as f:
            data = f.read()
        def Solve(data_bytes: bytes, desc_indx: List[int]):
            res = []
            for i in range(len(desc_indx) - 1):
                s = data_bytes[desc_indx[i]:desc_indx[i + 1]]
                s = s.decode('utf-8', errors='replace')
                while len(s) > 0 and s[-1] == '\u0000':
                    s = s[:-1]
                res.append(s)
            return res
        return Solve(data, indx)

    def load_from_folder(self, extracted_folder: Path):
        ef = Path(extracted_folder)
        card_indx = ef / "CARD_Indx.bytes.dec"
        card_name = ef / "CARD_Name.bytes.dec"
        card_desc = ef / "CARD_Desc.bytes.dec"
        if not card_indx.exists() or not card_name.exists() or not card_desc.exists():
            raise FileNotFoundError("CARD_Indx.bytes.dec, CARD_Name.bytes.dec or CARD_Desc.bytes.dec missing in extracted folder")
        self.names = self.progressive_processing(card_indx, card_name, 0)
        self.descs = self.progressive_processing(card_indx, card_desc, 4)
        # write canonical jsons
        write_json(str(ef / "CARD_Name.bytes.dec.json"), self.names)
        write_json(str(ef / "CARD_Desc.bytes.dec.json"), self.descs)
        # keep copy for edit save
        self.indx = card_indx.read_bytes()
        return

    def write_changed(self, changed_folder: Path):
        ensure_dir = Path(changed_folder)
        ensure_dir.mkdir(parents=True, exist_ok=True)
        write_json(str(ensure_dir / "CARD_Name.bytes.dec.json"), self.names)
        write_json(str(ensure_dir / "CARD_Desc.bytes.dec.json"), self.descs)