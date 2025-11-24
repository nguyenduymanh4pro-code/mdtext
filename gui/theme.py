"""
Light theme for the GUI: white background with soft light-blue accents.
"""
from tkinter import ttk

def apply_theme(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    bg = "#FFFFFF"        # white
    panel = "#F7FAFF"     # very light blue/white
    fg = "#0B1724"        # dark text
    accent = "#4da6ff"    # light blue accent
    muted = "#9BCBFF"
    danger = "#D9534F"

    style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10))
    style.configure("TFrame", background=panel)
    style.configure("TLabel", background=panel, foreground=fg)
    style.configure("TButton", background=accent, foreground="white", relief="flat")
    style.map("TButton",
              background=[("active", "#2D8CFF")])
    style.configure("Accent.TButton", background=accent, foreground="white")
    style.configure("Danger.TButton", background=danger, foreground="white")
    style.configure("TEntry", fieldbackground="#FFFFFF", foreground=fg)
    style.configure("TText", background="#FFFFFF", foreground=fg)
    style.configure("Treeview", background=panel, foreground=fg, fieldbackground=panel)
    style.configure("Treeview.Heading", background="#E6F3FF", foreground=fg)
