"""
Utility helpers used across the core modules.
"""
from pathlib import Path
import shutil
import sys
import subprocess
import os

def file_walker(source_folder: Path):
    for p in source_folder.rglob("*"):
        if p.is_file():
            yield p

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def open_path(path):
    path = Path(path)
    if not path.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])

def copy_path(src, dst):
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

def copy_folder(src, dst, exclude_patterns=None):
    src = Path(src)
    dst = Path(dst)
    exclude_patterns = exclude_patterns or []
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if any(rel.match(pat) for pat in exclude_patterns):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.is_file():
            shutil.copy2(p, target)

def truncate_for_list(s: str, n=60):
    if len(s) <= n:
        return s
    return s[:n-3] + "..."