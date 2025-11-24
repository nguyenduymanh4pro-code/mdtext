#!/usr/bin/env python3
"""
Main GUI window (reworked):

- Replaced the Cards Treeview with a simpler, more reliable Listbox + Scrollbar.
  Listbox is less error-prone for selection and editing, easier to navigate and faster on large lists.
- Added a Search entry + Search button that filters the card list in-place.
- Added a vertical scrollbar for the card list.
- Reworked layout to a horizontal PanedWindow (left: card list & search; right: editor/effects)
  for a cleaner, more professional and resizable UI.
- Kept the Effects panel (Treeview) because it shows multi-column data (Sel/Idx/Effect).
- All existing functionality preserved (extract / build braced / edit / save / reload / export / build mod).
- Replaced all usages of the old cards Treeview selection APIs with the Listbox selection helpers.
- Kept robust braced-rebuild fallback, effect editing modal, copy/insert/replace behaviors.
"""
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import tkinter.font as tkfont
import json

from core.asset_finder import AssetFinder
from core.asset_unpacker import AssetUnpacker
from core.parser import CardModule
from core.encryptor import Encryptor
from core.utils import AppLogger, ensure_dirs, zip_folder
from core.brace_utils import count_top_level_braces, insert_braces
from core.part_parser import get_pidx_table, get_part_table
from core import build_braced

APP_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = APP_ROOT / "output"
SAMPLE_DIR = APP_ROOT / "assets" / "sample_pack"


