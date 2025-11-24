"""
Updated GUI main window:
- Loads/creates braced DESC view using Card_Pidx/Card_Part if necessary.
- Save writes !Changed !Braced ... and !Unbraced !Changed ... and !Changed Card_Part.bytes.dec
- Keeps in-memory arrays updated so Save persists when switching cards.
- Copies found Unity asset container files into common_defs.copied_files_folder/0000/... for compatibility with step_4 script.
- Build button will run step_4_mod_the_files.py (single-click) to produce the modded 0000 folder (uses original scripts).
"""
import os
import threading
import json
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import shutil
import subprocess
import common_defs

from gui.theme import apply_theme
from core import asset_finder, asset_unpacker, card_parser, part_parser, utils

APP_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = APP_ROOT / "output"
EXTRACTED = OUTPUT / "extracted"
CHANGED = OUTPUT / "changed"
ASSETS = APP_ROOT / "assets"

REQUIRED_ASSETS = [
    ("CARD_Desc", "CARD_Desc"),
    ("CARD_Indx", "CARD_Indx"),
    ("CARD_Name", "CARD_Name"),
    ("Card_Part", "Card_Part"),
    ("Card_Pidx", "Card_Pidx"),
    ("CARD_Prop", "CARD_Prop"),
    ("WORD_Text", "WORD_Text"),
    ("WORD_Indx", "WORD_Indx"),
    ("CardPictureFontSetting", "CardPictureFontSetting"),
]

