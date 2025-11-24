from pathlib import Path
import UnityPy
import zlib
from core.decryptor import find_key_for_encrypted_bytes, decrypt_bytes
from core.utils import write_json
import logging

KNOWN = {"CARD_Indx","CARD_Name","CARD_Desc","WORD_Indx","WORD_Text","Card_Part","Card_Pidx","CardPictureFontSetting"}

log = logging.getLogger(__name__)

class AssetUnpacker:
    def __init__(self):
        pass

    def _process_env(self, env, dest: Path, logger=None, created=None):
        if created is None:
            created = []
        for cont_path, obj in env.container.items():
            try:
                data = obj.read()
            except Exception:
                continue
            name = getattr(data, "m_Name", None)
            if not name or name not in KNOWN:
                continue
            if obj.type.name == "TextAsset":
                b = data.m_Script.encode("utf-8", "surrogateescape")
                out = dest / f"{name}.bytes"
                out.write_bytes(b)
                created.append(str(out))
                if logger:
                    logger.log(f"Saved {out.name}")
            elif obj.type.name == "MonoBehaviour":
                try:
                    tree = data.read_typetree()
                    out = dest / f"{name}.json"
                    write_json(str(out), tree)
                    created.append(str(out))
                    if logger:
                        logger.log(f"Saved {out.name}")
                except Exception:
                    continue
        return created

    def _try_decode_all(self, dest: Path, logger=None, created=None):
        """
        Decode .bytes -> .bytes.dec for KNOWN assets.
        Strategy:
          - Reuse !CryptoKey.txt if present.
          - Else try to find key using CARD_Indx.bytes first (single pass).
          - Try zlib first (some assets are plain compressed).
          - If still fails for particular file, attempt per-file search (last resort).
        """
        if created is None:
            created = []
        keyfile = Path(__file__).parent / "!CryptoKey.txt"
        crypto_key = None
        if keyfile.exists():
            try:
                crypto_key = int(keyfile.read_text().strip(), 16)
                if logger:
                    logger.log(f"Using existing crypto key {hex(crypto_key)} from !CryptoKey.txt")
            except Exception:
                crypto_key = None

        if crypto_key is None:
            idx_enc = dest / "CARD_Indx.bytes"
            if idx_enc.exists():
                try:
                    if logger:
                        logger.log("Attempting to detect crypto key from CARD_Indx.bytes (single pass)...")
                    crypto_key = find_key_for_encrypted_bytes(idx_enc.read_bytes(), start=0, max_trials=1<<14)
                    keyfile.write_text(hex(crypto_key))
                    if logger:
                        logger.log(f"Detected crypto key {hex(crypto_key)} and stored to !CryptoKey.txt")
                except Exception:
                    crypto_key = None

        for name in KNOWN:
            bpath = dest / f"{name}.bytes"
            if not bpath.exists():
                continue
            try:
                b = bpath.read_bytes()
            except Exception:
                continue
            # try zlib (plain) first
            try:
                dec = zlib.decompress(b)
                dec_path = dest / f"{name}.bytes.dec"
                dec_path.write_bytes(dec)
                created.append(str(dec_path))
                if logger:
                    logger.log(f"Wrote decompressed {dec_path.name}")
                continue
            except zlib.error:
                pass
            # try with detected crypto_key
            if crypto_key is not None:
                try:
                    dec = decrypt_bytes(b, crypto_key)
                    dec_path = dest / f"{name}.bytes.dec"
                    dec_path.write_bytes(dec)
                    created.append(str(dec_path))
                    if logger:
                        logger.log(f"Decoded {name}.bytes using key {hex(crypto_key)}")
                    continue
                except Exception:
                    pass
            # last resort per-file search (expensive) - only when necessary
            try:
                if logger:
                    logger.log(f"Searching crypto key for {bpath.name} (this may take time)...")
                k = find_key_for_encrypted_bytes(b, start=0, max_trials=1<<14)
                dec = decrypt_bytes(b, k)
                dec_path = dest / f"{name}.bytes.dec"
                dec_path.write_bytes(dec)
                created.append(str(dec_path))
                keyfile.write_text(hex(k))
                crypto_key = k
                if logger:
                    logger.log(f"Found crypto key {hex(k)} from {bpath.name} and decoded file")
            except Exception:
                if logger:
                    logger.log(f"Could not decode {bpath.name}; left as raw .bytes")
        return created

    def unpack_from_paths(self, candidate_paths, dest_folder: str, progress_callback=None, logger=None):
        dest = Path(dest_folder)
        dest.mkdir(parents=True, exist_ok=True)
        created = []
        total = max(1, len(candidate_paths))
        for idx, path in enumerate(candidate_paths):
            try:
                p = Path(path)
                if not p.exists() or not p.is_file():
                    if logger:
                        logger.log(f"Skipped missing file: {path}")
                    if progress_callback:
                        progress_callback(int((idx+1)/total*100))
                    continue
                env = UnityPy.load(str(p))
                if not env:
                    if logger:
                        logger.log(f"UnityPy failed to load: {p}")
                    if progress_callback:
                        progress_callback(int((idx+1)/total*100))
                    continue
                self._process_env(env, dest, logger=logger, created=created)
            except Exception as e:
                if logger:
                    logger.log(f"Error processing {path}: {e}")
            finally:
                if progress_callback:
                    progress_callback(int((idx+1)/total*100))

        # decode all candidates (reuse key if found)
        self._try_decode_all(dest, logger=logger, created=created)
        return created

    def unpack_assets(self, path_0000: str, dest_folder: str, progress_callback=None, logger=None):
        dest = Path(dest_folder)
        dest.mkdir(parents=True, exist_ok=True)
        created = []
        files = list(Path(path_0000).rglob("*"))
        total = len(files) if files else 1
        count = 0
        for p in files:
            if not p.is_file():
                continue
            try:
                env = UnityPy.load(str(p))
            except Exception:
                count += 1
                if progress_callback:
                    progress_callback(int(count/total*100))
                continue
            try:
                self._process_env(env, dest, logger=logger, created=created)
            except Exception as e:
                if logger:
                    logger.log(f"Error processing {p}: {e}")
            count += 1
            if progress_callback:
                progress_callback(int(count/total*100))

        self._try_decode_all(dest, logger=logger, created=created)
        return created