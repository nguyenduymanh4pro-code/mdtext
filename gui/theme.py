"""
Light professional theme: white background with blue accents.
Applied before MainWindow is created.
"""
import tkinter as tk
from tkinter import ttk

def apply_theme_light(root):
    style = ttk.Style(root)
    # Use default motif if clam not available; clam gives better visuals
    try:
        style.theme_use("clam")
    except Exception:
        pass

    bg = "#f7fbff"
    panel = "#ffffff"
    accent = "#0b79d0"
    text = "#0b2233"
    entry_bg = "#ffffff"
    root.configure(bg=bg)

    style.configure(".", background=bg, foreground=text, font=("Segoe UI", 10))
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=text)
    style.configure("TButton", background=panel, foreground=text, borderwidth=1)
    style.map("TButton",
              background=[("active", "#e6f2fb")])
    style.configure("Accent.TButton", background=accent, foreground="white")
    style.configure("TEntry", fieldbackground=entry_bg, foreground=text)
    style.configure("Treeview", background=panel, fieldbackground=panel, foreground=text)
    style.configure("Treeview.Heading", background=accent, foreground="white")
    style.configure("TProgressbar", troughcolor="#e9f3fb", background=accent)