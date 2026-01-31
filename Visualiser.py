#!/usr/bin/env python3
"""
Visualiser_GUI.py
=================

A simple GUI tool to:
- Load a tab-separated dataset (optionally .gz)
- Preview the dataset to verify it's correct
- Choose which column is the "ID" (row identifier) column
- Select multiple Row IDs (checkboxes + search)
- Create custom groups and assign sample/value columns to each group (checkboxes)
- Plot:
    * X-axis = groups
    * Each sample column is a DIFFERENT COLOR within the group
    * Each Row ID is a DIFFERENT MARKER SHAPE
    * Two legends on the side:
        - Samples legend (colors)
        - Row IDs legend (marker shapes)
- NEW: User can type:
    * Plot Title
    * X-axis label
    * Y-axis label

Run:
    python Visualiser_GUI.py
"""

# ============================================================
# 1) Imports
# ============================================================

import os
import glob
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


# ============================================================
# 2) Small helper functions
# ============================================================

def detect_id_column(columns):
    """
    Try to guess which column is the ID column.
    If we can't guess, return the first column.
    """
    likely_names = {
        "id", "ids", "name", "names", "symbol",
        "gene", "genes", "gene_symbol", "gene symbol",
        "ensembl", "ensembl_id", "row", "rowid", "row_id"
    }
    for c in columns:
        if str(c).strip().lower() in likely_names:
            return c
    return columns[0]


def to_float_list(values):
    """
    Convert values to floats, remove non-numeric (NaN).

    Returns:
        list[float]
    """
    s = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    return s.astype(float).tolist()


# ============================================================
# 3) Scrollable frame (for many checkboxes)
# ============================================================

