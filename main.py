#!/usr/bin/env python3
"""
md_text_mod_tool - entrypoint

Usage:
    python main.py
"""
import sys
from gui.main_window import MainWindow
import tkinter as tk

def main():
    root = tk.Tk()
    root.title("MD Text Mod Tool")
    root.geometry("1100x720")
    app = MainWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()