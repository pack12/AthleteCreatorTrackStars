#!/usr/bin/env /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
# athlete_creator.py — Tkinter companion app for creating custom athletes
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

ROSTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_roster.json")


def _load_json() -> list[dict]:
    if not os.path.exists(ROSTER_FILE):
        return []
    try:
        with open(ROSTER_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_json(athletes: list[dict]) -> None:
    with open(ROSTER_FILE, "w") as f:
        json.dump(athletes, f, indent=2)


class AthleteCreatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Athlete Creator")
        self.resizable(False, False)
        self._build_ui()
        self._refresh_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # ── Input panel ──────────────────────────────────────────────
        input_frame = tk.LabelFrame(self, text="New Athlete", **pad)
        input_frame.grid(row=0, column=0, sticky="nsew", **pad)

        # Name
        tk.Label(input_frame, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.name_var = tk.StringVar()
        tk.Entry(input_frame, textvariable=self.name_var, width=28).grid(
            row=0, column=1, columnspan=2, sticky="w", padx=6, pady=4
        )

        # Gender
        tk.Label(input_frame, text="Gender:").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.gender_var = tk.StringVar(value="M")
        gender_frame = tk.Frame(input_frame)
        gender_frame.grid(row=1, column=1, columnspan=2, sticky="w")
        tk.Radiobutton(gender_frame, text="M", variable=self.gender_var, value="M").pack(side="left")
        tk.Radiobutton(gender_frame, text="F", variable=self.gender_var, value="F").pack(side="left")

        # Sliders
        self.speed_var     = tk.DoubleVar(value=0.50)
        self.stamina_var   = tk.DoubleVar(value=0.50)
        self.technique_var = tk.DoubleVar(value=0.50)

        self._slider_row(input_frame, row=2, label="Speed:",     var=self.speed_var)
        self._slider_row(input_frame, row=3, label="Stamina:",   var=self.stamina_var)
        self._slider_row(input_frame, row=4, label="Technique:", var=self.technique_var)

        # Add button
        tk.Button(
            input_frame, text="Add Athlete", command=self._add_athlete,
            bg="#2e7d32", fg="black", font=("Helvetica", 11, "bold"), width=16
        ).grid(row=5, column=0, columnspan=3, pady=10)

        # ── Roster panel ─────────────────────────────────────────────
        roster_frame = tk.LabelFrame(self, text="Custom Roster", **pad)
        roster_frame.grid(row=0, column=1, sticky="nsew", **pad)

        # Scrollable listbox
        list_frame = tk.Frame(roster_frame)
        list_frame.pack(fill="both", expand=True, padx=6, pady=4)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        self.listbox = tk.Listbox(
            list_frame, width=32, height=16,
            yscrollcommand=scrollbar.set, selectmode="single",
            font=("Courier", 11)
        )
        scrollbar.config(command=self.listbox.yview)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Action buttons
        btn_frame = tk.Frame(roster_frame)
        btn_frame.pack(fill="x", padx=6, pady=(0, 6))

        tk.Button(
            btn_frame, text="Remove Selected", command=self._remove_selected,
            bg="#c62828", fg="black", width=16
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            btn_frame, text="Clear All", command=self._clear_all,
            bg="#6a1b9a", fg="black", width=10
        ).pack(side="left")

    def _slider_row(self, parent: tk.Widget, row: int, label: str, var: tk.DoubleVar):
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=4)
        slider = tk.Scale(
            parent, variable=var, from_=0.0, to=1.0, resolution=0.01,
            orient="horizontal", length=200, showvalue=False,
            command=lambda _: self._update_slider_label(var, label)
        )
        slider.grid(row=row, column=1, padx=6, pady=4)

        # Value label
        lbl = tk.Label(parent, text=f"{var.get():.2f}", width=5, anchor="w")
        lbl.grid(row=row, column=2, padx=4)
        # Store reference keyed by variable id so command can update it
        if not hasattr(self, "_slider_labels"):
            self._slider_labels: dict[int, tk.Label] = {}
        self._slider_labels[id(var)] = lbl

        # Update immediately on drag
        var.trace_add("write", lambda *_: self._update_slider_label(var, label))

    def _update_slider_label(self, var: tk.DoubleVar, _label: str):
        lbl = self._slider_labels.get(id(var))
        if lbl:
            try:
                lbl.config(text=f"{var.get():.2f}")
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_athlete(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Name cannot be empty.")
            return

        athletes = _load_json()
        color_idx = len(athletes) % 8

        athletes.append({
            "name":      name,
            "gender":    self.gender_var.get(),
            "speed":     round(self.speed_var.get(), 2),
            "stamina":   round(self.stamina_var.get(), 2),
            "technique": round(self.technique_var.get(), 2),
            "color_idx": color_idx,
        })

        _save_json(athletes)
        self.name_var.set("")
        self._refresh_list()

    def _remove_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Remove", "Select an athlete to remove.")
            return
        idx = sel[0]
        athletes = _load_json()
        if idx < len(athletes):
            removed = athletes.pop(idx)
            # Reassign color_idx sequentially
            for i, a in enumerate(athletes):
                a["color_idx"] = i % 8
            _save_json(athletes)
            self._refresh_list()

    def _clear_all(self):
        if not messagebox.askyesno("Clear All", "Remove all custom athletes?"):
            return
        _save_json([])
        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for a in _load_json():
            gender_tag = f"[{a.get('gender', '?')}]"
            self.listbox.insert("end", f"{gender_tag} {a.get('name', '?')}")


if __name__ == "__main__":
    app = AthleteCreatorApp()
    app.mainloop()
