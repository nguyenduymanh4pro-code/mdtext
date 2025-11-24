"""
Merge + encrypt logic based on _CARD_merge+calc_index.py and _CARD_encrypt.py
- Rebuild merged name/desc strings and index array
- Write .bytes (encrypted) files using community crypto
"""
from pathlib import Path
from core.decryptor import encrypt_bytes, find_key_for_encrypted_bytes
from core.utils import write_json
import json

class Encryptor:
    def __init__(self):
        self.keyfile = Path(__file__).parent / "!CryptoKey.txt"
        self.key = None
        if self.keyfile.exists():
            try:
                self.key = int(self.keyfile.read_text().strip(), 16)
            except Exception:
                self.key = None

    def _get_utf8_len(self, s: str):
        return len(s.encode('utf-8'))

    def build_mod(self, extracted_folder: Path, changed_folder: Path, modded_folder: Path, logger=None, progress_callback=None):
        extracted = Path(extracted_folder)
        changed = Path(changed_folder)
        modded = Path(modded_folder)
        modded.mkdir(parents=True, exist_ok=True)

        # load JSONs preferring changed
        name_path = changed / "CARD_Name.bytes.dec.json" if (changed / "CARD_Name.bytes.dec.json").exists() else extracted / "CARD_Name.bytes.dec.json"
        desc_path = changed / "CARD_Desc.bytes.dec.json" if (changed / "CARD_Desc.bytes.dec.json").exists() else extracted / "CARD_Desc.bytes.dec.json"

        with name_path.open(encoding="utf-8") as f:
            names = json.load(f)
        with desc_path.open(encoding="utf-8") as f:
            descs = json.load(f)

        # Merge with padding to 4 bytes like community script
        name_merge = "\x00"*8
        desc_merge = "\x00"*8
        name_indx = [0]
        desc_indx = [0]
        for i in range(len(names)):
            nm = names[i]
            ds = descs[i]
            def helper(sentence, indx, merge_str):
                length = self._get_utf8_len(sentence)
                if i == 0:
                    length += 8
                space_len = (4 - length % 4) % 4
                indx.append(indx[-1] + length + space_len)
                return merge_str + sentence + ("\x00"*space_len)
            name_merge = helper(nm, name_indx, name_merge)
            desc_merge = helper(ds, desc_indx, desc_merge)
        name_indx = [4,8] + name_indx[1:]
        desc_indx = [4,8] + desc_indx[1:]
        card_indx = []
        for i in range(len(name_indx)):
            card_indx.append(name_indx[i]); card_indx.append(desc_indx[i])
        # int -> 4 little endian bytes
        def int_to_4bytes(n):
            return bytes([(n >> (8*i)) & 0xFF for i in range(4)])
        card_indx_merge = b"".join(int_to_4bytes(x) for x in card_indx)

        # write dec files to modded folder first
        (modded / "CARD_Name.bytes.dec").write_bytes(name_merge.encode("utf-8"))
        (modded / "CARD_Desc.bytes.dec").write_bytes(desc_merge.encode("utf-8"))
        (modded / "CARD_Indx.bytes.dec").write_bytes(card_indx_merge)

        # determine key: prefer existing key; else try find key using extracted CARD_Indx.bytes (raw encrypted file)
        if self.key is None:
            candidate = None
            ext_indx_enc = extracted / "CARD_Indx.bytes"
            if ext_indx_enc.exists():
                try:
                    k = find_key_for_encrypted_bytes(ext_indx_enc.read_bytes(), start=0, max_trials=1<<14)
                    self.key = k
                    if logger: logger.log(f"Detected crypto key {hex(k)}")
                    self.keyfile.write_text(hex(k))
                except Exception:
                    self.key = 0
            else:
                self.key = 0

        # encrypt .dec content to .bytes
        for name in ["CARD_Name","CARD_Desc","CARD_Indx"]:
            dec = (modded / f"{name}.bytes.dec").read_bytes()
            enc = encrypt_bytes(dec, self.key)
            (modded / f"{name}.bytes").write_bytes(enc)
            if logger: logger.log(f"Wrote encrypted {name}.bytes")

        # For other assets: copy over Card_Part, WORD_* from changed or extracted and encrypt if dec exists
        for other in ["Card_Part","WORD_Text","WORD_Indx"]:
            src = (changed / f"{other}.bytes.dec") if (changed / f"{other}.bytes.dec").exists() else (extracted / f"{other}.bytes.dec")
            if src and src.exists():
                dec = src.read_bytes()
                enc = encrypt_bytes(dec, self.key)
                (modded / f"{other}.bytes").write_bytes(enc)
                if logger: logger.log(f"Wrote encrypted {other}.bytes")
            else:
                # fallback: copy original .bytes if present
                orig = extracted / f"{other}.bytes"
                if orig.exists():
                    (modded / orig.name).write_bytes(orig.read_bytes())
        if progress_callback:
            progress_callback(100)
        if logger:
            logger.log("Encryption & build completed")