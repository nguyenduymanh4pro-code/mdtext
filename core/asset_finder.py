"""
Search Unity asset container files under the game's 0000 folder to find assets
by their internal m_Name. Uses UnityPy to open files and inspect container objects.

Provides:
- named_search
- size_search
- brute_force_search
- multi_search

Each returned result is a dict:
{
  "path": Path(...),
  "size": int,
  "container": object_name (m_Name)
}
"""
from pathlib import Path
import UnityPy
import os
from typing import List, Optional

def is_correct_file(path, obj, search_term):
    try:
        data = obj.read()
        return getattr(data, "m_Name", "") == search_term
    except Exception:
        return False

def named_search(path_0000: Path, search_term: str, expected_filename: str) -> Optional[dict]:
    expected_file_path = path_0000 / expected_filename[:2] / expected_filename
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
            files_list.append((abs(fp.stat().st_size - expected_size), fp))
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
    Try smart methods first, fall back to brute force.
    """
    logger(f"Searching for {search_term} ...")
    res = named_search(path_0000, search_term, expected_filename)
    if res:
        logger(f"Found {search_term} by named_search.")
        return res
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

def multi_search(path_0000: Path, search_terms: List[str], expected_info=None, logger=print):
    """
    expected_info is optional list of (expected_filename, expected_size)
    Returns list of results or None for each.
    """
    results = []
    for i, term in enumerate(search_terms):
        exp_fn, exp_sz = ("", 0)
        if expected_info and i < len(expected_info):
            exp_fn, exp_sz = expected_info[i]
        r = search(path_0000, term, exp_fn, exp_sz, logger=logger)
        results.append(r)
    return results