"""
Main GUI window using Tkinter with three tabs: Extract, Edit, Repack.
Implements logging and progress callbacks and integrates core modules.
"""
import os
import threading
import json
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from gui.theme import apply_theme
from core import asset_finder, asset_unpacker, card_parser, encryptor, decryptor, part_parser, word_parser, utils

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
        self.card_index = []  # list of card IDs for Edit tab
        self.card_names = []
        self.card_descs = []

        # Make output dirs
        OUTPUT.mkdir(exist_ok=True)
        EXTRACTED.mkdir(exist_ok=True, parents=True)
        CHANGED.mkdir(exist_ok=True, parents=True)

        # If sample data exists, load it
        sample_json = ASSETS / "sample_data" / "CARD_Desc.bytes.dec.json"
        if sample_json.exists():
            self.log("Sample data found. Loading sample dataset.")
            self._load_extracted_sample(ASSETS / "sample_data")

    def _create_widgets(self):
        # Top: toolbar-like frame to choose game folder
        top = ttk.Frame(self)
        top.pack(side="top", fill="x", padx=8, pady=6)

        ttk.Label(top, text="Game 0000 folder:").pack(side="left")
        self.folder_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.folder_var, width=70).pack(side="left", padx=6)
        ttk.Button(top, text="Browse", command=self.browse_folder).pack(side="left", padx=6)
        ttk.Button(top, text="Find & Extract All", command=self._on_extract_all).pack(side="left", padx=6)

        # Notebook tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(0,8))

        # Extract Tab
        self.tab_extract = ttk.Frame(notebook)
        notebook.add(self.tab_extract, text="Extract")

        self._build_extract_tab()

        # Edit Tab
        self.tab_edit = ttk.Frame(notebook)
        notebook.add(self.tab_edit, text="Edit")

        self._build_edit_tab()

        # Repack Tab
        self.tab_repack = ttk.Frame(notebook)
        notebook.add(self.tab_repack, text="Repack")

        self._build_repack_tab()

        # Bottom: log console and progress
        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", padx=8, pady=6)
        self.log_text = tk.Text(bottom, height=8, wrap="none", bg="#071225", fg="#E6EEF6")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(bottom, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text['yscrollcommand'] = scrollbar.set

        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=8, pady=(0,8))

    def _build_extract_tab(self):
        frame = self.tab_extract
        lbl = ttk.Label(frame, text="Extract / Decrypt")
        lbl.pack(anchor="nw", padx=8, pady=6)

        # Results listing
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

        self.card_listbox = tk.Listbox(left, width=40, height=28, bg="#071225", fg="#E6EEF6")
        self.card_listbox.pack(side="top", fill="y", expand=True)
        self.card_listbox.bind("<<ListboxSelect>>", self._on_card_select)

        right = ttk.Frame(middle)
        right.pack(side="left", fill="both", expand=True)

        lbl_name = ttk.Label(right, text="Name:")
        lbl_name.pack(anchor="nw")
        self.name_text = tk.Text(right, height=2, bg="#071225", fg="#E6EEF6")
        self.name_text.pack(fill="x", pady=(0,6))

        lbl_desc = ttk.Label(right, text="Description:")
        lbl_desc.pack(anchor="nw")
        self.desc_text = tk.Text(right, height=12, bg="#071225", fg="#E6EEF6")
        self.desc_text.pack(fill="both", expand=True)

        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill="x", pady=6)
        ttk.Button(btn_frame, text="Save Changes", command=self._save_changes).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Export changed JSON", command=self._export_changed_json).pack(side="left", padx=4)

    def _build_repack_tab(self):
        frame = self.tab_repack
        ttk.Label(frame, text="Repack / Encrypt").pack(anchor="nw", padx=8, pady=6)

        ttk.Button(frame, text="Build Mod Files", command=self._build_mod_files).pack(padx=8, pady=4, anchor="nw")
        ttk.Button(frame, text="Export ZIP", command=self._export_zip).pack(padx=8, pady=4, anchor="nw")
        ttk.Button(frame, text="Open mod output folder", command=lambda: utils.open_path(OUTPUT)).pack(padx=8, pady=4, anchor="nw")

    # UI actions

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_var.set(path)

    def _log_callback(self, s, end="\n"):
        self.log(s + end)

    def log(self, s):
        self.log_text.insert("end", s + "\n")
        self.log_text.see("end")

    def set_progress(self, value, maximum=None):
        if maximum:
            self.progress['maximum'] = maximum
        self.progress['value'] = value

    def _on_extract_all(self):
        folder = self.folder_var.get().strip()
        if not folder:
            folder = filedialog.askdirectory(title="Select 0000 folder")
            if not folder: return
            self.folder_var.set(folder)

        folder = Path(folder)
        if not folder.exists():
            messagebox.showerror("Error", "Selected folder does not exist.")
            return

        # Run in thread to keep UI responsive
        thread = threading.Thread(target=self._extract_all_thread, args=(folder,), daemon=True)
        thread.start()

    def _extract_all_thread(self, folder):
        self.log("Starting search & extract...")
        # 1) Find files
        targets = [name for name, _ in REQUIRED_ASSETS]
        results = asset_finder.multi_search(folder, targets, logger=self._log_callback)
        self.search_results = {targets[i]: results[i] for i in range(len(targets))}
        # populate extract_tree
        for i in self.extract_tree.get_children():
            self.extract_tree.delete(i)
        for k, v in self.search_results.items():
            if v:
                self.extract_tree.insert("", "end", values=(str(v['path']), v['size'], v['container']))
                self.log(f"Found {k}: {v['path']} ({v['size']} bytes) in {v['container']}")
            else:
                self.extract_tree.insert("", "end", values=(f"NOT FOUND: {k}", "-", "-"))
                self.log(f"Missing {k}")

        # 2) Extract: use UnityPy to extract TextAsset & MonoBehaviour content into output/extracted
        EXTRACTED.mkdir(parents=True, exist_ok=True)
        # If no found results, ask to use sample
        any_found = any(v for v in self.search_results.values())
        if not any_found:
            self.log("No files found in given folder. Use sample data if available.")
            return

        asset_files = [v['path'] for v in self.search_results.values() if v]
        # unpack_all_assets expects directories containing Unity asset files; for safety pass parent dirs
        # We'll iterate found file paths individually
        total = len(asset_files)
        self.set_progress(0, total)
        for idx, file_path in enumerate(asset_files, start=1):
            try:
                asset_unpacker.unpack_single_asset(Path(file_path), EXTRACTED, logger=self._log_callback)
            except Exception as e:
                self.log(f"Error extracting {file_path}: {e}")
            self.set_progress(idx)
        self.log("Extraction complete.")
        # After extraction, attempt to parse card list into Edit tab
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

    def _extract_single_thread(self, path):
        self.log(f"Extracting {path} ...")
        try:
            asset_unpacker.unpack_single_asset(path, self.extracted_folder, logger=self._log_callback)
            self.log("Done.")
        except Exception as e:
            self.log(f"Error: {e}")

    def _load_extracted(self, extracted_path):
        """
        Try to load parsed card JSONs from extracted_path (or sample).
        """
        self.log("Loading extracted data...")
        try:
            name_file = Path(extracted_path) / "CARD_Name.bytes.dec.json"
            desc_file = Path(extracted_path) / "CARD_Desc.bytes.dec.json"
            indx_file = Path(extracted_path) / "CARD_Indx.bytes.dec"
            if not name_file.exists() or not desc_file.exists():
                self.log("Name/Desc JSON files not found in extracted folder.")
                return
            self.card_names = card_parser.load_names(name_file)
            self.card_descs = card_parser.load_descs(desc_file)
            self.card_index = list(range(len(self.card_names)))
            self._populate_card_list()
            self.log(f"Loaded {len(self.card_names)} cards.")
        except Exception as e:
            self.log(f"Failed to load extracted data: {e}")

    def _load_extracted_sample(self, sample_folder):
        """
        Load included sample dataset for testing.
        """
        self._load_extracted(sample_folder)

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
        # get full index (the displayed index might be filtered)
        value = w.get(sel)
        idx = int(value.split("-")[0].strip())
        name = self.card_names[idx]
        desc = self.card_descs[idx] if idx < len(self.card_descs) else ""
        self.name_text.delete("1.0", "end")
        self.name_text.insert("1.0", name)
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", desc)

    def _save_changes(self):
        # Save current edited card back to changed JSON
        sel = self.card_listbox.curselection()
        if not sel:
            messagebox.showinfo("Select", "Select a card to save.")
            return
        sel_idx = sel[0]
        display = self.card_listbox.get(sel_idx)
        idx = int(display.split("-")[0].strip())
        new_name = self.name_text.get("1.0", "end").rstrip("\n")
        new_desc = self.desc_text.get("1.0", "end").rstrip("\n")
        self.card_names[idx] = new_name
        if idx < len(self.card_descs):
            self.card_descs[idx] = new_desc
        else:
            # pad
            while len(self.card_descs) <= idx:
                self.card_descs.append("")
            self.card_descs[idx] = new_desc

        # write changed outputs
        CHANGED.mkdir(parents=True, exist_ok=True)
        name_out = CHANGED / "CARD_Name.bytes.dec.json"
        desc_out = CHANGED / "CARD_Desc.bytes.dec.json"
        with open(name_out, "w", encoding="utf-8") as f:
            json.dump(self.card_names, f, ensure_ascii=False, indent=2)
        with open(desc_out, "w", encoding="utf-8") as f:
            json.dump(self.card_descs, f, ensure_ascii=False, indent=2)
        self.log(f"Saved changes for card {idx} to {CHANGED}")

    def _export_changed_json(self):
        # Export changed JSON files to user-chosen location
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
        # Build modded bytes files from changed JSON and other extracted assets
        out_folder = filedialog.askdirectory(title="Choose output folder for mod files")
        if not out_folder:
            return
        out_folder = Path(out_folder)
        thread = threading.Thread(target=self._build_mod_files_thread, args=(out_folder,), daemon=True)
        thread.start()

    def _build_mod_files_thread(self, out_folder):
        self.log("Starting build...")
        try:
            # Load changed JSON if any otherwise use extracted
            name_json = CHANGED / "CARD_Name.bytes.dec.json"
            desc_json = CHANGED / "CARD_Desc.bytes.dec.json"
            source_name = name_json if name_json.exists() else self.extracted_folder / "CARD_Name.bytes.dec.json"
            source_desc = desc_json if desc_json.exists() else self.extracted_folder / "CARD_Desc.bytes.dec.json"

            # Use card_parser to merge + encrypt index
            card_parser.build_and_encrypt(CARD_Name_json=source_name,
                                          CARD_Desc_json=source_desc,
                                          CARD_Indx_template=self.extracted_folder / "CARD_Indx.bytes.dec",
                                          out_folder=out_folder,
                                          logger=self._log_callback)
            # Re-embed WORD and Part and fontsetting if available
            # For simplicity, copy other extracted files to out_folder and encrypt WORD/Text/Part using encryptor
            utils.copy_folder(self.extracted_folder, out_folder, exclude_patterns=["CARD_Name.bytes.dec.json", "CARD_Desc.bytes.dec.json"])
            self.log("Build finished.")
            messagebox.showinfo("Done", f"Built mod files to {out_folder}")
        except Exception as e:
            self.log(f"Error during build: {e}")
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