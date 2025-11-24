"""
Faster asset finder that leverages step_1_config.txt (if present) to avoid brute-force.

This module provides:
- load_search_triples_from_config(config_path) -> list[(search_term, expected_filename, expected_size)]
- named_search / size_search / brute_force_search (same semantics)
- search(...) (tries smart methods then brute force)
- multi_search(path_0000, search_terms, expected_info=None, logger=print)

If expected_info is omitted, multi_search will attempt to read the repository's
step_1_config.txt (project root) to obtain expected filenames and sizes so it can
do a much faster direct lookup (direct path / size-based) instead of full brute force.
"""
from pathlib import Path
import UnityPy
import os
from typing import List, Optional, Tuple

def is_correct_file(path, obj, search_term):
    try:
        data = obj.read()
        return getattr(data, "m_Name", "") == search_term
    except Exception:
        return False

def named_search(path_0000: Path, search_term: str, expected_filename: str) -> Optional[dict]:
    """
    If we know the expected filename (the hex filename stored in 0000/<first2>/<filename>),
    go directly to that path and check whether its contained Unity objects include the
    requested m_Name. This is very fast compared to brute force.
    """
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
    """
    Search files in path_0000 sorted by closeness to expected_size. This reduces the
    number of UnityPy loads for large collections.
    """
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
    """
    Full scan. Slow; fallback only.
    """
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
            logger(f"Found {search_term} by named_search.")
            return res
    # try size-based search if expected_size provided
    if expected_size:
        res = size_search(path_0000, search_term, expected_size)
        if res:
            logger(f"Found {search_term} by size_search.")
            return res
    logger(f"Falling back to brute force for {search_term}...")
    res = brute_force_search(path_0000, search_term)
    if res:
        logger(f"Found {search_term} by brute_force.")
    else:
        logger(f"Could not find {search_term}.")
    return res

def multi_search(path_0000: Path, search_terms: List[str], expected_info: Optional[List[Tuple[str,int]]] = None, logger=print):
    """
    Multi-search helper. If expected_info is None, attempts to load step_1_config.txt
    from the repository root and use that to accelerate searches.

    expected_info is a list of tuples (expected_filename, expected_size) corresponding
    to the search_terms list. If an entry is missing, blank/defaults will be used.

    Returns list of result dicts (or None) in the same order as search_terms.
    """
    path_0000 = Path(path_0000)
    # If expected_info not provided, try to read from a config file near project root.
    if expected_info is None:
        try:
            # step_1_config.txt is typically located next to the scripts (project root in this repo)
            repo_root = Path(__file__).resolve().parents[1]
            cfg_path = repo_root / "step_1_config.txt"
            if cfg_path.is_file():
                cfg_triples = load_search_triples_from_config(cfg_path)
                # Build a mapping from search_term -> (expected_filename, expected_size)
                cfg_map = {t[0]: (t[1], t[2]) for t in cfg_triples}
                expected_info = []
                for term in search_terms:
                    if term in cfg_map:
                        expected_info.append(cfg_map[term])
                    else:
                        expected_info.append(("", 0))
            else:
                expected_info = [("", 0)] * len(search_terms)
        except Exception:
            expected_info = [("", 0)] * len(search_terms)

    # Now run searches using the expected_info entries
    ans = [None for _ in search_terms]
    for i, term in enumerate(search_terms):
        expected_filename, expected_size = ("", 0)
        if expected_info and i < len(expected_info):
            expected_filename, expected_size = expected_info[i]
        ans[i] = search(path_0000, term, expected_filename, expected_size, logger=logger)
    for file_path in ans:
        logger(f"Found {file_path}")
    return ans

def load_search_triples_from_config(config_path: Path) -> List[Tuple[str,str,int]]:
    """
    Parse a step_1_config.txt file that looks like:

    ### Put the path to YOUR 0000 folder in the below line
    C:\...\0000
    ### Names of assets of interest ...
    CARD_Desc 21ae1efa 725225
    CARD_Indx 507764bc 61824
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
    # first non-comment line is path_0000; skip it
    if not lines:
        return []
    # lines[0] is path_0000; parse subsequent lines
    triples = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 3:
            search_term = parts[0]
            expected_filename = parts[1]
            try:
                expected_size = int(parts[2])
            except Exception:
                expected_size = 0
            triples.append((search_term, expected_filename, expected_size))
    return triples
