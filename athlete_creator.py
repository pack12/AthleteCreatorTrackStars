#!/usr/bin/env /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
# athlete_creator.py — Tkinter companion app for creating custom athletes
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import messagebox, ttk

ROSTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_roster.json")

# ── Physics constants (mirrored from game) ────────────────────────────────────
MIN_MAX_SPEED   = 6.0
MAX_MAX_SPEED   = 9.5
MIN_MAX_SPEED_F = 5.5
MAX_MAX_SPEED_F = 7.6
BASE_DRAG       = 0.048
MIN_DRAG        = 0.032
MIN_STAMINA_CAP = 35
MAX_STAMINA_CAP = 165
PHYSICS_SUBSTEP = 0.05

# Pacing strategies: list of (end_fraction, effort) segments
_STRATEGIES: dict[str, list[tuple[float, float]]] = {
    "aggressive":   [(0.30, 1.00), (0.60, 0.92), (0.85, 0.87), (1.00, 0.90)],
    "even":         [(1.00, 0.83)],
    "conservative": [(0.50, 0.74), (0.80, 0.84), (1.00, 1.00)],
    "kick":         [(0.72, 0.68), (0.88, 0.82), (1.00, 1.00)],
}

_EVENT_STRATEGY: dict[float, str] = {
    400.0:  "aggressive",
    800.0:  "even",
    1600.0: "conservative",
    3200.0: "kick",
}


def _get_effort(strategy: str, progress: float) -> float:
    """Return effort level (0-1) for the given race progress fraction."""
    for end_frac, effort in _STRATEGIES[strategy]:
        if progress <= end_frac:
            return effort
    return _STRATEGIES[strategy][-1][1]


def simulate_time(
    speed_stat: float,
    stamina_stat: float,
    technique_stat: float,
    gender: str,
    event_distance: float,
    strategy: str,
) -> float:
    """Run headless physics loop and return finish time in seconds."""
    if gender == "F":
        max_speed = MIN_MAX_SPEED_F + speed_stat * (MAX_MAX_SPEED_F - MIN_MAX_SPEED_F)
    else:
        max_speed = MIN_MAX_SPEED + speed_stat * (MAX_MAX_SPEED - MIN_MAX_SPEED)

    drag_coeff  = BASE_DRAG - technique_stat * (BASE_DRAG - MIN_DRAG)
    stamina_cap = MIN_STAMINA_CAP + stamina_stat * (MAX_STAMINA_CAP - MIN_STAMINA_CAP)

    speed    = 0.0
    distance = 0.0
    energy   = 1.0
    elapsed  = 0.0
    dt       = PHYSICS_SUBSTEP

    while distance < event_distance and elapsed < 1200.0:
        progress = distance / event_distance
        effort   = _get_effort(strategy, progress)

        if energy < 0.30:
            max_eff = 0.25 + (energy / 0.30) * 0.75
            effort  = min(effort, max_eff)

        drive  = drag_coeff * max_speed ** 2 * effort
        drag   = drag_coeff * speed ** 2
        accel  = drive - drag
        speed += accel * dt
        if speed < 0:
            speed = 0.0
        distance += speed * dt
        energy   -= (effort ** 2) / stamina_cap * dt
        elapsed  += dt

    return elapsed


def format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds) // 60
    secs    = seconds - minutes * 60
    return f"{minutes}:{secs:04.1f}"


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

        # ── Estimated Times panel ────────────────────────────────────
        times_frame = tk.LabelFrame(self, text="Estimated Times", **pad)
        times_frame.grid(row=0, column=2, sticky="nsew", **pad)

        mono = ("Courier", 11)
        self._time_labels: dict[str, tk.Label] = {}

        events = [
            (400.0,  "400m",  "Aggressive"),
            (800.0,  "800m",  "Even Pace"),
            (1600.0, "1600m", "Conservative"),
            (3200.0, "3200m", "Sit & Kick"),
        ]
        for i, (dist, label, strat_name) in enumerate(events):
            tk.Label(times_frame, text=f"{label}", font=mono, anchor="w", width=6).grid(
                row=i, column=0, sticky="w", padx=(8, 2), pady=6
            )
            lbl = tk.Label(times_frame, text="–", font=mono, anchor="w", width=10)
            lbl.grid(row=i, column=1, sticky="w", padx=2, pady=6)
            tk.Label(times_frame, text=f"({strat_name})", font=("Helvetica", 10), fg="#555555").grid(
                row=i, column=2, sticky="w", padx=(2, 8), pady=6
            )
            self._time_labels[label] = lbl

        # Wire traces — update whenever sliders or gender change
        for var in (self.speed_var, self.stamina_var, self.technique_var):
            var.trace_add("write", lambda *_: self._update_estimated_times())
        self.gender_var.trace_add("write", lambda *_: self._update_estimated_times())
        self._update_estimated_times()

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

    def _update_estimated_times(self):
        try:
            spd  = self.speed_var.get()
            sta  = self.stamina_var.get()
            tec  = self.technique_var.get()
            gen  = self.gender_var.get()
        except tk.TclError:
            return

        events = [
            (400.0,  "400m",  "aggressive"),
            (800.0,  "800m",  "even"),
            (1600.0, "1600m", "conservative"),
            (3200.0, "3200m", "kick"),
        ]
        for dist, label, strategy in events:
            t = simulate_time(spd, sta, tec, gen, dist, strategy)
            self._time_labels[label].config(text=f"~{format_time(t)}")

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
