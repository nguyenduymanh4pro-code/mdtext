"""
Common utilities.
"""
from pathlib import Path
import json
import zipfile
import time

def ensure_dirs(*paths):
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)

class AppLogger:
    def __init__(self, widget=None):
        self.widget = widget

    def set_widget(self, widget):
        self.widget = widget

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        s = f"[{ts}] {msg}\n"
        if self.widget:
            try:
                self.widget.insert("end", s)
                self.widget.see("end")
            except Exception:
                pass
        else:
            print(s)

def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def read_json(path):
    import json
    return json.loads(Path(path).read_text(encoding="utf-8"))

def zip_folder(src_folder: Path, dest_zip: str):
    src_folder = Path(src_folder)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src_folder.rglob("*"):
            z.write(p, p.relative_to(src_folder))