#!/usr/bin/env python3
"""
md_text_mod_tool - revised full tool (entrypoint)

Run:
    python main.py
"""
import tkinter as tk
from gui.main_window import MainWindow
from gui.theme import apply_theme_light

def main():
    root = tk.Tk()
    root.title("MD Text Mod Tool")
    root.geometry("1160x760")
    apply_theme_light(root)
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()