"""
Faster asset finder that leverages a built-in mapping of expected
asset filenames (hex names) to avoid brute-force scanning.

Behavior:
- If a step_1_config.txt exists next to the project root it is still used.
- Otherwise a built-in default list (from your message) is used so the tool
  will try a direct named lookup at 0000/<first2>/<expected_filename> for each asset.
- Falls back to size-based search or brute force only if direct lookup fails.

This makes searching many orders of magnitude faster in typical Master Duel installs.
"""
from pathlib import Path
import UnityPy
import os
from typing import List, Optional, Tuple

# Default triples taken from your message: (search_term, expected_filename, expected_size)
# expected_size set to 0 when unknown: named_search uses expected_filename only.
DEFAULT_SEARCH_TRIPLES: List[Tuple[str, str, int]] = [
    ("CARD_Desc", "21ae1efa", 0),
    ("CARD_Indx", "507764bc", 0),
    ("CARD_Name", "7438cca8", 0),
    ("Card_Part", "52739c94", 0),
    ("Card_Pidx", "494e34d0", 0),
    ("CARD_Prop", "85757744", 0),
    ("WORD_Text", "f5361426", 0),
    ("WORD_Indx", "b4d165f3", 0),
    ("CardPictureFontSetting", "fcd008c9", 0),
]

def is_correct_file(path, obj, search_term):
    try:
        data = obj.read()
        return getattr(data, "m_Name", "") == search_term
    except Exception:
        return False

def named_search(path_0000: Path, search_term: str, expected_filename: str) -> Optional[dict]:
    """
    Direct lookup to 0000/<first2>/<expected_filename> which is much faster than scanning.
    """
    if not expected_filename:
        return None
    expected_file_path = Path(path_0000) / expected_filename[:2] / expected_filename
    if expected_file_path.is_file():
        try:
            env = UnityPy.load(str(expected_file_path))
        except Exception:
            return None
        for path, obj in env.container.items():
            if is_correct_file(path, obj, search_term):
                return {"path": str(expected_file_path), "size": os.path.getsize(expected_file_path), "container": path}
    return None

def size_search(path_0000: Path, search_term: str, expected_size: int) -> Optional[dict]:
    files_list = []
    for root, dirs, files in os.walk(path_0000):
        for fn in files:
            fp = Path(root) / fn
            try:
                files_list.append((abs(fp.stat().st_size - expected_size), fp))
            except Exception:
                continue
    files_list.sort(key=lambda x: x[0])
    for _, file_path in files_list:
        try:
            env = UnityPy.load(str(file_path))
        except Exception:
            continue
        for path, obj in env.container.items():
            if is_correct_file(path, obj, search_term):
                return {"path": str(file_path), "size": os.path.getsize(file_path), "container": path}
    return None

def brute_force_search(path_0000: Path, search_term: str) -> Optional[dict]:
    for root, dirs, files in os.walk(path_0000):
        for fn in files:
            fp = Path(root) / fn
            try:
                env = UnityPy.load(str(fp))
            except Exception:
                continue
            for path, obj in env.container.items():
                if is_correct_file(path, obj, search_term):
                    return {"path": str(fp), "size": os.path.getsize(fp), "container": path}
    return None

def search(path_0000: Path, search_term: str, expected_filename: str, expected_size: int, logger=print):
    """
    Try named_search (direct path), then size_search, then brute force.
    """
    logger(f"Searching for {search_term} ...")
    if expected_filename:
        res = named_search(path_0000, search_term, expected_filename)
        if res:
            logger(f"Found {search_term} by named_search -> {res['path']}")
            return res
    # try size-based search if expected_size provided and > 0
    if expected_size:
        res = size_search(path_0000, search_term, expected_size)
        if res:
            logger(f"Found {search_term} by size_search -> {res['path']}")
            return res
    logger(f"Falling back to brute force for {search_term}...")
    res = brute_force_search(path_0000, search_term)
    if res:
        logger(f"Found {search_term} by brute_force -> {res['path']}")
    else:
        logger(f"Could not find {search_term}.")
    return res

def load_search_triples_from_config(config_path: Path) -> List[Tuple[str,str,int]]:
    """
    Parse a step_1_config.txt file that looks like:
      <path_to_0000>
      CARD_Desc 21ae1efa 725225
      ...
    Returns list of triples (search_term, expected_filename, expected_size)
    """
    config_path = Path(config_path)
    lines = []
    with open(config_path, encoding="utf-8") as f:
        for raw in f.readlines():
            s = raw.strip()
            if not s or s.startswith("###"):
                continue
            lines.append(s)
    if not lines:
        return []
    triples = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 2:
            search_term = parts[0]
            expected_filename = parts[1]
            expected_size = 0
            if len(parts) >= 3:
                try:
                    expected_size = int(parts[2])
                except Exception:
                    expected_size = 0
            triples.append((search_term, expected_filename, expected_size))
    return triples

def multi_search(path_0000: Path, search_terms: List[str], expected_info: Optional[List[Tuple[str,int]]] = None, logger=print):
    """
    Multi-search helper. Uses the following priority to determine expected filename:
    1) explicit expected_info argument (if provided by caller)
    2) step_1_config.txt located at repo root
    3) DEFAULT_SEARCH_TRIPLES hard-coded mapping (fast path based on your data)
    4) fallback to empty expected filename (slow)

    Returns list of result dicts (or None) in the same order as search_terms.
    """
    path_0000 = Path(path_0000)

    if expected_info is None:
        # attempt to load config near repo root
        try:
            repo_root = Path(__file__).resolve().parents[1]
            cfg_path = repo_root / "step_1_config.txt"
            if cfg_path.is_file():
                cfg_triples = load_search_triples_from_config(cfg_path)
            else:
                cfg_triples = []
        except Exception:
            cfg_triples = []

        # build mapping from cfg_triples or default triples
        mapping = {t[0]: (t[1], t[2]) for t in cfg_triples} if cfg_triples else {t[0]: (t[1], t[2]) for t in DEFAULT_SEARCH_TRIPLES}
        expected_info = []
        for term in search_terms:
            if term in mapping:
                expected_info.append(mapping[term])
            else:
                expected_info.append(("", 0))

    ans = [None for _ in search_terms]
    for i, term in enumerate(search_terms):
        expected_filename, expected_size = ("", 0)
        if expected_info and i < len(expected_info):
            expected_filename, expected_size = expected_info[i]
        ans[i] = search(path_0000, term, expected_filename, expected_size, logger=logger)
    for file_path in ans:
        logger(f"Search result: {file_path}")
    return ans