class MainWindow(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill="both", expand=True)

        ensure_dirs(OUTPUT_ROOT)
        self.logger = AppLogger()
        self._setup_backend()
        self._build_ui()
        self.last_search_results = None

        # raw braced list loaded directly from file (unescaped, used for extracting effects)
        self._braced_raw: Optional[List[str]] = None
        # current segments/material used by the Effects Treeview
        self._current_segments: List[str] = []
        self._current_material: Optional[str] = None
        # checked state for effects rows (iid -> bool)
        self._checked_rows: Dict[str, bool] = {}

        # internal filtered index map: visible_list_index -> real card index
        self._visible_to_index: List[int] = []

    # ---------------- Backend setup ----------------
    def _setup_backend(self):
        self.finder = AssetFinder()
        self.unpacker = AssetUnpacker()
        self.cardmod = CardModule()
        self.encryptor = Encryptor()

        self.extracted = OUTPUT_ROOT / "extracted"
        self.changed = OUTPUT_ROOT / "changed"
        self.modded = OUTPUT_ROOT / "modded"
        ensure_dirs(self.extracted, self.changed, self.modded)

    # ---------------- UI building ----------------
    def _build_ui(self):
        # Top controls: folder selection
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=10)
        ttk.Label(top, text="Game 0000 folder:").pack(side="left")
        self.game_var = tk.StringVar()
        self.entry_game = ttk.Entry(top, textvariable=self.game_var, width=78)
        self.entry_game.pack(side="left", padx=8)
        ttk.Button(top, text="Browse", command=self._browse).pack(side="left")
        ttk.Button(top, text="Use Sample", command=self._use_sample).pack(side="left", padx=6)

        # Main area: PanedWindow with left = card list, right = editor + effects
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Left pane: search + listbox with scrollbar
        left_panel = ttk.Frame(paned, width=300)
        paned.add(left_panel, weight=1)

        search_row = ttk.Frame(left_panel)
        search_row.pack(fill="x", pady=(6, 6))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=(0,6))
        search_entry.bind("<Return>", lambda e: self.search_cards())
        ttk.Button(search_row, text="Search", command=self.search_cards).pack(side="left")
        ttk.Button(search_row, text="Clear", command=self._clear_search).pack(side="left", padx=(6,0))

        ttk.Label(left_panel, text="Cards").pack(anchor="w")
        listbox_frame = ttk.Frame(left_panel)
        listbox_frame.pack(fill="both", expand=True, pady=(6,0))

        # card listbox + scrollbar
        self.card_listbox = tk.Listbox(listbox_frame, activestyle="none", exportselection=False)
        self.card_listbox.pack(side="left", fill="both", expand=True)
        self.card_listbox.bind("<<ListboxSelect>>", self.on_select)
        self.card_listbox.bind("<Double-Button-1>", lambda e: self._focus_desc())

        card_scroll = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.card_listbox.yview)
        card_scroll.pack(side="right", fill="y")
        self.card_listbox.config(yscrollcommand=card_scroll.set)

        # Bottom-left quick actions
        left_bottom = ttk.Frame(left_panel)
        left_bottom.pack(fill="x", pady=(6, 6))
        ttk.Button(left_bottom, text="Refresh List", command=self._populate_card_list).pack(side="left")
        ttk.Button(left_bottom, text="Reload From Extracted", command=self.reload_from_extracted).pack(side="left", padx=6)

        # Right pane: editor and effects
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=3)

        # Name editor
        ttk.Label(right_panel, text="Name:").pack(anchor="nw")
        self.name_text = tk.Text(right_panel, height=2, wrap='word', font=("Segoe UI", 10))
        self.name_text.pack(fill="x", pady=(0,8))

        # Description header with show-braced
        desc_header = ttk.Frame(right_panel)
        desc_header.pack(fill="x", anchor="nw")
        ttk.Label(desc_header, text="Description:").pack(side="left")
        self.show_braced_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(desc_header, text="Show braced", variable=self.show_braced_var, command=self._toggle_braced).pack(side="left", padx=(8,0))
        ttk.Button(desc_header, text="Reset Description", command=self._reset_description).pack(side="right")

        # Description with scrollbar
        desc_frame = ttk.Frame(right_panel)
        desc_frame.pack(fill="both", expand=True)
        self.desc_text = tk.Text(desc_frame, height=14, wrap='word', font=("Segoe UI", 10))
        self.desc_text.pack(side="left", fill="both", expand=True)
        desc_scroll = ttk.Scrollbar(desc_frame, orient="vertical", command=self.desc_text.yview)
        desc_scroll.pack(side="right", fill="y")
        self.desc_text.config(yscrollcommand=desc_scroll.set)

        # Effects panel title
        ttk.Label(right_panel, text="Effects (top-level segments):").pack(anchor="nw", pady=(8,0))
        eff_frame = ttk.Frame(right_panel)
        eff_frame.pack(fill="both", expand=False)

        # Effects Treeview (Sel, Idx, Effect/Material)
        columns = ("sel", "idx", "effect")
        self.effects_tv = ttk.Treeview(eff_frame, columns=columns, show="headings", selectmode="browse", height=12)
        self.effects_tv.heading("sel", text="Sel")
        self.effects_tv.heading("idx", text="Idx")
        self.effects_tv.heading("effect", text="Effect / Material")
        self.effects_tv.column("sel", width=48, anchor="center")
        self.effects_tv.column("idx", width=48, anchor="center")
        self.effects_tv.column("effect", width=720, anchor="w")
        self.effects_tv.pack(side="left", fill="both", expand=True)

        eff_scroll = ttk.Scrollbar(eff_frame, orient="vertical", command=self.effects_tv.yview)
        eff_scroll.pack(side="right", fill="y")
        self.effects_tv.config(yscrollcommand=eff_scroll.set)

        # Effects interactions
        self.effects_tv.bind("<Button-1>", self._on_effects_click, add="+")
        self.effects_tv.bind("<ButtonRelease-1>", self._on_effects_select, add="+")
        self.effects_tv.bind("<Double-1>", lambda e: self._edit_selected_effect(), add="+")

        # Effects action buttons
        eff_btn_frame = ttk.Frame(right_panel)
        eff_btn_frame.pack(fill="x", pady=(8,6))
        ttk.Button(eff_btn_frame, text="Insert Selected Effect", command=self._insert_selected_effect).pack(side="left")
        ttk.Button(eff_btn_frame, text="Insert Material", command=self._insert_material).pack(side="left", padx=6)
        ttk.Button(eff_btn_frame, text="Edit Selected", command=self._edit_selected_effect).pack(side="left", padx=6)
        ttk.Button(eff_btn_frame, text="Copy Selected", command=self._copy_selected_effect).pack(side="left", padx=6)
        self.replace_effect_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(eff_btn_frame, text="Replace selected effect in description", variable=self.replace_effect_var).pack(side="left", padx=12)

        # Save / Export / Build buttons
        bottom_row = ttk.Frame(right_panel)
        bottom_row.pack(fill="x", pady=(8,6))
        ttk.Button(bottom_row, text="Save Change", command=self.save_change).pack(side="left")
        ttk.Button(bottom_row, text="Export Changed JSONs", command=self.export_changed_jsons).pack(side="left", padx=6)
        ttk.Button(bottom_row, text="Build Mod Files", command=self.build_mod_files).pack(side="right")

        # Status & log area
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=12, pady=(0,8))
        ttk.Label(status_frame, text="Status:").pack(side="left")
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left", padx=(6,0))

        ttk.Label(self, text="Log:").pack(anchor="w", padx=12)
        self.logbox = tk.Text(self, height=8)
        self.logbox.pack(fill="both", expand=False, padx=12, pady=(4,12))
        self.logger.set_widget(self.logbox)

        # Progress bar
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=12, pady=(0, 8))

        # Styling attempt
        style = ttk.Style()
        try:
            style.configure("Treeview", rowheight=20)
        except Exception:
            pass

    # ---------------- small helpers for card selection ----------------
    def _visible_count(self) -> int:
        return len(self._visible_to_index)

    def _get_selected_card_index(self) -> Optional[int]:
        """Return the actual card index corresponding to current selection in the Listbox, or None."""
        sel = self.card_listbox.curselection()
        if not sel:
            return None
        visible_idx = sel[0]
        if visible_idx < 0 or visible_idx >= len(self._visible_to_index):
            return None
        return self._visible_to_index[visible_idx]

    def _select_card_by_index(self, idx: int):
        """Select and scroll to the given real card index."""
        try:
            vis_idx = self._visible_to_index.index(idx)
        except ValueError:
            # not in current filtered list: rebuild full list then select
            self._clear_search()
            try:
                vis_idx = self._visible_to_index.index(idx)
            except Exception:
                return
        self.card_listbox.selection_clear(0, "end")
        self.card_listbox.selection_set(vis_idx)
        self.card_listbox.see(vis_idx)
        # Trigger update
        self.on_select(None)

    # ---------------- Thread-safe UI helpers ----------------
    def _ui_insert_assets(self, lines: List[str]):
        self.logger.log("Detected assets:")
        for s in lines:
            self.logger.log(s)

    def _ui_set_last_search(self, results):
        self.last_search_results = results

    def _start_activity(self, status_text: str):
        def _start():
            try:
                self.status_var.set(status_text)
                self.progress.config(mode="indeterminate")
                self.progress.start(10)
            except Exception:
                pass
        self.master.after(0, _start)

    def _stop_activity(self, idle_text: str = "Idle"):
        def _stop():
            try:
                self.progress.stop()
                self.progress.config(mode="determinate", value=0)
                self.status_var.set(idle_text)
            except Exception:
                pass
        self.master.after(0, _stop)

    # ---------------- Handlers ----------------
    def _browse(self):
        folder = filedialog.askdirectory(title="Select the game 0000 folder")
        if folder:
            self.game_var.set(folder)

    def _use_sample(self):
        sample = SAMPLE_DIR
        if not sample.exists():
            messagebox.showinfo("Sample missing", f"Sample data missing: {sample}")
            return
        self.game_var.set(str(sample))

    def find_files(self):
        path = self.game_var.get().strip()
        if not path:
            messagebox.showwarning("Missing folder", "Please select the 0000 folder first.")
            return

        self.logger.log("Searching assets...")

        def worker():
            try:
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
                items = self.finder.find_many(path, targets)
                lines = []
                for item in items:
                    lines.append(f"{item['name']} | path={item.get('path')} | size={item.get('size',0)}")
                self.master.after(0, self._ui_insert_assets, lines)
                self.master.after(0, self._ui_set_last_search, items)
                self.master.after(0, lambda: self.logger.log(f"Search finished. {len(items)} assets found."))
            except Exception as e:
                self.master.after(0, self.logger.log, f"Find files error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def extract_all(self):
        path = self.game_var.get().strip()
        if not path:
            messagebox.showwarning("Missing folder", "Please select the 0000 folder.")
            return

        self.logger.log("Starting extraction...")
        self.progress.config(mode="determinate", value=0)
        self.status_var.set("Extracting...")

        def worker():
            try:
                candidate_paths = []
                if self.last_search_results:
                    for it in self.last_search_results:
                        p = it.get("path")
                        if p:
                            candidate_paths.append(p)
                if candidate_paths:
                    self.master.after(0, self.logger.log, f"Extracting {len(candidate_paths)} candidate files (fast mode)...")
                    created = self.unpacker.unpack_from_paths(candidate_paths, str(self.extracted),
                                                             progress_callback=self._set_progress,
                                                             logger=self.logger)
                else:
                    self.master.after(0, self.logger.log, "No search results; doing full scan (slow)...")
                    created = self.unpacker.unpack_assets(path, str(self.extracted),
                                                          progress_callback=self._set_progress,
                                                          logger=self.logger)
                self.master.after(0, self.logger.log, f"Extraction finished ({len(created)} files).")

                try:
                    self.cardmod.load_from_folder(self.extracted)
                except Exception as e:
                    self.master.after(0, self.logger.log, f"Parse cards error: {e}")

                # load raw braced JSON (unescaped) for effects pane
                self._load_braced_raw()

                self._start_activity("Building braced descriptions...")
                try:
                    ok, msg = build_braced.build_braced(str(self.extracted))
                    self.master.after(0, self.logger.log, msg)
                    try:
                        self.cardmod.load_from_folder(self.extracted)
                    except Exception as e:
                        self.master.after(0, self.logger.log, f"Reload after braced error: {e}")
                    self._load_braced_raw()
                finally:
                    self._stop_activity("Idle")

                self.master.after(0, self._populate_card_list)
            except Exception as e:
                self.master.after(0, self.logger.log, f"Extraction error: {e}")
                self._stop_activity("Idle")
            finally:
                self._set_progress(0)

        threading.Thread(target=worker, daemon=True).start()

    def build_braced_btn(self):
        if not self.extracted.exists():
            messagebox.showwarning("Missing", f"Extracted folder not found: {self.extracted}")
            return

        self.logger.log("Building braced descriptions...")
        self._start_activity("Building braced descriptions...")

        def worker():
            try:
                ok, msg = build_braced.build_braced(str(self.extracted))
                self.master.after(0, self.logger.log, msg)
                if ok:
                    try:
                        self.cardmod.load_from_folder(self.extracted)
                        self._load_braced_raw()
                        self.master.after(0, self._populate_card_list)
                        self.master.after(0, lambda: messagebox.showinfo("Build Braced", "Braced JSON built and reloaded."))
                    except Exception as e:
                        self.master.after(0, self.logger.log, f"After build braced: reload error: {e}")
                else:
                    self.master.after(0, lambda: messagebox.showwarning("Build Braced", msg))
            except Exception as e:
                self.master.after(0, self.logger.log, f"Build braced error: {e}")
            finally:
                self._stop_activity("Idle")

        threading.Thread(target=worker, daemon=True).start()

    def _set_progress(self, v):
        try:
            def upd():
                try:
                    self.progress.config(mode="determinate")
                    self.progress["value"] = v
                except Exception:
                    pass
            self.master.after(0, upd)
        except Exception:
            pass

    # ---------------- Card list population & search ----------------
    def _populate_card_list(self, preserve_selection: bool = False):
        """Populate the listbox from cardmod.names. Keep optional preserved selection."""
        prev_idx = self._get_selected_card_index()
        self.card_listbox.delete(0, "end")
        self._visible_to_index = []
        for i, name in enumerate(self.cardmod.names):
            display = f"{i:05d}  {name}"
            self.card_listbox.insert("end", display)
            self._visible_to_index.append(i)
        if preserve_selection and prev_idx is not None:
            self._select_card_by_index(prev_idx)
        else:
            # Select first if available
            if self._visible_to_index:
                self.card_listbox.selection_set(0)
                self.card_listbox.see(0)
                self.on_select(None)

    def search_cards(self):
        q = self.search_var.get().lower().strip()
        # if empty, restore full list
        if not q:
            self._populate_card_list()
            return
        self.card_listbox.delete(0, "end")
        self._visible_to_index = []
        for idx, name in enumerate(self.cardmod.names):
            if q in name.lower() or q in str(idx):
                display = f"{idx:05d}  {name}"
                self.card_listbox.insert("end", display)
                self._visible_to_index.append(idx)
        if self._visible_to_index:
            self.card_listbox.selection_set(0)
            self.card_listbox.see(0)
            self.on_select(None)

    def _clear_search(self):
        self.search_var.set("")
        self._populate_card_list()

    # ---------------- Effects utilities (unchanged behavior, just uses _get_selected_card_index) ----------------
    def _load_braced_raw(self):
        braced_file = self.extracted / "CARD_Desc.bytes.dec.braced.json"
        if braced_file.exists():
            try:
                self._braced_raw = json.loads(braced_file.read_text(encoding="utf-8"))
                self.logger.log(f"Loaded raw braced JSON ({len(self._braced_raw)} entries).")
            except Exception as e:
                self._braced_raw = None
                self.logger.log(f"Failed to load raw braced JSON: {e}")
        else:
            self._braced_raw = None

    def _extract_top_level_segments(self, s: str) -> Tuple[Optional[str], List[str]]:
        if s is None:
            return None, []
        # detect material (text before first top-level brace)
        depth = 0
        material_text = None
        first_top = None
        for i, ch in enumerate(s):
            if ch == '{':
                if depth == 0:
                    first_top = i
                    break
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
        if first_top is not None and first_top > 0:
            candidate = s[:first_top].strip()
            if candidate:
                material_text = candidate
        res = []
        depth = 0
        cur = []
        for ch in s:
            if ch == '{':
                if depth == 0:
                    cur = []
                else:
                    cur.append(ch)
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0:
                        res.append(''.join(cur).strip())
                    else:
                        cur.append(ch)
                else:
                    pass
            else:
                if depth > 0:
                    cur.append(ch)
        return material_text, res

    def _try_rebuild_braced_for_index(self, idx: int) -> Optional[str]:
        pidx_path = self.extracted / "Card_Pidx.bytes.dec"
        part_path = self.extracted / "Card_Part.bytes.dec"
        if not pidx_path.exists() or not part_path.exists():
            return None
        try:
            pidx_table = get_pidx_table(pidx_path)
            part_table = get_part_table(part_path, pidx_table)
            parts = part_table[idx] if idx < len(part_table) else []
            raw_desc = self.cardmod.descs[idx] if idx < len(self.cardmod.descs) else ""
            rebuilt = insert_braces(raw_desc, parts)
            self.logger.log(f"Rebuilt braced for index {idx} using Card_Part/Card_Pidx (parts count={len(parts)}).")
            return rebuilt
        except Exception as e:
            self.logger.log(f"Failed to rebuild braced for index {idx}: {e}")
            return None

    def _render_effects(self, idx: int):
        # clear previous
        for iid in self.effects_tv.get_children():
            self.effects_tv.delete(iid)
        self._checked_rows.clear()
        self._current_segments = []
        self._current_material = None

        braced_src = None
        if self._braced_raw and idx < len(self._braced_raw):
            braced_src = self._braced_raw[idx]
        else:
            if hasattr(self.cardmod, "braced_descs") and idx < len(self.cardmod.braced_descs):
                b = self.cardmod.braced_descs[idx]
                braced_src = b.replace('\\"', '"')

        material_text = None
        segments: List[str] = []
        if braced_src:
            material_text, segments = self._extract_top_level_segments(braced_src)

        expected = None
        if hasattr(self.cardmod, "effect_counts") and idx < len(self.cardmod.effect_counts):
            expected = self.cardmod.effect_counts[idx]

        need_rebuild = False
        if expected is not None:
            if expected > 0 and len(segments) != expected:
                need_rebuild = True
        else:
            if not segments:
                need_rebuild = True

        if need_rebuild:
            rebuilt = self._try_rebuild_braced_for_index(idx)
            if rebuilt:
                mat2, seg2 = self._extract_top_level_segments(rebuilt)
                if seg2 and (expected is None or len(seg2) == expected or len(seg2) > len(segments)):
                    braced_src = rebuilt
                    material_text, segments = mat2, seg2
                    self.logger.log(f"Using rebuilt braced for card {idx} (effects={len(segments)}).")

        if not segments:
            raw_desc = self.cardmod.descs[idx] if idx < len(self.cardmod.descs) else ""
            parts = [p.strip() for p in raw_desc.replace('\r', '').split('\n') if p.strip()]
            if not parts:
                parts = [p.strip() + '.' for p in raw_desc.split('.') if p.strip()]
            segments = parts if parts else ["(no effect segments)"]

        self._current_segments = segments
        self._current_material = material_text

        # Insert material row if exists
        if material_text:
            display_material = material_text.replace('"', '\\"')
            iid = "mat"
            self.effects_tv.insert("", "end", iid=iid, values=("☐", "", display_material), tags=("material",))
            self._checked_rows[iid] = False

        for i, seg in enumerate(segments, start=1):
            display_effect_inner = seg.replace('"', '\\"')
            display_effect = "{" + display_effect_inner + "}"
            iid = f"e{i-1}"
            self.effects_tv.insert("", "end", iid=iid, values=("☐", str(i), display_effect), tags=("effect",))
            self._checked_rows[iid] = False

        try:
            self.effects_tv.tag_configure("material", background="#f8fff8", font=("Segoe UI", 10, "bold"))
            self.effects_tv.tag_configure("effect", background="#ffffff", font=("Consolas" if "Consolas" in tkfont.families() else "Segoe UI", 10))
        except Exception:
            pass

    def _refresh_effects_for_selected(self):
        idx = self._get_selected_card_index()
        if idx is None:
            return
        self._render_effects(idx)

    def _on_effects_click(self, event):
        row = self.effects_tv.identify_row(event.y)
        col = self.effects_tv.identify_column(event.x)
        if not row:
            return
        if col == "#1":
            current = self._checked_rows.get(row, False)
            new = not current
            self._checked_rows[row] = new
            symbol = "☑" if new else "☐"
            values = list(self.effects_tv.item(row, "values"))
            values[0] = symbol
            self.effects_tv.item(row, values=values)
            self.effects_tv.focus(row)
            self.effects_tv.selection_set(row)
            return "break"

    def _on_effects_select(self, event):
        row = self.effects_tv.identify_row(event.y)
        if row:
            self.effects_tv.focus(row)
            self.effects_tv.selection_set(row)
            try:
                self.effects_tv.see(row)
            except Exception:
                pass

    def _on_effects_double_click(self, event):
        row = self.effects_tv.identify_row(event.y)
        if not row:
            return
        self.effects_tv.focus(row)
        self.effects_tv.selection_set(row)
        self._edit_selected_effect()

    def _edit_selected_effect(self):
        focus = self.effects_tv.focus()
        if not focus:
            messagebox.showinfo("No selection", "Please select an effect or material to edit.")
            return

        if focus == "mat":
            current_text = self._current_material or ""
            is_material = True
        elif focus.startswith("e"):
            try:
                idx = int(focus[1:])
                current_text = self._current_segments[idx] if 0 <= idx < len(self._current_segments) else ""
                is_material = False
            except Exception:
                messagebox.showinfo("Invalid selection", "Could not determine which effect was selected.")
                return
        else:
            messagebox.showinfo("Invalid selection", "Please select a valid effect row.")
            return

        editor = tk.Toplevel(self.master)
        editor.title("Edit Effect" if not is_material else "Edit Material")
        editor.transient(self.master)
        editor.grab_set()
        editor.geometry("760x260")
        lbl = ttk.Label(editor, text="Edit the text below. For effects, edit the inner content (without surrounding braces).")
        lbl.pack(anchor="w", padx=8, pady=(8, 2))

        text_frame = ttk.Frame(editor)
        text_frame.pack(fill="both", expand=True, padx=8, pady=4)
        edit_text = tk.Text(text_frame, wrap='word', font=("Segoe UI", 10))
        edit_text.pack(side="left", fill="both", expand=True)
        edit_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=edit_text.yview)
        edit_scroll.pack(side="right", fill="y")
        edit_text.config(yscrollcommand=edit_scroll.set)
        edit_text.insert("1.0", current_text)

        btn_frame = ttk.Frame(editor)
        btn_frame.pack(fill="x", pady=(6, 8), padx=8)
        def on_save():
            new_raw = edit_text.get("1.0", "end-1c")
            if not is_material:
                if '{' in new_raw or '}' in new_raw:
                    ok = messagebox.askyesno("Braces in effect?", "You included '{' or '}' inside the effect inner text. These characters may break braced structure. Do you want to keep them?")
                    if not ok:
                        return
            if is_material:
                self._current_material = new_raw
                display_material = new_raw.replace('"', '\\"')
                try:
                    if "mat" in self.effects_tv.get_children():
                        values = list(self.effects_tv.item("mat", "values"))
                        if len(values) >= 3:
                            values[2] = display_material
                            self.effects_tv.item("mat", values=values)
                        else:
                            idx = self._get_selected_card_index()
                            if idx is not None:
                                self._render_effects(idx)
                    else:
                        idx = self._get_selected_card_index()
                        if idx is not None:
                            self._render_effects(idx)
                except Exception:
                    idx = self._get_selected_card_index()
                    if idx is not None:
                        self._render_effects(idx)
            else:
                try:
                    idx = int(focus[1:])
                    if 0 <= idx < len(self._current_segments):
                        self._current_segments[idx] = new_raw
                        display_effect_inner = new_raw.replace('"', '\\"')
                        display_effect = "{" + display_effect_inner + "}"
                        iid = focus
                        values = list(self.effects_tv.item(iid, "values"))
                        if len(values) >= 3:
                            values[2] = display_effect
                            self.effects_tv.item(iid, values=values)
                        else:
                            sel_idx = self._get_selected_card_index()
                            if sel_idx is not None:
                                self._render_effects(sel_idx)
                except Exception:
                    sel_idx = self._get_selected_card_index()
                    if sel_idx is not None:
                        self._render_effects(sel_idx)
            editor.grab_release()
            editor.destroy()
            self.logger.log("Edited effect/material in panel (in-memory only). Use Insert or Save Change to apply.")

        ttk.Button(btn_frame, text="Save Edit", command=on_save).pack(side="left")
        ttk.Button(btn_frame, text="Cancel", command=lambda: (editor.grab_release(), editor.destroy())).pack(side="left", padx=6)
        editor.bind_all("<Control-s>", lambda e=None: (on_save(), "break"))
        editor.wait_window()

    def _get_checked_effects(self) -> List[Tuple[int, str]]:
        checked = []
        for iid, checked_flag in self._checked_rows.items():
            if not checked_flag:
                continue
            if iid == "mat":
                if self._current_material:
                    checked.append((-1, self._current_material))
            elif iid.startswith("e"):
                try:
                    idx = int(iid[1:])
                    if 0 <= idx < len(self._current_segments):
                        checked.append((idx, self._current_segments[idx]))
                except Exception:
                    pass
        return checked

    def _insert_material_into_description(self, description_text: str, material_text: str) -> str:
        if description_text is None:
            description_text = ""
        idx = description_text.find('{')
        if idx == -1:
            if description_text.strip():
                return material_text + " " + description_text
            else:
                return material_text
        else:
            return material_text + description_text[idx:]

    def _insert_selected_effect(self):
        idx = self._get_selected_card_index()
        if idx is None:
            messagebox.showinfo("No card", "Please select a card first.")
            return

        checked = self._get_checked_effects()
        if not checked:
            focus = self.effects_tv.focus()
            if focus:
                if focus == "mat":
                    if self._current_material:
                        checked = [(-1, self._current_material)]
                elif focus.startswith("e"):
                    try:
                        j = int(focus[1:])
                        checked = [(j, self._current_segments[j])]
                    except Exception:
                        pass

        if not checked:
            messagebox.showinfo("No effect", "Please check/select an effect row in the Effects panel.")
            return

        if self.replace_effect_var.get() and self.show_braced_var.get():
            full = self.desc_text.get("1.0", "end-1c")
            if not full:
                messagebox.showinfo("No description", "Description is empty; cannot replace.")
                return
            brace_positions = []
            depth = 0
            start_pos = None
            for i, ch in enumerate(full):
                if ch == '{':
                    if depth == 0:
                        start_pos = i
                    depth += 1
                elif ch == '}':
                    if depth > 0:
                        depth -= 1
                        if depth == 0 and start_pos is not None:
                            brace_positions.append((start_pos, i))
                            start_pos = None
            new_full = full
            replacements = []
            for seg_idx, seg_text in checked:
                if seg_idx == -1:
                    if self._current_material:
                        first_brace = new_full.find('{')
                        if first_brace == -1:
                            new_full = self._current_material + (" " + new_full if new_full.strip() else "")
                        else:
                            new_full = self._current_material + new_full[first_brace:]
                        replacements.append(("material", self._current_material))
            numeric_repls = [(seg_idx, seg_text) for seg_idx, seg_text in checked if seg_idx != -1]
            if numeric_repls:
                numeric_repls_sorted = sorted(numeric_repls, key=lambda x: x[0], reverse=True)
                for seg_idx, seg_text in numeric_repls_sorted:
                    brace_positions_tmp = []
                    depth = 0
                    start_pos = None
                    for i, ch in enumerate(new_full):
                        if ch == '{':
                            if depth == 0:
                                start_pos = i
                            depth += 1
                        elif ch == '}':
                            if depth > 0:
                                depth -= 1
                                if depth == 0 and start_pos is not None:
                                    brace_positions_tmp.append((start_pos, i))
                                    start_pos = None
                    if seg_idx < 0 or seg_idx >= len(brace_positions_tmp):
                        messagebox.showinfo("Replace failed", f"Effect {seg_idx+1} cannot be located in the current description; skipping.")
                        continue
                    s_byte, e_byte = brace_positions_tmp[seg_idx]
                    new_inner = seg_text.replace('"', '\\"')
                    new_full = new_full[:s_byte+1] + new_inner + new_full[e_byte:]
                    replacements.append((seg_idx+1, new_inner))
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", new_full)
            self.logger.log(f"Replaced checked effects for card {idx}; replacements: {replacements}")
            self._render_effects(idx)
            return

        insert_texts = []
        for seg_idx, seg_text in checked:
            if seg_idx == -1:
                insert_texts.append(seg_text)
            else:
                if self.show_braced_var.get():
                    inner = seg_text.replace('"', '\\"')
                    insert_texts.append("{" + inner + "}")
                else:
                    insert_texts.append(seg_text)
        insert_str = " ".join(insert_texts)
        try:
            self.desc_text.insert("insert", insert_str)
            self.logger.log(f"Inserted checked effect(s) into description for card {idx}")
        except Exception as e:
            self.logger.log(f"Failed to insert effect(s): {e}")

    def _insert_material(self):
        idx = self._get_selected_card_index()
        if idx is None:
            messagebox.showinfo("No card", "Please select a card first.")
            return
        checked = self._get_checked_effects()
        material = None
        for seg_idx, seg_text in checked:
            if seg_idx == -1:
                material = seg_text
                break
        if material is None:
            material = self._current_material
        if material is None:
            messagebox.showinfo("No material", "No material text available for this card.")
            return
        full = self.desc_text.get("1.0", "end-1c")
        if self.show_braced_var.get():
            new_full = self._insert_material_into_description(full, material)
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", new_full)
            self.logger.log(f"Inserted/Replaced material into braced description for card {idx}")
            self._render_effects(idx)
        else:
            try:
                self.desc_text.insert("insert", material + " ")
                self.logger.log(f"Inserted material into unbraced description for card {idx}")
            except Exception as e:
                self.logger.log(f"Failed to insert material: {e}")

    def _get_checked_effect_text(self) -> Optional[str]:
        checked = self._get_checked_effects()
        if not checked:
            focus = self.effects_tv.focus()
            if focus:
                if focus == "mat":
                    return self._current_material
                elif focus.startswith("e"):
                    try:
                        j = int(focus[1:])
                        return self._current_segments[j]
                    except Exception:
                        return None
            return None
        return checked[0][1]

    def _copy_selected_effect(self):
        text = self._get_checked_effect_text()
        if not text:
            messagebox.showinfo("No effect", "Please select an effect to copy.")
            return
        try:
            try:
                import clipboard as _clipboard_module
                _clipboard_module.copy(text)
            except Exception:
                self.master.clipboard_clear()
                self.master.clipboard_append(text)
        except Exception:
            messagebox.showwarning("Clipboard failed", "Could not copy to clipboard.")
            return
        self.logger.log("Copied selected effect to clipboard.")

    # ---------------- Selection handlers & description/braced sync ----------------
    def on_select(self, event):
        idx = self._get_selected_card_index()
        if idx is None:
            return

        name = self.cardmod.names[idx] if idx < len(self.cardmod.names) else ""
        desc = self.cardmod.descs[idx] if idx < len(self.cardmod.descs) else ""
        braced_available = hasattr(self.cardmod, "braced_descs") and idx < len(self.cardmod.braced_descs)

        self.name_text.delete("1.0", "end")
        self.name_text.insert("1.0", name)

        expected = 0
        if hasattr(self.cardmod, "effect_counts") and idx < len(self.cardmod.effect_counts):
            expected = self.cardmod.effect_counts[idx]
        # show count
        try:
            self.effect_count_var.set(f"Effects: {expected}")
        except Exception:
            # sometimes effect_count_var might not exist yet (older UI); safe guard
            pass

        if self.show_braced_var.get() and braced_available:
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", self.cardmod.braced_descs[idx])
        else:
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", desc)

        self._render_effects(idx)

    def _focus_desc(self):
        """Focus description text area (used on double-click)."""
        try:
            self.desc_text.focus_set()
        except Exception:
            pass

    def _toggle_braced(self):
        idx = self._get_selected_card_index()
        if idx is None:
            # just flip variable (already flipped) and do nothing
            return
        braced_available = hasattr(self.cardmod, "braced_descs") and idx < len(self.cardmod.braced_descs)
        if self.show_braced_var.get():
            if braced_available:
                self.desc_text.delete("1.0", "end")
                self.desc_text.insert("1.0", self.cardmod.braced_descs[idx])
            else:
                messagebox.showinfo("No braced data", "Braced descriptions not available for this dataset.")
                self.show_braced_var.set(False)
        else:
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", self.cardmod.descs[idx] if idx < len(self.cardmod.descs) else "")

    def _reset_description(self):
        idx = self._get_selected_card_index()
        if idx is None:
            messagebox.showinfo("No card", "Please select a card first.")
            return
        if self.show_braced_var.get() and hasattr(self.cardmod, "braced_descs") and idx < len(self.cardmod.braced_descs):
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", self.cardmod.braced_descs[idx])
        else:
            self.desc_text.delete("1.0", "end")
            self.desc_text.insert("1.0", self.cardmod.descs[idx] if idx < len(self.cardmod.descs) else "")
        self.logger.log(f"Description reset for card {idx}")

    def save_change(self):
        idx = self._get_selected_card_index()
        if idx is None:
            messagebox.showinfo("No card", "Please select a card to save change.")
            return
        new_name = self.name_text.get("1.0", "end").strip()
        new_desc_raw = self.desc_text.get("1.0", "end").rstrip("\n")
        expected = self.cardmod.effect_counts[idx] if hasattr(self.cardmod, "effect_counts") and idx < len(self.cardmod.effect_counts) else 0

        if self.show_braced_var.get():
            user_effects = count_top_level_braces(new_desc_raw)
            if user_effects != expected:
                ok = messagebox.askyesno("Effect count mismatch",
                                         f"The edited braced text contains {user_effects} effect(s), but original expects {expected}.\n"
                                         "Saving may break part table mapping. Do you still want to save?")
                if not ok:
                    return
            new_desc_unbraced = new_desc_raw.replace("{", "").replace("}", "")
            self.cardmod.descs[idx] = new_desc_unbraced
        else:
            if "{" in new_desc_raw or "}" in new_desc_raw:
                ok = messagebox.askyesno("Braces detected",
                                         "You edited the unbraced view but included '{' or '}' characters. These may be treated as literal characters.\n"
                                         "Do you want to continue saving (braces will be kept) or cancel and edit again?")
                if not ok:
                    return
            self.cardmod.descs[idx] = new_desc_raw

        self.cardmod.names[idx] = new_name
        self.cardmod.write_changed(self.changed)
        self.logger.log(f"Saved change for ID {idx}")
        # refresh list and keep selection
        self._populate_card_list(preserve_selection=True)

    def reload_from_extracted(self):
        try:
            self.cardmod.load_from_folder(self.extracted)
            self._load_braced_raw()
            self._populate_card_list()
            self.logger.log("Reloaded data from extracted.")
        except Exception as e:
            self.logger.log(f"Reload error: {e}")

    def export_changed_jsons(self):
        try:
            self.cardmod.write_changed(self.changed)
            self.logger.log(f"Exported changed JSONs to {self.changed}")
            messagebox.showinfo("Exported", f"Exported changed JSONs to:\n{self.changed}")
        except Exception as e:
            self.logger.log(f"Export changed error: {e}")

    def build_mod_files(self):
        out_dir = filedialog.askdirectory(title="Select output folder for mod files")
        if not out_dir:
            return
        out_dir = Path(out_dir)
        self.logger.log("Starting build...")

        def task():
            try:
                self.cardmod.write_changed(self.changed)
                self.encryptor.build_mod(
                    self.extracted,
                    self.changed,
                    self.modded,
                    logger=self.logger,
                    progress_callback=self._set_progress
                )
                import shutil
                shutil.copytree(self.modded, out_dir, dirs_exist_ok=True)
                self.master.after(0, self.logger.log, f"Build finished. Mod files in {out_dir}")
                self.master.after(0, lambda: messagebox.showinfo("Build finished", f"Mod files exported to:\n{out_dir}"))
            except Exception as e:
                self.master.after(0, self.logger.log, f"Error during build: {e}")

        threading.Thread(target=task, daemon=True).start()

    def export_mod_zip(self):
        dest = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("Zip files", "*.zip")], title="Save mod zip")
        if not dest:
            return
        try:
            zip_folder(str(self.modded), dest)
            self.logger.log(f"Exported mod zip to {dest}")
            messagebox.showinfo("Exported", f"Exported mod zip to:\n{dest}")
        except Exception as e:
            self.logger.log(f"Error exporting zip: {e}")