class ScrollableFrame(ttk.Frame):
    """
    A simple "scrollable frame" widget:
    - Canvas + inner Frame + Scrollbar
    """
    def __init__(self, parent, height=300):
        super().__init__(parent)

        self.canvas = tk.Canvas(self, height=height, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")


# ============================================================
# 4) Main GUI application
# ============================================================

class TableVisualiserApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Window basics
        self.title("Interactive Table Visualiser By Aya Yacoub")
        self.geometry("1560x900")

        # ---- Dataset storage
        self.df = None
        self.id_col = None
        self.value_cols = []
        self.id_list_all = []

        # ---- Row ID selection (checkboxes)
        self.id_vars = {}            # row_id -> BooleanVar
        self.max_ids_shown = 250

        # ---- Groups storage
        self.groups = {}             # group_name -> {"col_vars": {col: BooleanVar}}
        self.active_group = None

        # ---- Marker shapes (for Row IDs)
        self.id_markers = ["o", "s", "^", "D", "v", "P", "X", "*", "<", ">", "h", "H", "8", "p"]

        # ---- Plot state
        self.last_fig = None
        self.preview_win = None

        self.build_ui()

    # ========================================================
    # UI layout
    # ========================================================

    def build_ui(self):
        # ---------------- Top toolbar ----------------
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Dataset:").pack(side="left")
        self.file_var = tk.StringVar(value="No file loaded")
        ttk.Label(top, textvariable=self.file_var).pack(side="left", padx=(6, 12))

        ttk.Button(top, text="Select Dataset File...", command=self.select_file).pack(side="left")
        ttk.Button(top, text="Auto-detect .gz in folder", command=self.autodetect_file).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Preview Dataset", command=self.preview_dataset).pack(side="left", padx=(8, 0))

        ttk.Separator(self).pack(fill="x", padx=10, pady=(0, 8))

        # ---------------- Main layout: 3 columns ----------------
        main = ttk.Frame(self, padding=(10, 0, 10, 10))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=3)
        main.columnconfigure(2, weight=1)

        # ---------------- Left panel: Row IDs ----------------
        ids_panel = ttk.LabelFrame(main, text="1) Row IDs (select multiple)", padding=10)
        ids_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        idcol_frame = ttk.Frame(ids_panel)
        idcol_frame.pack(fill="x")
        ttk.Label(idcol_frame, text="ID column:").pack(side="left")
        self.idcol_var = tk.StringVar(value="(none)")
        self.idcol_combo = ttk.Combobox(idcol_frame, textvariable=self.idcol_var, state="readonly")
        self.idcol_combo.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.idcol_combo.bind("<<ComboboxSelected>>", lambda e: self.on_id_column_changed())

        ttk.Label(ids_panel, text="Search Row IDs (contains):").pack(anchor="w", pady=(10, 0))
        self.id_search_var = tk.StringVar()
        self.id_search_var.trace_add("write", lambda *_: self.refresh_id_checkboxes())
        ttk.Entry(ids_panel, textvariable=self.id_search_var).pack(fill="x", pady=(4, 8))

        btn_row = ttk.Frame(ids_panel)
        btn_row.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_row, text="Select all shown", command=self.select_all_shown_ids).pack(side="left")
        ttk.Button(btn_row, text="Clear shown", command=self.clear_all_shown_ids).pack(side="left", padx=(6, 0))
        ttk.Label(btn_row, text=f"(max {self.max_ids_shown})").pack(side="right")

        self.ids_scroll = ScrollableFrame(ids_panel, height=610)
        self.ids_scroll.pack(fill="both", expand=True)

        self.ids_info_var = tk.StringVar(value="Load a dataset to populate Row IDs.")
        ttk.Label(ids_panel, textvariable=self.ids_info_var).pack(anchor="w", pady=(8, 0))

        # ---------------- Middle panel: Groups ----------------
        groups_panel = ttk.LabelFrame(main, text="2) Groups (assign sample columns)", padding=10)
        groups_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))

        group_top = ttk.Frame(groups_panel)
        group_top.pack(fill="x")

        ttk.Label(group_top, text="Groups:").pack(side="left")
        self.group_listbox = tk.Listbox(group_top, height=6, exportselection=False)
        self.group_listbox.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.group_listbox.bind("<<ListboxSelect>>", lambda e: self.on_group_select())

        grp_btns = ttk.Frame(group_top)
        grp_btns.pack(side="left", fill="y")
        ttk.Button(grp_btns, text="Add Group", command=self.add_group).pack(fill="x")
        ttk.Button(grp_btns, text="Rename", command=self.rename_group).pack(fill="x", pady=(6, 0))
        ttk.Button(grp_btns, text="Remove", command=self.remove_group).pack(fill="x", pady=(6, 0))

        ttk.Separator(groups_panel).pack(fill="x", pady=10)

        self.active_group_var = tk.StringVar(value="Active group: (none)")
        ttk.Label(groups_panel, textvariable=self.active_group_var).pack(anchor="w")

        col_btn_row = ttk.Frame(groups_panel)
        col_btn_row.pack(fill="x", pady=(6, 6))
        ttk.Button(col_btn_row, text="Select all columns", command=self.select_all_cols_in_group).pack(side="left")
        ttk.Button(col_btn_row, text="Clear all columns", command=self.clear_all_cols_in_group).pack(side="left", padx=(6, 0))

        self.group_cols_scroll = ScrollableFrame(groups_panel, height=545)
        self.group_cols_scroll.pack(fill="both", expand=True)

        self.cols_info_var = tk.StringVar(value="Load a dataset to assign columns to groups.")
        ttk.Label(groups_panel, textvariable=self.cols_info_var).pack(anchor="w", pady=(8, 0))

        # ---------------- Right panel: Plot controls ----------------
        plot_panel = ttk.LabelFrame(main, text="3) Plot options", padding=10)
        plot_panel.grid(row=0, column=2, sticky="nsew")

        # ----- NEW: custom plot titles -----
        ttk.Label(plot_panel, text="Plot title:").pack(anchor="w")
        self.plot_title_var = tk.StringVar(value="My Plot")
        ttk.Entry(plot_panel, textvariable=self.plot_title_var).pack(fill="x", pady=(2, 8))

        ttk.Label(plot_panel, text="X-axis label:").pack(anchor="w")
        self.x_label_var = tk.StringVar(value="Groups")
        ttk.Entry(plot_panel, textvariable=self.x_label_var).pack(fill="x", pady=(2, 8))

        ttk.Label(plot_panel, text="Y-axis label:").pack(anchor="w")
        self.y_label_var = tk.StringVar(value="Value")
        ttk.Entry(plot_panel, textvariable=self.y_label_var).pack(fill="x", pady=(2, 10))

        # ----- jitter + other options -----
        self.jitter_alpha = tk.DoubleVar(value=0.80)
        self.jitter_width = tk.DoubleVar(value=0.06)
        self.show_grid = tk.BooleanVar(value=True)
        self.rotate_xticks = tk.BooleanVar(value=True)

        row1 = ttk.Frame(plot_panel)
        row1.pack(fill="x", pady=(6, 0))
        ttk.Label(row1, text="Jitter alpha").pack(side="left")
        ttk.Scale(row1, from_=0.2, to=1.0, variable=self.jitter_alpha, orient="horizontal").pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

        row2 = ttk.Frame(plot_panel)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Jitter width").pack(side="left")
        ttk.Scale(row2, from_=0.01, to=0.25, variable=self.jitter_width, orient="horizontal").pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )

        ttk.Checkbutton(plot_panel, text="Show grid", variable=self.show_grid).pack(anchor="w", pady=(10, 0))
        ttk.Checkbutton(plot_panel, text="Rotate group labels", variable=self.rotate_xticks).pack(anchor="w")

        ttk.Separator(plot_panel).pack(fill="x", pady=10)

        ttk.Button(plot_panel, text="Plot Box + Jitter", command=self.plot).pack(anchor="w", fill="x")
        ttk.Button(plot_panel, text="Save Plot as PNG...", command=self.save_plot).pack(anchor="w", fill="x", pady=(6, 0))

        ttk.Separator(plot_panel).pack(fill="x", pady=10)

        ttk.Button(plot_panel, text="Export Groups...", command=self.export_groups).pack(anchor="w", fill="x")
        ttk.Button(plot_panel, text="Exit", command=self.destroy).pack(anchor="w", fill="x", pady=(6, 0))

        # ---------------- Status bar ----------------
        self.status_var = tk.StringVar(value="Load a dataset to begin.")
        status = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=6)
        status.pack(fill="x", side="bottom")

    # ========================================================
    # File loading
    # ========================================================

    def select_file(self):
        path = filedialog.askopenfilename(
            title="Select tab-separated dataset (optionally gzipped)",
            filetypes=[
                ("GZipped files", "*.gz"),
                ("Tab-separated", "*.tab *.tsv *.txt"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.load_dataset(path)

    def autodetect_file(self):
        candidates = glob.glob("*.tab.gz") + glob.glob("*.tsv.gz") + glob.glob("*.txt.gz") + glob.glob("*.gz")
        if not candidates:
            messagebox.showinfo("Auto-detect", "No .gz files found in the current folder.")
            return
        path = sorted(candidates, key=len)[0]
        self.load_dataset(path)

    def load_dataset(self, path):
        self.file_var.set(os.path.basename(path))
        self.status_var.set("Loading dataset...")

        def worker():
            try:
                compression = "gzip" if path.lower().endswith(".gz") else None
                df = pd.read_csv(path, sep="\t", compression=compression)

                if df.shape[1] < 2:
                    raise ValueError("Dataset must have at least 2 columns (ID + values).")

                id_col = detect_id_column(df.columns)
                value_cols = [c for c in df.columns if c != id_col]

                self.df = df
                self.id_col = id_col
                self.value_cols = value_cols
                self.id_list_all = df[id_col].astype(str).tolist()

                self.after(0, lambda: self.after_load_success(path))
            except Exception as e:
                self.after(0, lambda: self.after_load_error(path, e))

        threading.Thread(target=worker, daemon=True).start()

    def after_load_success(self, path):
        self.status_var.set(
            f"Loaded: {os.path.basename(path)} | rows={self.df.shape[0]} cols={self.df.shape[1]} | ID col={self.id_col}"
        )

        self.idcol_combo["values"] = list(self.df.columns)
        self.idcol_var.set(self.id_col)

        self.id_search_var.set("")
        self.refresh_id_checkboxes()
        self.ids_info_var.set(f"Select Row IDs. Total: {len(self.id_list_all)}")

        # Reset groups
        self.groups.clear()
        self.group_listbox.delete(0, tk.END)
        self.active_group = None
        self.active_group_var.set("Active group: (none)")
        self.render_active_group_columns(clear=True)

        # Starter groups
        self.create_group("Group 1")
        self.create_group("Group 2")
        self.select_group_by_index(0)

        self.cols_info_var.set(f"Value columns: {len(self.value_cols)}. Assign columns to groups.")

        self.preview_dataset()

    def after_load_error(self, path, error):
        self.status_var.set("Failed to load dataset.")
        messagebox.showerror("Load error", f"Could not load:\n{path}\n\nError:\n{error}")

    # ========================================================
    # Preview window
    # ========================================================

    def preview_dataset(self):
        if self.df is None:
            messagebox.showinfo("No dataset", "Load a dataset first.")
            return

        if self.preview_win is not None and self.preview_win.winfo_exists():
            self.preview_win.lift()
            return

        win = tk.Toplevel(self)
        win.title("Dataset Preview")
        win.geometry("1160x560")
        self.preview_win = win

        header = ttk.Frame(win, padding=10)
        header.pack(fill="x")

        info = (
            f"File: {self.file_var.get()} | Shape: {self.df.shape[0]} × {self.df.shape[1]} | "
            f"ID column: {self.id_col} | Value columns: {len(self.value_cols)}"
        )
        ttk.Label(header, text=info).pack(anchor="w")

        ctrl = ttk.Frame(win, padding=(10, 0, 10, 10))
        ctrl.pack(fill="x")

        ttk.Label(ctrl, text="Rows:").pack(side="left")
        rows_var = tk.IntVar(value=15)
        ttk.Spinbox(ctrl, from_=5, to=200, textvariable=rows_var, width=6).pack(side="left", padx=(6, 12))

        ttk.Label(ctrl, text="Columns:").pack(side="left")
        cols_var = tk.IntVar(value=12)
        ttk.Spinbox(ctrl, from_=2, to=60, textvariable=cols_var, width=6).pack(side="left", padx=(6, 12))

        table_frame = ttk.Frame(win, padding=10)
        table_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(table_frame, show="headings")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        xscroll.pack(side="bottom", fill="x")

        def render():
            nrows = rows_var.get()
            ncols = cols_var.get()
            cols = [self.id_col] + [c for c in self.df.columns if c != self.id_col][: max(1, ncols - 1)]
            preview = self.df.loc[: nrows - 1, cols].copy()

            tree.delete(*tree.get_children())
            tree["columns"] = cols

            for c in cols:
                tree.heading(c, text=str(c))
                tree.column(c, width=170, anchor="w")

            for _, row in preview.iterrows():
                tree.insert("", "end", values=[str(row[c]) for c in cols])

        ttk.Button(ctrl, text="Refresh Preview", command=render).pack(side="left")
        ttk.Button(ctrl, text="Close", command=win.destroy).pack(side="right")

        render()

    # ========================================================
    # Row ID checkboxes
    # ========================================================

    def refresh_id_checkboxes(self):
        if self.df is None:
            return

        query = self.id_search_var.get().strip().lower()

        for w in self.ids_scroll.inner.winfo_children():
            w.destroy()

        shown = []
        if not query:
            shown = self.id_list_all[: self.max_ids_shown]
        else:
            for rid in self.id_list_all:
                if query in rid.lower():
                    shown.append(rid)
                    if len(shown) >= self.max_ids_shown:
                        break

        for rid in shown:
            if rid not in self.id_vars:
                self.id_vars[rid] = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(self.ids_scroll.inner, text=rid, variable=self.id_vars[rid])
            cb.pack(anchor="w")

        self.ids_info_var.set(f"Showing {len(shown)} IDs (search to filter).")

    def select_all_shown_ids(self):
        for child in self.ids_scroll.inner.winfo_children():
            if isinstance(child, ttk.Checkbutton):
                rid = child.cget("text")
                self.id_vars[rid].set(True)

    def clear_all_shown_ids(self):
        for child in self.ids_scroll.inner.winfo_children():
            if isinstance(child, ttk.Checkbutton):
                rid = child.cget("text")
                self.id_vars[rid].set(False)

    def get_selected_ids(self):
        return [rid for rid, var in self.id_vars.items() if var.get()]

    # ========================================================
    # ID column dropdown
    # ========================================================

    def on_id_column_changed(self):
        if self.df is None:
            return

        new_id_col = self.idcol_var.get()
        if new_id_col == self.id_col:
            return

        self.id_col = new_id_col
        self.value_cols = [c for c in self.df.columns if c != self.id_col]
        self.id_list_all = self.df[self.id_col].astype(str).tolist()

        self.id_search_var.set("")
        self.refresh_id_checkboxes()

        for gname in list(self.groups.keys()):
            self.groups[gname]["col_vars"] = {c: tk.BooleanVar(value=False) for c in self.value_cols}

        self.render_active_group_columns(clear=False)
        self.cols_info_var.set(f"Value columns: {len(self.value_cols)}. Assign columns to groups.")
        self.status_var.set(f"ID column changed to '{self.id_col}'.")

    # ========================================================
    # Groups handling
    # ========================================================

    def create_group(self, name):
        self.groups[name] = {"col_vars": {c: tk.BooleanVar(value=False) for c in self.value_cols}}
        self.group_listbox.insert(tk.END, name)

    def add_group(self):
        if self.df is None:
            messagebox.showwarning("No dataset", "Load a dataset first.")
            return
        base = "Group"
        i = 1
        while f"{base} {i}" in self.groups:
            i += 1
        name = f"{base} {i}"
        self.create_group(name)
        self.select_group_by_name(name)

    def rename_group(self):
        if self.active_group is None:
            messagebox.showwarning("No group", "Select a group first.")
            return

        old = self.active_group
        new = self.ask_text("Rename Group", "New group name:", initial=old)
        if not new:
            return
        new = new.strip()
        if not new:
            return
        if new in self.groups and new != old:
            messagebox.showerror("Name exists", "A group with that name already exists.")
            return

        self.groups[new] = self.groups.pop(old)
        idx = self.group_index(old)
        self.group_listbox.delete(idx)
        self.group_listbox.insert(idx, new)

        self.active_group = new
        self.active_group_var.set(f"Active group: {new}")
        self.group_listbox.selection_clear(0, tk.END)
        self.group_listbox.selection_set(idx)
        self.group_listbox.activate(idx)

        self.render_active_group_columns()

    def remove_group(self):
        if self.active_group is None:
            messagebox.showwarning("No group", "Select a group first.")
            return

        name = self.active_group
        if not messagebox.askyesno("Remove group", f"Remove '{name}'?"):
            return

        idx = self.group_index(name)
        self.groups.pop(name, None)
        self.group_listbox.delete(idx)

        if self.group_listbox.size() > 0:
            new_idx = min(idx, self.group_listbox.size() - 1)
            self.select_group_by_index(new_idx)
        else:
            self.active_group = None
            self.active_group_var.set("Active group: (none)")
            self.render_active_group_columns(clear=True)

    def on_group_select(self):
        sel = self.group_listbox.curselection()
        if not sel:
            return
        self.active_group = self.group_listbox.get(sel[0])
        self.active_group_var.set(f"Active group: {self.active_group}")
        self.render_active_group_columns()

    def render_active_group_columns(self, clear=False):
        for w in self.group_cols_scroll.inner.winfo_children():
            w.destroy()

        if clear or self.active_group is None or self.df is None:
            return

        col_vars = self.groups[self.active_group]["col_vars"]
        for c in self.value_cols:
            cb = ttk.Checkbutton(self.group_cols_scroll.inner, text=str(c), variable=col_vars[c])
            cb.pack(anchor="w")

    def select_all_cols_in_group(self):
        if self.active_group is None:
            return
        for var in self.groups[self.active_group]["col_vars"].values():
            var.set(True)

    def clear_all_cols_in_group(self):
        if self.active_group is None:
            return
        for var in self.groups[self.active_group]["col_vars"].values():
            var.set(False)

    def get_group_cols(self, group_name):
        col_vars = self.groups[group_name]["col_vars"]
        return [c for c, var in col_vars.items() if var.get()]

    def group_index(self, name):
        for i in range(self.group_listbox.size()):
            if self.group_listbox.get(i) == name:
                return i
        return None

    def select_group_by_index(self, idx):
        self.group_listbox.selection_clear(0, tk.END)
        self.group_listbox.selection_set(idx)
        self.group_listbox.activate(idx)
        self.on_group_select()

    def select_group_by_name(self, name):
        idx = self.group_index(name)
        if idx is not None:
            self.select_group_by_index(idx)

    def ask_text(self, title, label, initial=""):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("400x160")
        win.grab_set()

        ttk.Label(win, text=label).pack(anchor="w", padx=12, pady=(12, 4))
        var = tk.StringVar(value=initial)
        entry = ttk.Entry(win, textvariable=var)
        entry.pack(fill="x", padx=12)
        entry.focus_set()

        result = {"value": None}

        def ok():
            result["value"] = var.get()
            win.destroy()

        def cancel():
            win.destroy()

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=12, pady=12)
        ttk.Button(btns, text="OK", command=ok).pack(side="left")
        ttk.Button(btns, text="Cancel", command=cancel).pack(side="left", padx=(8, 0))

        win.wait_window()
        return result["value"]

    # ========================================================
    # Plotting
    # ========================================================

    def plot(self):
        if self.df is None:
            messagebox.showwarning("No dataset", "Load a dataset first.")
            return

        selected_ids = self.get_selected_ids()
        if not selected_ids:
            messagebox.showwarning("No Row IDs", "Select at least one Row ID.")
            return

        ordered_groups = [self.group_listbox.get(i) for i in range(self.group_listbox.size())]

        group_to_cols = {}
        for g in ordered_groups:
            cols = self.get_group_cols(g)
            if cols:
                group_to_cols[g] = cols

        if not group_to_cols:
            messagebox.showwarning("No samples selected", "Select at least one sample/column in at least one group.")
            return

        fig = self.make_group_plot(selected_ids, ordered_groups, group_to_cols)
        self.last_fig = fig
        plt.show()

    def make_group_plot(self, selected_ids, ordered_groups, group_to_cols):
        ordered_groups = [g for g in ordered_groups if g in group_to_cols]
        G = len(ordered_groups)
        K = len(selected_ids)

        # Colors per sample column
        sample_order = []
        seen = set()
        for g in ordered_groups:
            for c in group_to_cols[g]:
                if c not in seen:
                    seen.add(c)
                    sample_order.append(c)

        cmap = plt.get_cmap("tab20")
        sample_color = {c: cmap(i % 20) for i, c in enumerate(sample_order)}

        # Marker per Row ID
        id_marker = {rid: self.id_markers[i % len(self.id_markers)] for i, rid in enumerate(selected_ids)}

        # Fast lookup for rows
        idx_map = {}
        for i, rid in enumerate(self.df[self.id_col].astype(str).tolist()):
            lrid = rid.lower()
            if lrid not in idx_map:
                idx_map[lrid] = i

        fig = plt.figure(figsize=(13.5, 6.8))
        ax = fig.add_subplot(111)

        group_x = np.arange(G)
        offsets = np.linspace(-0.25, 0.25, num=K) if K > 1 else np.array([0.0])

        jitter_alpha = float(self.jitter_alpha.get())
        jitter_width = float(self.jitter_width.get())
        rng_master = np.random.default_rng(2026)

        # Legend handles
        id_handles = []
        sample_handles = [
            Line2D([0], [0], marker="o", color=sample_color[c], linestyle="None", markersize=7, label=str(c))
            for c in sample_order
        ]

        # Draw per Row ID
        for k, rid in enumerate(selected_ids):
            lrid = rid.lower()
            if lrid not in idx_map:
                continue

            row = self.df.iloc[idx_map[lrid]]
            positions = group_x + offsets[k]

            # Boxplot data per group
            per_group_values = []
            per_group_cols = []
            for g in ordered_groups:
                cols = group_to_cols[g]
                vals = to_float_list(row[cols].values)
                per_group_values.append(vals)
                per_group_cols.append(cols)

            ax.boxplot(
                per_group_values,
                positions=positions,
                widths=0.16 if K > 1 else 0.35,
                showfliers=False,
                manage_ticks=False
            )

            # Jitter points
            rng = np.random.default_rng(rng_master.integers(0, 10_000_000))
            for gi, g in enumerate(ordered_groups):
                cols = per_group_cols[gi]
                x0 = positions[gi]

                for c in cols:
                    v = pd.to_numeric(row[c], errors="coerce")
                    if pd.isna(v):
                        continue

                    xj = rng.normal(loc=x0, scale=jitter_width, size=1)[0]
                    ax.scatter(
                        xj, float(v),
                        marker=id_marker[rid],
                        color=sample_color[c],
                        s=40,
                        alpha=jitter_alpha
                    )

            # Shape legend handle
            id_handles.append(
                Line2D([0], [0], marker=id_marker[rid], color="black", linestyle="None", markersize=8, label=rid)
            )

        # ---------- Labels (from GUI inputs) ----------
        title = self.plot_title_var.get().strip()
        xlab = self.x_label_var.get().strip()
        ylab = self.y_label_var.get().strip()

        ax.set_title(title if title else "Plot")
        ax.set_xlabel(xlab if xlab else "X")
        ax.set_ylabel(ylab if ylab else "Y")

        # x-axis tick labels are the group names
        ax.set_xticks(group_x)
        ax.set_xticklabels(
            ordered_groups,
            rotation=60 if self.rotate_xticks.get() else 0,
            ha="right" if self.rotate_xticks.get() else "center"
        )

        if self.show_grid.get():
            ax.grid(True, linestyle="--", alpha=0.3)

        # ---------- Legends: shapes + colors ----------
        if id_handles:
            leg_shapes = ax.legend(
                handles=id_handles,
                title="Row IDs (marker shape)",
                loc="upper left",
                bbox_to_anchor=(1.02, 1.0),
                borderaxespad=0.0
            )
            ax.add_artist(leg_shapes)

        if sample_handles:
            ax.legend(
                handles=sample_handles,
                title="Samples (color)",
                loc="lower left",
                bbox_to_anchor=(1.02, 0.0),
                borderaxespad=0.0
            )

        fig.tight_layout()
        return fig

    # ========================================================
    # Save plot / export groups
    # ========================================================

    def save_plot(self):
        if self.last_fig is None:
            messagebox.showinfo("No plot", "Make a plot first.")
            return

        path = filedialog.asksaveasfilename(
            title="Save plot as PNG",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return

        self.last_fig.savefig(path, dpi=200, bbox_inches="tight")
        self.status_var.set(f"Saved plot: {path}")

    def export_groups(self):
        if not self.groups:
            messagebox.showinfo("No groups", "No groups to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Export groups to TXT",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return

        lines = []
        lines.append(f"Dataset: {self.file_var.get()}")
        lines.append(f"ID column: {self.id_col}")
        lines.append("")

        for i in range(self.group_listbox.size()):
            g = self.group_listbox.get(i)
            cols = self.get_group_cols(g)

            lines.append(f"[{g}]")
            if cols:
                for c in cols:
                    lines.append(f"  - {c}")
            else:
                lines.append("  (no columns selected)")
            lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self.status_var.set(f"Exported groups: {path}")


# ============================================================
# 5) Main entry point
# ============================================================

def main():
    app = TableVisualiserApp()
    app.mainloop()


if __name__ == "__main__":
    main()
