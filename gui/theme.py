"""
Simple Tkinter styling (dark + blue)
"""
from tkinter import ttk

def apply_theme(root):
    style = ttk.Style(root)

    # Use clam for better control
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Colors
    bg = "#0f1724"        # dark blue/charcoal
    panel = "#0b1220"
    fg = "#E6EEF6"
    accent = "#3B82F6"    # blue
    muted = "#93C5FD"
    danger = "#EF4444"

    style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10))
    style.configure("TFrame", background=panel)
    style.configure("TLabel", background=panel, foreground=fg)
    style.configure("TButton", background=accent, foreground="white", relief="flat")
    style.map("TButton",
              background=[("active", "#1E40AF")])
    style.configure("Accent.TButton", background=accent, foreground="white")
    style.configure("Danger.TButton", background=danger, foreground="white")
    style.configure("TEntry", fieldbackground="#071225", foreground=fg)
    style.configure("TText", background="#071225", foreground=fg)
    style.configure("Treeview", background=panel, foreground=fg, fieldbackground=panel)
    style.configure("Treeview.Heading", background="#071225", foreground=fg)