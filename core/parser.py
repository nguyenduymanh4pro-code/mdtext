from pathlib import Path
from core.utils import write_json
from typing import List
import json

class CardModule:
    """
    Parse CARD_Indx / CARD_Name / CARD_Desc and optionally load braced json.
    """
    def __init__(self):
        self.names: List[str] = []
        self.descs: List[str] = []
        self.braced_descs: List[str] = []
        self.effect_counts: List[int] = []
        self.indx_bytes = b""

    def _bytes_to_int_list(self, path: Path):
        with path.open("rb") as f:
            data = f.read()
        return list(data)

    def _progressive_processing(self, card_indx_path: Path, target_path: Path, start: int):
        arr = self._bytes_to_int_list(card_indx_path)
        idxs = []
        # every 8 bytes block contains two 4-byte little-endian ints; start selects name(0) or desc(4)
        for i in range(start, len(arr), 8):
            chunk = bytes(arr[i:i+4])
            if len(chunk) < 4:
                break
            num = int.from_bytes(chunk, 'little')
            idxs.append(num)
        # drop header index
        if len(idxs) > 0:
            idxs = idxs[1:]
        data = target_path.read_bytes()
        res = []
        for i in range(len(idxs) - 1):
            a = idxs[i]; b = idxs[i+1]
            if a < 0 or b <= a or b > len(data):
                # guard — keep alignment with empty string if indices look bad
                res.append("")
                continue
            s = data[a:b]
            try:
                txt = s.decode("utf-8")
            except Exception:
                txt = s.decode("utf-8", errors="replace")
            txt = txt.rstrip("\x00")
            res.append(txt)
        return res

    def load_from_folder(self, extracted_folder: Path):
        ef = Path(extracted_folder)
        card_indx = ef / "CARD_Indx.bytes.dec"
        card_name = ef / "CARD_Name.bytes.dec"
        card_desc = ef / "CARD_Desc.bytes.dec"
        jn = ef / "CARD_Name.bytes.dec.json"
        jd = ef / "CARD_Desc.bytes.dec.json"
        braced_j = ef / "CARD_Desc.bytes.dec.braced.json"

        # Support pre-split JSON case (sample)
        if jn.exists() and jd.exists() and (not (card_indx.exists() and card_name.exists() and card_desc.exists())):
            self.names = json.loads(jn.read_text(encoding="utf-8"))
            self.descs = json.loads(jd.read_text(encoding="utf-8"))

            # Load braced JSON if available. We want the GUI to show escaped quotes (\"Name\")
            # while keeping the original (unescaped) braced strings for counting effects.
            if braced_j.exists():
                try:
                    braced_raw = json.loads(braced_j.read_text(encoding="utf-8"))
                    # effect_counts must be computed from the real braced data (without added backslashes)
                    from core.brace_utils import count_top_level_braces
                    self.effect_counts = [count_top_level_braces(s) for s in braced_raw]
                    # create display-safe version where internal double-quotes are escaped
                    self.braced_descs = [s.replace('"', '\\"') for s in braced_raw]
                except Exception:
                    # fallback: if parsing fails, use descs and zero effects
                    self.braced_descs = [d for d in self.descs]
                    self.effect_counts = [0 for _ in self.descs]
            else:
                self.braced_descs = [d for d in self.descs]
                self.effect_counts = [0 for _ in self.descs]
            return

        if not (card_indx.exists() and card_name.exists() and card_desc.exists()):
            raise FileNotFoundError("Missing CARD_Indx.bytes.dec or CARD_Name.bytes.dec or CARD_Desc.bytes.dec")

        self.indx_bytes = card_indx.read_bytes()
        self.names = self._progressive_processing(card_indx, card_name, 0)
        self.descs = self._progressive_processing(card_indx, card_desc, 4)

        # write canonical jsons (used by Encryptor)
        write_json(str(ef / "CARD_Name.bytes.dec.json"), self.names)
        write_json(str(ef / "CARD_Desc.bytes.dec.json"), self.descs)

        # load braced if exists and compute effect_counts
        if braced_j.exists():
            try:
                braced_raw = json.loads(braced_j.read_text(encoding="utf-8"))
                from core.brace_utils import count_top_level_braces
                # compute counts from real braced strings
                self.effect_counts = [count_top_level_braces(s) for s in braced_raw]
                # display version escapes double-quotes so GUI shows \"Name\" explicitly
                self.braced_descs = [s.replace('"', '\\"') for s in braced_raw]
            except Exception:
                # fallback
                self.braced_descs = [d for d in self.descs]
                self.effect_counts = [0 for _ in self.descs]
        else:
            self.braced_descs = [d for d in self.descs]
            self.effect_counts = [0 for _ in self.descs]

    def write_changed(self, changed_folder: Path):
        changed_folder.mkdir(parents=True, exist_ok=True)
        write_json(str(changed_folder / "CARD_Name.bytes.dec.json"), self.names)
        write_json(str(changed_folder / "CARD_Desc.bytes.dec.json"), self.descs)