class MainWindow(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        apply_theme(master)
        self.master = master
        self.pack(fill="both", expand=True)
        self._create_widgets()
        self.extracted_folder = EXTRACTED
        self.changed_folder = CHANGED
        self.search_results = {}
        self.card_names = []
        self.card_descs = []     # current (braced) descriptions displayed/edited
        self.orig_descs = []     # original unbraced descriptions (for reference)
        OUTPUT.mkdir(exist_ok=True)
        EXTRACTED.mkdir(exist_ok=True, parents=True)
        CHANGED.mkdir(exist_ok=True, parents=True)

        # load sample if present
        sample_json = ASSETS / "sample_data" / "CARD_Desc.bytes.dec.json"
        if sample_json.exists():
            self.log("Sample data found. Loading sample dataset.")
            self._load_extracted(ASSETS / "sample_data")

    # --- UI creation (same layout, unchanged) ---
    def _create_widgets(self):
        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=8, pady=6)
        ttk.Label(top, text="Game 0000 folder:").pack(side="left")
        self.folder_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.folder_var, width=70).pack(side="left", padx=6)
        ttk.Button(top, text="Browse", command=self.browse_folder).pack(side="left", padx=6)
        ttk.Button(top, text="Find & Extract All", command=self._on_extract_all).pack(side="left", padx=6)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0,8))

        self.tab_extract = ttk.Frame(notebook)
        notebook.add(self.tab_extract, text="Extract")
        self._build_extract_tab()

        self.tab_edit = ttk.Frame(notebook)
        notebook.add(self.tab_edit, text="Edit")
        self._build_edit_tab()

        self.tab_repack = ttk.Frame(notebook)
        notebook.add(self.tab_repack, text="Repack")
        self._build_repack_tab()

        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", padx=8, pady=6)
        self.log_text = tk.Text(bottom, height=8, wrap="none", bg="#FFFFFF", fg="#0B1724")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(bottom, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text['yscrollcommand'] = scrollbar.set
        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=8, pady=(0,8))

    def _build_extract_tab(self):
        frame = self.tab_extract
        ttk.Label(frame, text="Extract / Decrypt").pack(anchor="nw", padx=8, pady=6)
        self.extract_tree = ttk.Treeview(frame, columns=("path", "size", "container"), show="headings", height=12)
        self.extract_tree.heading("path", text="Found Path")
        self.extract_tree.heading("size", text="Size")
        self.extract_tree.heading("container", text="Container Name")
        self.extract_tree.pack(fill="both", expand=True, padx=8, pady=6)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", padx=8, pady=6)
        ttk.Button(btn_frame, text="Extract Selected", command=self._extract_selected).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Extract & Decrypt All", command=self._on_extract_all).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Open extracted folder", command=lambda: utils.open_path(self.extracted_folder)).pack(side="left", padx=4)

    def _build_edit_tab(self):
        frame = self.tab_edit
        top = ttk.Frame(frame)
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Search (ID or name):").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.search_var, width=40).pack(side="left", padx=6)
        ttk.Button(top, text="Search", command=self._on_search).pack(side="left", padx=6)
        ttk.Button(top, text="Reload extracted", command=self._reload_extracted).pack(side="left", padx=6)

        middle = ttk.Frame(frame)
        middle.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(middle)
        left.pack(side="left", fill="y", padx=(0,8))
        self.card_listbox = tk.Listbox(left, width=40, height=28, bg="#FFFFFF", fg="#0B1724")
        self.card_listbox.pack(side="top", fill="y", expand=True)
        self.card_listbox.bind("<<ListboxSelect>>", self._on_card_select)
        right = ttk.Frame(middle)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Name:").pack(anchor="nw")
        self.name_text = tk.Text(right, height=2, bg="#FFFFFF", fg="#0B1724")
        self.name_text.pack(fill="x", pady=(0,6))
        ttk.Label(right, text="Description (braced view):").pack(anchor="nw")
        self.desc_text = tk.Text(right, height=12, bg="#FFFFFF", fg="#0B1724")
        self.desc_text.pack(fill="both", expand=True)
        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill="x", pady=6)
        ttk.Button(btn_frame, text="Save Changes", command=self._save_changes).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Export changed JSON", command=self._export_changed_json).pack(side="left", padx=4)

    def _build_repack_tab(self):
        frame = self.tab_repack
        ttk.Label(frame, text="Repack / Encrypt").pack(anchor="nw", padx=8, pady=6)
        ttk.Button(frame, text="Build Mod Files (1-click)", command=self._build_mod_files).pack(padx=8, pady=4, anchor="nw")
        ttk.Button(frame, text="Export ZIP", command=self._export_zip).pack(padx=8, pady=4, anchor="nw")
        ttk.Button(frame, text="Open mod output folder", command=lambda: utils.open_path(OUTPUT)).pack(padx=8, pady=4, anchor="nw")

    # --- Logging / progress ---
    def log(self, s):
        self.log_text.insert("end", s + "\n")
        self.log_text.see("end")

    def set_progress(self, value, maximum=None):
        if maximum:
            self.progress['maximum'] = maximum
        self.progress['value'] = value

    # --- Actions ---
    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_var.set(path)

    def _on_extract_all(self):
        folder = self.folder_var.get().strip()
        if not folder:
            folder = filedialog.askdirectory(title="Select 0000 folder")
            if not folder:
                return
            self.folder_var.set(folder)
        folder = Path(folder)
        if not folder.exists():
            messagebox.showerror("Error", "Selected folder does not exist.")
            return
        thread = threading.Thread(target=self._extract_all_thread, args=(folder,), daemon=True)
        thread.start()

    def _extract_all_thread(self, folder: Path):
        self.log("Starting search & extract...")
        targets = [name for name, _ in REQUIRED_ASSETS]
        # fast multi_search uses built-in hex-name mapping or step_1_config.txt
        results = asset_finder.multi_search(folder, targets, logger=self.log)
        self.search_results = {targets[i]: results[i] for i in range(len(targets))}
        # populate tree
        for i in self.extract_tree.get_children():
            self.extract_tree.delete(i)
        for k, v in self.search_results.items():
            if v:
                self.extract_tree.insert("", "end", values=(str(v['path']), v['size'], v['container']))
                self.log(f"Found {k}: {v['path']} ({v['size']} bytes) in {v['container']}")
            else:
                self.extract_tree.insert("", "end", values=(f"NOT FOUND: {k}", "-", "-"))
                self.log(f"Missing {k}")

        # Copy found Unity container files into common_defs.copied_files_folder/0000/... for compatibility
        copied_root = Path(common_defs.copied_files_folder)
        for k, info in self.search_results.items():
            if not info:
                continue
            src = Path(info['path'])
            dest_dir = copied_root / "0000" / src.name[:2]
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            try:
                shutil.copy2(src, dest)
                self.log(f"Copied container {src.name} -> {dest}")
            except Exception as e:
                self.log(f"Failed to copy {src} to {dest}: {e}")

        # Extract each found container (unpack assets) into EXTRACTED
        EXTRACTED.mkdir(parents=True, exist_ok=True)
        files_to_extract = [v['path'] for v in self.search_results.values() if v]
        total = len(files_to_extract)
        self.set_progress(0, total)
        for idx, fp in enumerate(files_to_extract, start=1):
            try:
                asset_unpacker.unpack_single_asset(Path(fp), EXTRACTED, logger=self.log)
            except Exception as e:
                self.log(f"Error extracting {fp}: {e}")
            self.set_progress(idx)
        self.log("Extraction complete.")
        # After extraction, prepare braced descriptions and load into Edit tab
        self._load_extracted(EXTRACTED)

    def _extract_selected(self):
        sel = self.extract_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a row to extract.")
            return
        val = self.extract_tree.item(sel[0], "values")
        path = val[0]
        if path.startswith("NOT FOUND"):
            messagebox.showwarning("Not Found", "Selected row is not a file.")
            return
        thread = threading.Thread(target=self._extract_single_thread, args=(Path(path),), daemon=True)
        thread.start()

    def _extract_single_thread(self, path: Path):
        self.log(f"Extracting {path} ...")
        try:
            asset_unpacker.unpack_single_asset(path, self.extracted_folder, logger=self.log)
            self.log("Done.")
            self._load_extracted(self.extracted_folder)
        except Exception as e:
            self.log(f"Error: {e}")

    def _load_extracted(self, extracted_path: Path):
        self.log("Loading extracted data...")
        try:
            name_file = Path(extracted_path) / "CARD_Name.bytes.dec.json"
            desc_file = Path(extracted_path) / "CARD_Desc.bytes.dec.json"
            # original unbraced JSON
            if not name_file.exists() or not desc_file.exists():
                self.log("Name/Desc JSON files not found in extracted folder.")
                return
            names = card_parser.load_names(name_file)
            descs = card_parser.load_descs(desc_file)
            # Try to find existing braced file generated by earlier step_2; if missing create one
            braced_file = Path(extracted_path) / "!Braced CARD_Desc.bytes.dec.json"
            if braced_file.exists():
                with open(braced_file, encoding="utf-8") as f:
                    braced_descs = json.load(f)
                self.log("Loaded existing braced descriptions.")
            else:
                # use Card_Pidx/Card_Part to build braced view
                pidx = Path(extracted_path) / "Card_Pidx.bytes.dec"
                part = Path(extracted_path) / "Card_Part.bytes.dec"
                if pidx.exists() and part.exists():
                    braced_descs = card_parser.build_braced_descs(descs, pidx, part)
                    # write a braced file to extracted for convenience
                    with open(braced_file, "w", encoding="utf-8") as f:
                        json.dump(braced_descs, f, ensure_ascii=False, indent=2)
                    self.log("Generated braced descriptions from Card_Pidx/Card_Part.")
                else:
                    # fallback: show unbraced but still editable
                    braced_descs = descs.copy()
                    self.log("No part/pidx to compute braces; using unbraced descriptions.")
            # load into GUI data structures
            self.card_names = names
            self.card_descs = braced_descs
            self.orig_descs = descs
            # if user previously saved changed braced file, prefer that (from CHANGED)
            changed_braced = CHANGED / "!Changed !Braced CARD_Desc.bytes.dec.json"
            if changed_braced.exists():
                with open(changed_braced, encoding="utf-8") as f:
                    changed_list = json.load(f)
                # override the in-memory descs with changed ones
                self.card_descs = changed_list
                self.log("Found changed braced file; using changed descriptions.")
            self._populate_card_list()
            self.log(f"Loaded {len(self.card_names)} cards.")
        except Exception as e:
            self.log(f"Failed to load extracted data: {e}")

    def _populate_card_list(self):
        self.card_listbox.delete(0, "end")
        for i, name in enumerate(self.card_names):
            display = f"{i:05d} - {utils.truncate_for_list(name, 60)}"
            self.card_listbox.insert("end", display)

    def _on_search(self):
        q = self.search_var.get().strip().lower()
        if not q:
            self._populate_card_list()
            return
        hits = []
        for i, name in enumerate(self.card_names):
            if q in name.lower() or q == str(i):
                hits.append((i, name))
        self.card_listbox.delete(0, "end")
        for i, name in hits:
            self.card_listbox.insert("end", f"{i:05d} - {utils.truncate_for_list(name, 60)}")

    def _reload_extracted(self):
        self._load_extracted(self.extracted_folder)

    def _on_card_select(self, evt):
        w = evt.widget
        if not w.curselection():
            return
        sel = w.curselection()[0]
        value = w.get(sel)
        idx = int(value.split("-")[0].strip())
        name = self.card_names[idx]
        desc = self.card_descs[idx] if idx < len(self.card_descs) else ""
        self.name_text.delete("1.0", "end")
        self.name_text.insert("1.0", name)
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", desc)

    def _save_changes(self):
        sel = self.card_listbox.curselection()
        if not sel:
            messagebox.showinfo("Select", "Select a card to save.")
            return
        sel_idx = sel[0]
        display = self.card_listbox.get(sel_idx)
        idx = int(display.split("-")[0].strip())
        new_name = self.name_text.get("1.0", "end").rstrip("\n")
        new_braced_desc = self.desc_text.get("1.0", "end").rstrip("\n")
        # update in-memory arrays
        self.card_names[idx] = new_name
        if idx < len(self.card_descs):
            self.card_descs[idx] = new_braced_desc
        else:
            while len(self.card_descs) <= idx:
                self.card_descs.append("")
            self.card_descs[idx] = new_braced_desc
        # Write changed braced file and unbraced + changed part
        CHANGED.mkdir(parents=True, exist_ok=True)
        # save names changed JSON (simple copy of CARD_Name.dec.json but changed entries)
        name_out = CHANGED / "CARD_Name.bytes.dec.json"
        with open(name_out, "w", encoding="utf-8") as f:
            json.dump(self.card_names, f, ensure_ascii=False, indent=2)
        # save braced changed
        braced_out = card_parser.save_changed_braced(CHANGED, self.card_descs)
        # create unbraced changed and save
        unbraced = card_parser.make_unbraced_from_braced(self.card_descs)
        unbraced_out = card_parser.save_unbraced_changed(CHANGED, unbraced)
        # using extracted part/pidx and original braced file (or freshly built) to create changed Card_Part
        try:
            pidx_src = Path(EXTRACTED) / "Card_Pidx.bytes.dec"
            part_src = Path(EXTRACTED) / "Card_Part.bytes.dec"
            if pidx_src.exists() and part_src.exists():
                # use original braced (before change) — orig_braced computed earlier if any
                orig_braced_file = Path(EXTRACTED) / "!Braced CARD_Desc.bytes.dec.json"
                if orig_braced_file.exists():
                    with open(orig_braced_file, encoding="utf-8") as f:
                        orig_braced = json.load(f)
                else:
                    # if not exists, build from orig descs
                    orig_braced = card_parser.build_braced_descs(self.orig_descs, pidx_src, part_src)
                changed_part_path = CHANGED / "!Changed Card_Part.bytes.dec"
                card_parser.make_changed_part_file(changed_part_path, pidx_src, part_src, orig_braced, self.card_descs)
                self.log(f"Wrote changed part file: {changed_part_path}")
            else:
                self.log("Card_Pidx/Card_Part not available in extracted; cannot auto-build changed part file.")
        except Exception as e:
            self.log(f"Error building changed part file: {e}")

        # also write unbraced and braced to CHANGED for other script compatibility
        self.log(f"Saved changes for card {idx} to {CHANGED}")
        # keep UI consistent: update list display text
        self._populate_card_list()

    def _export_changed_json(self):
        folder = filedialog.askdirectory(title="Choose folder to export changed JSON")
        if not folder:
            return
        folder = Path(folder)
        CHANGED.mkdir(parents=True, exist_ok=True)
        for p in CHANGED.glob("*"):
            if p.is_file():
                utils.copy_path(p, folder / p.name)
        messagebox.showinfo("Exported", f"Exported changed JSON files to {folder}")

    def _build_mod_files(self):
        # Use the original step_4_mod_the_files.py to produce modded 0000 if available.
        # Ensure copied_files_folder contains the Unity containers (we copied them earlier on extract).
        step4 = Path(APP_ROOT) / "step_4_mod_the_files.py"
        if not step4.exists():
            messagebox.showerror("Missing", "step_4_mod_the_files.py not found in project root.")
            return
        thread = threading.Thread(target=self._build_mod_thread, args=(step4,), daemon=True)
        thread.start()

    def _build_mod_thread(self, step4_script: Path):
        try:
            # run the original script (it uses common_defs paths)
            self.log("Running step_4_mod_the_files.py ...")
            subprocess.check_call(["python", str(step4_script)], cwd=str(APP_ROOT))
            self.log("step_4_mod_the_files.py finished.")
            messagebox.showinfo("Done", f"Built mod files in {common_defs.modded_folder}")
        except subprocess.CalledProcessError as e:
            self.log(f"Error building mod files: {e}")
            messagebox.showerror("Error", str(e))

    def _export_zip(self):
        out = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("Zip files", "*.zip")])
        if not out:
            return
        out = Path(out)
        base = OUTPUT
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(base):
                for f in files:
                    fp = Path(root) / f
                    z.write(fp, fp.relative_to(base))
        messagebox.showinfo("Exported", f"Exported ZIP to {out}")
