"""
Fast asset finder for Master Duel 0000 folder.

This module implements a faster search strategy than per-target scanning:
- First attempts direct lookup by known asset hex id under 0000/<xx>/<hexid>
- Then performs a single-pass scan of all files (not per-target) and loads each Unity file once,
  checking all contained objects for any of the requested m_Name values.
This minimizes repeated UnityPy loads and is significantly faster on large 0000 folders.

Usage:
    finder = AssetFinder()
    targets = [
        ("CARD_Desc", "21ae1efa"),
        ("CARD_Indx", "507764bc"),
        ("CARD_Name", "7438cca8"),
        ("Card_Part", "52739c94"),
        ("Card_Pidx", "494e34d0"),
        ("CARD_Prop", "85757744"),
        ("WORD_Text", "f5361426"),
        ("WORD_Indx", "b4d165f3"),
        ("CardPictureFontSetting", "fcd008c9"),
    ]
    results = finder.find_many(path_0000, targets)
    # results is a list in same order as targets; each item is dict:
    # {"name": m_name, "id": hexid, "path": path_or_None, "size": size_int_or_0, "container": container_name_or_None}
"""
from typing import List, Tuple, Dict, Optional
from pathlib import Path
import os
import UnityPy
import traceback

class AssetFinder:
    def __init__(self):
        pass

    def _try_open_env(self, file_path: Path):
        try:
            return UnityPy.load(str(file_path))
        except Exception:
            return None

    def _check_env_for_targets(self, env, wanted_names: set) -> List[Dict]:
        """
        Inspect UnityPy env.container items and return list of matches:
        [{'m_Name': ..., 'container': container_path}, ...]
        """
        found = []
        try:
            # iterate container mapping (gives container path and object)
            for cont_path, obj in env.container.items():
                try:
                    data = obj.read()
                except Exception:
                    # fallback: try obj.read_typetree() if read() fails for some MonoBehaviours
                    try:
                        data = obj.read_typetree()
                    except Exception:
                        continue
                m_name = getattr(data, "m_Name", None)
                if m_name and m_name in wanted_names:
                    found.append({"m_Name": m_name, "container": cont_path})
        except Exception:
            # if anything unexpected happens, ignore env
            pass
        return found

    def _direct_lookup_candidates(self, path_0000: Path, hexid: str) -> List[Path]:
        """
        Return candidate filesystem paths to check quickly based on hex id:
        - 0000/<first2>/<hexid>
        - any file with name equal to hexid or starting with hexid
        """
        candidates = []
        try:
            sub = path_0000 / hexid[:2] / hexid
            if sub.exists():
                candidates.append(sub)
        except Exception:
            pass

        # Try some common extensions / filename patterns without scanning whole tree:
        # check immediate subfolder entries under 0000/<first2>
        try:
            hint_dir = path_0000 / hexid[:2]
            if hint_dir.exists() and hint_dir.is_dir():
                for p in hint_dir.iterdir():
                    if p.is_file() and p.name.startswith(hexid):
                        candidates.append(p)
        except Exception:
            pass

        # also check top-level files in 0000 with name starting with hexid
        try:
            for p in path_0000.iterdir():
                if p.is_file() and p.name.startswith(hexid):
                    candidates.append(p)
        except Exception:
            pass

        # deduplicate while preserving order
        seen = set()
        uniq = []
        for c in candidates:
            if str(c) not in seen:
                seen.add(str(c))
                uniq.append(c)
        return uniq

    def find_many(self, path_0000: str, targets: List[Tuple[str, str]]) -> List[Dict]:
        """
        Fast multi-target search.

        path_0000: path to 0000 folder (string)
        targets: list of (m_Name, hexid) tuples in the exact order you want results returned.

        Returns: list of dicts (same order as targets). Each dict:
            {
                "name": m_Name,
                "id": hexid,
                "path": path to Unity file containing the asset or None,
                "size": filesize in bytes (0 if not found),
                "container": container key (object path inside file) or None
            }
        """
        base = Path(path_0000)
        result_map: Dict[str, Dict] = {}   # m_Name -> result dict
        # initialize results with None
        for m_name, hexid in targets:
            result_map[m_name] = {"name": m_name, "id": hexid, "path": None, "size": 0, "container": None}

        wanted_names = set([m for m, _ in targets])

        # 1) Fast direct lookup attempts per hex id (cheap checks to avoid full scan)
        for m_name, hexid in targets:
            if result_map[m_name]["path"] is not None:
                continue
            try:
                candidates = self._direct_lookup_candidates(base, hexid)
                for cand in candidates:
                    env = self._try_open_env(cand)
                    if not env:
                        continue
                    matches = self._check_env_for_targets(env, {m_name})
                    if matches:
                        # take first match
                        found = matches[0]
                        result_map[m_name] = {
                            "name": m_name,
                            "id": hexid,
                            "path": str(cand),
                            "size": cand.stat().st_size if cand.exists() else 0,
                            "container": found.get("container"),
                        }
                        # once found, remove from wanted_names
                        if m_name in wanted_names:
                            wanted_names.remove(m_name)
                        break
            except Exception:
                # don't break overall flow if direct lookup fails
                continue

        # 2) If all found, return in original order
        if not wanted_names:
            return [result_map[m_name] for m_name, _ in targets]

        # 3) Brute-force single-pass scan of all files under 0000:
        #    load each Unity file once and check all objects for any wanted_names
        try:
            for root, _, files in os.walk(base):
                for fname in files:
                    # stop early if everything found
                    if not wanted_names:
                        break
                    fpath = Path(root) / fname
                    try:
                        env = self._try_open_env(fpath)
                        if not env:
                            continue
                        matches = self._check_env_for_targets(env, wanted_names)
                        if not matches:
                            continue
                        for found in matches:
                            m_name = found.get("m_Name")
                            if m_name and m_name in wanted_names:
                                # record only if not already recorded
                                if result_map[m_name]["path"] is None:
                                    result_map[m_name] = {
                                        "name": m_name,
                                        "id": next((hid for (mn,hid) in targets if mn==m_name), ""),
                                        "path": str(fpath),
                                        "size": fpath.stat().st_size if fpath.exists() else 0,
                                        "container": found.get("container"),
                                    }
                                    wanted_names.discard(m_name)
                    except Exception:
                        # ignore individual file failures; continue scanning
                        continue
                if not wanted_names:
                    break
        except Exception:
            # full walk failed unexpectedly; fall back to whatever we've found so far
            pass

        # return list aligned with requested order
        return [result_map[m_name] for m_name, _ in targets]