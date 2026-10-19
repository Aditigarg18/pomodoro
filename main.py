
import json
import math
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import date
from tkinter import PhotoImage
# Windows notifications are optional.
try:
    from winotify import Notification
except ImportError:
    Notification = None


# =========================================================
# SETTINGS
# =========================================================

APP_NAME = "Focus Mode"
BG = "#F4F6FB"
CARD = "#FFFFFF"
TEXT = "#20243A"
MUTED = "#73798C"
PRIMARY = "#635BFF"
PRIMARY_DARK = "#5148E5"
GREEN = "#22A06B"
RED = "#E05260"
ORANGE = "#F59E0B"
BORDER = "#E5E7EB"
FONT_NAME = "Segoe UI"

WORK_MIN = 25
SHORT_BREAK_MIN = 5
LONG_BREAK_MIN = 20
LONG_BREAK_EVERY = 4

TODAY = date.today().isoformat()
TASK_FILE = Path(__file__).resolve().parent / "tasks.json"
SKILL_FILE = Path(__file__).resolve().parent / "skill_learning.py"

PRIORITIES = {
    "High": ("🔥", RED),
    "Medium": ("🟡", ORANGE),
    "Low": ("🟢", GREEN),
}

BADGE_INFO = {
    "first_task": ("🌱", "First Step", "Complete your first task"),
    "task_crusher": ("🔥", "Task Crusher", "Complete 5 tasks"),
    "productivity_pro": ("⚡", "Productivity Pro", "Complete 10 tasks"),
    "focus_starter": ("🍅", "Focus Starter", "Finish 1 focus session"),
    "deep_focus": ("🧠", "Deep Focus", "Finish 5 focus sessions"),
    "focus_master": ("🚀", "Focus Master", "Finish 10 focus sessions"),
    "perfect_day": ("💯", "Perfect Day", "Complete every task"),
}


# =========================================================
# APP STATE
# =========================================================

tasks = []
completed_sessions = 0
focus_minutes = 0

timer_mode = "Focus"
seconds_left = WORK_MIN * 60
timer_running = False
timer_after_id = None
completed_focus_sessions = 0

badges = {key: False for key in BADGE_INFO}


# =========================================================
# ROOT WINDOW AND THEME
# =========================================================

root = tk.Tk()
root.title("Focus Mode | Productivity Dashboard")
root.geometry("1120x850")
root.minsize(900, 680)
root.configure(bg=BG)

style = ttk.Style(root)

try:
    style.theme_use("clam")
except tk.TclError:
    pass

style.configure(
    "TProgressbar",
    troughcolor="#E9EAF4",
    background=PRIMARY,
    bordercolor="#E9EAF4",
    lightcolor=PRIMARY,
    darkcolor=PRIMARY,
    thickness=10,
)

style.configure(
    "TCombobox",
    padding=7,
    fieldbackground=CARD,
    background=CARD,
)

style.configure(
    "Vertical.TScrollbar",
    background="#D8D9E6",
    troughcolor=BG,
    bordercolor=BG,
)


# =========================================================
# UI HELPERS
# =========================================================

def create_card(parent):
    return tk.Frame(
        parent,
        bg=CARD,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0,
    )


def create_button(
    parent,
    text,
    command,
    bg=PRIMARY,
    fg="white",
    padx=14,
    pady=9,
):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=PRIMARY_DARK if bg == PRIMARY else bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        cursor="hand2",
        font=(FONT_NAME, 10, "bold"),
        padx=padx,
        pady=pady,
    )


def notify(title, message):
    if Notification is None:
        return

    try:
        Notification(
            app_id=APP_NAME,
            title=title,
            msg=message,
        ).show()
    except Exception:
        pass


# =========================================================
# DATA STORAGE
# =========================================================

def save_data():
    """Save today's tasks, focus time, sessions and badges."""

    try:
        data = {}

        if TASK_FILE.exists():
            try:
                with open(TASK_FILE, "r", encoding="utf-8") as file:
                    loaded = json.load(file)

                if isinstance(loaded, dict):
                    data = loaded

            except (OSError, json.JSONDecodeError):
                data = {}

        data[TODAY] = {
            "tasks": [
                {
                    "text": task["text"],
                    "priority": task["priority"],
                    "done": task["done"],
                }
                for task in tasks
            ],
            "sessions": completed_sessions,
            "focus_minutes": focus_minutes,
            "badges": badges,
        }

        with open(TASK_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    except OSError as error:
        print("Could not save data:", error)


def load_data():
    """Load today's data, including the older task-list format."""

    global tasks
    global completed_sessions
    global focus_minutes
    global badges

    if not TASK_FILE.exists():
        return

    try:
        with open(TASK_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        day_data = data.get(TODAY, {})

    except (OSError, json.JSONDecodeError):
        return

    if isinstance(day_data, list):
        # Compatibility with the original tasks.json format.
        saved_tasks = day_data

    elif isinstance(day_data, dict):
        saved_tasks = day_data.get("tasks", [])

        completed_sessions = int(
            day_data.get("sessions", 0) or 0
        )

        focus_minutes = int(
            day_data.get("focus_minutes", 0) or 0
        )

        saved_badges = day_data.get("badges", {})

        if isinstance(saved_badges, dict):
            for key in badges:
                badges[key] = bool(saved_badges.get(key, False))

    else:
        saved_tasks = []

    tasks = []

    for item in saved_tasks:
        if isinstance(item, dict):
            task_text = str(item.get("text", "")).strip()

            if not task_text:
                continue

            priority = item.get("priority", "Medium")

            if priority not in PRIORITIES:
                priority = "Medium"

            tasks.append({
                "text": task_text,
                "priority": priority,
                "done": bool(item.get("done", False)),
            })

        elif isinstance(item, str):
            # Read task entries saved by the older version.
            done = "✅" in item

            if "🔥" in item:
                priority = "High"
            elif "🟡" in item:
                priority = "Medium"
            else:
                priority = "Low"

            task_text = item

            for symbol in ("🔥", "🟡", "🟢", "☐", "✅"):
                task_text = task_text.replace(symbol, "")

            task_text = task_text.strip()

            if task_text:
                tasks.append({
                    "text": task_text,
                    "priority": priority,
                    "done": done,
                })


# =========================================================
# TASK MANAGEMENT
# =========================================================

def get_task_stats():
    total = len(tasks)
    completed = sum(1 for task in tasks if task["done"])
    return total, completed


def add_task(event=None):
    task_text = task_entry.get().strip()
    priority = priority_var.get()

    if not task_text:
        task_entry.focus_set()
        return

    tasks.append({
        "text": task_text,
        "priority": priority,
        "done": False,
    })

    task_entry.delete(0, tk.END)

    render_tasks()
    refresh_dashboard()
    save_data()

    task_entry.focus_set()


def toggle_task(index):
    if not 0 <= index < len(tasks):
        return

    tasks[index]["done"] = not tasks[index]["done"]

    render_tasks()
    refresh_dashboard()
    check_badges()
    save_data()


def delete_task(index):
    if not 0 <= index < len(tasks):
        return

    del tasks[index]

    render_tasks()
    refresh_dashboard()
    check_badges()
    save_data()


def edit_task(index):
    if not 0 <= index < len(tasks):
        return

    task = tasks[index]

    dialog = tk.Toplevel(root)
    dialog.title("Edit Task")
    dialog.geometry("420x250")
    dialog.resizable(False, False)
    dialog.configure(bg=BG)
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(
        dialog,
        text="Edit your task",
        bg=BG,
        fg=TEXT,
        font=(FONT_NAME, 18, "bold"),
    ).pack(anchor="w", padx=24, pady=(22, 14))

    entry = tk.Entry(
        dialog,
        font=(FONT_NAME, 11),
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
    )

    entry.pack(fill="x", padx=24, ipady=9)
    entry.insert(0, task["text"])
    entry.focus_set()

    priority_row = tk.Frame(dialog, bg=BG)
    priority_row.pack(fill="x", padx=24, pady=15)

    tk.Label(
        priority_row,
        text="Priority",
        bg=BG,
        fg=MUTED,
        font=(FONT_NAME, 10),
    ).pack(side="left")

    edit_priority = tk.StringVar(value=task["priority"])

    ttk.Combobox(
        priority_row,
        textvariable=edit_priority,
        values=list(PRIORITIES.keys()),
        state="readonly",
        width=14,
    ).pack(side="right")

    def save_edit():
        new_text = entry.get().strip()

        if not new_text:
            messagebox.showinfo(
                "Task required",
                "Please enter a task name.",
                parent=dialog,
            )
            return

        task["text"] = new_text
        task["priority"] = edit_priority.get()

        render_tasks()
        refresh_dashboard()
        save_data()

        dialog.destroy()

    create_button(
        dialog,
        "Save changes",
        save_edit,
    ).pack(anchor="e", padx=24, pady=(0, 18))

    entry.bind("<Return>", lambda event: save_edit())


def render_tasks():
    for widget in task_list.winfo_children():
        widget.destroy()

    total, completed = get_task_stats()

    task_count_label.config(
        text=f"{total} task{'s' if total != 1 else ''}"
    )

    if not tasks:
        tk.Label(
            task_list,
            text="No tasks yet.\nAdd one above to get started ✨",
            bg=CARD,
            fg=MUTED,
            font=(FONT_NAME, 11),
            pady=30,
        ).pack(fill="x")

        return

    for index, task in enumerate(tasks):
        row = tk.Frame(task_list, bg=CARD)
        row.pack(fill="x", padx=12, pady=5)

        icon, priority_color = PRIORITIES[task["priority"]]

        checkbox_text = "✓" if task["done"] else "○"
        checkbox_bg = GREEN if task["done"] else "#F3F4F6"
        checkbox_fg = "white" if task["done"] else MUTED

        tk.Button(
            row,
            text=checkbox_text,
            command=lambda i=index: toggle_task(i),
            bg=checkbox_bg,
            fg=checkbox_fg,
            activebackground=checkbox_bg,
            relief="flat",
            bd=0,
            width=3,
            font=(FONT_NAME, 11, "bold"),
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))

        tk.Label(
            row,
            text=task["text"],
            bg=CARD,
            fg="#9CA3AF" if task["done"] else TEXT,
            font=(
                FONT_NAME,
                10,
                "overstrike" if task["done"] else "normal",
            ),
            anchor="w",
            justify="left",
            wraplength=240,
        ).pack(side="left", fill="x", expand=True)

        tk.Label(
            row,
            text=f"{icon} {task['priority']}",
            bg="#FFF1F2" if task["priority"] == "High"
            else "#FFFBEB" if task["priority"] == "Medium"
            else "#F0FDF4",
            fg=priority_color,
            font=(FONT_NAME, 8, "bold"),
            padx=6,
            pady=4,
        ).pack(side="left", padx=5)

        create_button(
            row,
            "Edit",
            lambda i=index: edit_task(i),
            bg="#EEF2FF",
            fg=PRIMARY,
            padx=8,
            pady=6,
        ).pack(side="left", padx=2)

        create_button(
            row,
            "×",
            lambda i=index: delete_task(i),
            bg="#FEF2F2",
            fg=RED,
            padx=9,
            pady=6,
        ).pack(side="left", padx=2)

        if index < len(tasks) - 1:
            tk.Frame(
                task_list,
                bg="#F1F2F6",
                height=1,
            ).pack(fill="x", padx=12, pady=3)


# =========================================================
# POMODORO TIMER
# =========================================================

def duration_for_mode(mode):
    if mode == "Focus":
        return WORK_MIN * 60

    if mode == "Short break":
        return SHORT_BREAK_MIN * 60

    return LONG_BREAK_MIN * 60


def update_timer_display():
    minutes, seconds = divmod(max(0, seconds_left), 60)

    timer_canvas.itemconfig(
        timer_text_id,
        text=f"{minutes:02d}:{seconds:02d}",
    )

    timer_canvas.itemconfig(
        timer_mode_id,
        text=timer_mode.upper(),
    )

    full_duration = duration_for_mode(timer_mode)

    progress = seconds_left / max(1, full_duration)

    timer_canvas.itemconfig(
        timer_arc_id,
        extent=-360 * progress,
    )

    if timer_running:
        start_pause_button.config(text="Pause timer")
    elif seconds_left != full_duration:
        start_pause_button.config(text="Resume timer")
    else:
        start_pause_button.config(
            text="Start focus" if timer_mode == "Focus"
            else "Start break"
        )


def set_mode(mode):
    global timer_mode, seconds_left

    timer_mode = mode
    seconds_left = duration_for_mode(mode)

    update_timer_display()


def tick():
    global seconds_left, timer_after_id

    timer_after_id = None

    if not timer_running:
        return

    if seconds_left > 0:
        seconds_left -= 1
        update_timer_display()

        timer_after_id = root.after(1000, tick)

    else:
        finish_interval()


def finish_interval():
    global completed_sessions
    global focus_minutes
    global timer_running

    timer_running = False
    start_pause_button.config(text="Start focus")

    if timer_mode == "Focus":
        completed_sessions += 1
        focus_minutes += WORK_MIN

        notify(
            "Focus session complete!",
            "Great work. Take a well-earned break.",
        )

        check_badges()

        if completed_sessions % LONG_BREAK_EVERY == 0:
            next_mode = "Long break"
        else:
            next_mode = "Short break"

        set_mode(next_mode)

        status_label.config(
            text="Focus session complete — take a break!",
            fg=GREEN,
        )

    else:
        notify(
            "Break finished",
            "Ready to focus again?",
        )

        set_mode("Focus")

        status_label.config(
            text="Break finished — ready for another session?",
            fg=PRIMARY,
        )

    refresh_dashboard()
    save_data()


def toggle_timer():
    global timer_running, timer_after_id

    if timer_running:
        timer_running = False

        if timer_after_id is not None:
            root.after_cancel(timer_after_id)
            timer_after_id = None

        update_timer_display()

        status_label.config(
            text="Timer paused.",
            fg=MUTED,
        )

        return

    timer_running = True

    update_timer_display()

    status_label.config(
        text=f"{timer_mode} session in progress. You've got this!",
        fg=PRIMARY,
    )

    timer_after_id = root.after(1000, tick)


def reset_timer():
    global timer_running, timer_after_id, seconds_left

    timer_running = False

    if timer_after_id is not None:
        root.after_cancel(timer_after_id)
        timer_after_id = None

    seconds_left = duration_for_mode(timer_mode)

    status_label.config(
        text="Timer reset. Ready when you are.",
        fg=MUTED,
    )

    update_timer_display()


def choose_timer_mode(mode):
    global timer_running, timer_after_id

    if timer_after_id is not None:
        root.after_cancel(timer_after_id)
        timer_after_id = None

    timer_running = False
    set_mode(mode)

    status_label.config(
        text=f"{mode} selected.",
        fg=MUTED,
    )


# =========================================================
# ACHIEVEMENTS
# =========================================================

def check_badges():
    total, done = get_task_stats()

    conditions = {
        "first_task": done >= 1,
        "task_crusher": done >= 5,
        "productivity_pro": done >= 10,
        "focus_starter": completed_sessions >= 1,
        "deep_focus": completed_sessions >= 5,
        "focus_master": completed_sessions >= 10,
        "perfect_day": total > 0 and done == total,
    }

    for key, unlocked in conditions.items():
        if unlocked and not badges[key]:
            badges[key] = True

            icon, name, description = BADGE_INFO[key]

            notify(
                f"Achievement unlocked: {name}",
                f"{icon} {name} — nice work!",
            )

    render_badges()
    save_data()


def render_badges():
    for widget in badge_grid.winfo_children():
        widget.destroy()

    for index, (key, info) in enumerate(BADGE_INFO.items()):
        icon, name, description = info
        unlocked = badges[key]

        badge_bg = "#F0FDF4" if unlocked else "#F9FAFB"
        badge_fg = GREEN if unlocked else "#9CA3AF"

        badge = tk.Frame(
            badge_grid,
            bg=badge_bg,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=8,
            pady=8,
        )

        badge.grid(
            row=index // 4,
            column=index % 4,
            padx=4,
            pady=4,
            sticky="nsew",
        )

        tk.Label(
            badge,
            text=icon if unlocked else "🔒",
            bg=badge_bg,
            fg=badge_fg,
            font=(FONT_NAME, 17),
        ).pack()

        tk.Label(
            badge,
            text=name,
            bg=badge_bg,
            fg=TEXT if unlocked else MUTED,
            font=(FONT_NAME, 8, "bold"),
        ).pack(pady=(3, 2))

        tk.Label(
            badge,
            text="Unlocked" if unlocked else description,
            bg=badge_bg,
            fg=badge_fg,
            font=(FONT_NAME, 7),
            wraplength=100,
        ).pack()


# =========================================================
# DASHBOARD
# =========================================================

def refresh_dashboard():
    total, done = get_task_stats()

    percent = int(done / total * 100) if total else 0

    tasks_value.config(text=f"{done}/{total}")
    sessions_value.config(text=str(completed_sessions))
    focus_value.config(text=f"{focus_minutes} min")

    progress_percent.config(text=f"{percent}%")
    progress_bar["value"] = percent

    render_badges()


# =========================================================
# OPEN THE SEPARATE SKILL LEARNING APP
# =========================================================

def open_skill_learning():
    if not SKILL_FILE.exists():
        messagebox.showerror(
            "File not found",
            "Could not find 'skill learning.py'.\n\n"
            "Place it in the same folder as main.py.",
        )
        return

    try:
        subprocess.Popen([
            sys.executable,
            str(SKILL_FILE),
        ])
    except OSError as error:
        messagebox.showerror(
            "Could not open Skill Learning",
            str(error),
        )


# =========================================================
# USER INTERFACE
# =========================================================

# Header
header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=28, pady=(22, 16))

header_left = tk.Frame(header, bg=BG)
header_left.pack(side="left")

tk.Label(
    header_left,
    text="Focus Mode",
    bg=BG,
    fg=TEXT,
    font=(FONT_NAME, 25, "bold"),
).pack(anchor="w")

tk.Label(
    header_left,
    text=f"Build focus, one session at a time  •  {TODAY}",
    bg=BG,
    fg=MUTED,
    font=(FONT_NAME, 10),
).pack(anchor="w", pady=(3, 0))

create_button(
    header,
    "📚 Skill Learning",
    open_skill_learning,
).pack(side="right", pady=5)

# Main two-column layout
content = tk.Frame(root, bg=BG)
content.pack(
    fill="both",
    expand=True,
    padx=28,
    pady=(0, 24),
)

content.columnconfigure(0, weight=5, uniform="columns")
content.columnconfigure(1, weight=6, uniform="columns")
content.rowconfigure(0, weight=1)

left_column = tk.Frame(content, bg=BG)
left_column.grid(
    row=0,
    column=0,
    sticky="nsew",
    padx=(0, 12),
)

right_column = tk.Frame(content, bg=BG)
right_column.grid(
    row=0,
    column=1,
    sticky="nsew",
    padx=(12, 0),
)

# ---------------- TIMER CARD ----------------

timer_card = create_card(left_column)
timer_card.pack(fill="x", pady=(0, 14))

tk.Label(
    timer_card,
    text="FOCUS TIMER",
    bg=CARD,
    fg=MUTED,
    font=(FONT_NAME, 9, "bold"),
).pack(pady=(20, 2))

tk.Label(
    timer_card,
    text="Small steps. Real progress.",
    bg=CARD,
    fg=TEXT,
    font=(FONT_NAME, 15, "bold"),
).pack()
# Tomato image in the timer
tomato_path = Path(__file__).resolve().parent / "tomato.png"

tomato_image = PhotoImage(file=str(tomato_path))

# Resize the image if it is too large
if tomato_image.width() > 180 or tomato_image.height() > 180:
    tomato_image = tomato_image.subsample(
        max(1, math.ceil(tomato_image.width() / 180)),
        max(1, math.ceil(tomato_image.height() / 180))
    )

timer_canvas = tk.Canvas(
    timer_card,
    width=270,
    height=270,
    bg=CARD,
    highlightthickness=0,
)

timer_canvas.pack(pady=(8, 4))

timer_canvas.create_image(
    135, 135,
    image=tomato_image
)

timer_mode_id = timer_canvas.create_text(
    135, 155,
    text="FOCUS",
    fill=TEXT,
    font=(FONT_NAME, 10, "bold"),
)

timer_text_id = timer_canvas.create_text(
    135, 125,
    text="25:00",
    fill=TEXT,
    font=(FONT_NAME, 24, "bold"),
)

timer_arc_id = None

timer_controls = tk.Frame(timer_card, bg=CARD)
timer_controls.pack(pady=(0, 10))

start_pause_button = create_button(
    timer_controls,
    "Start focus",
    toggle_timer,
)

start_pause_button.pack(side="left", padx=5)

create_button(
    timer_controls,
    "Reset",
    reset_timer,
    bg="#F3F4F6",
    fg=TEXT,
).pack(side="left", padx=5)

mode_controls = tk.Frame(timer_card, bg=CARD)
mode_controls.pack(pady=(0, 10))

create_button(
    mode_controls,
    "Focus · 25m",
    lambda: choose_timer_mode("Focus"),
    bg="#F3F4F6",
    fg=TEXT,
    padx=8,
    pady=7,
).pack(side="left", padx=3)

create_button(
    mode_controls,
    "Short · 5m",
    lambda: choose_timer_mode("Short break"),
    bg="#F3F4F6",
    fg=TEXT,
    padx=8,
    pady=7,
).pack(side="left", padx=3)

create_button(
    mode_controls,
    "Long · 20m",
    lambda: choose_timer_mode("Long break"),
    bg="#F3F4F6",
    fg=TEXT,
    padx=8,
    pady=7,
).pack(side="left", padx=3)

status_label = tk.Label(
    timer_card,
    text="Ready to focus? Start a session when you're ready.",
    bg=CARD,
    fg=MUTED,
    font=(FONT_NAME, 9),
    wraplength=380,
)

status_label.pack(pady=(0, 18))

# ---------------- DASHBOARD CARD ----------------

dashboard_card = create_card(left_column)
dashboard_card.pack(fill="both", expand=True)

tk.Label(
    dashboard_card,
    text="Today's overview",
    bg=CARD,
    fg=TEXT,
    font=(FONT_NAME, 15, "bold"),
).pack(anchor="w", padx=18, pady=(18, 4))

tk.Label(
    dashboard_card,
    text="Your progress so far",
    bg=CARD,
    fg=MUTED,
    font=(FONT_NAME, 9),
).pack(anchor="w", padx=18)

stats = tk.Frame(dashboard_card, bg=CARD)
stats.pack(fill="x", padx=12, pady=12)

for column in range(3):
    stats.columnconfigure(column, weight=1)


def create_stat_tile(parent, column, title, initial, color):
    tile = tk.Frame(
        parent,
        bg="#F8F9FC",
        padx=8,
        pady=12,
    )

    tile.grid(
        row=0,
        column=column,
        padx=5,
        sticky="nsew",
    )

    tk.Label(
        tile,
        text=title,
        bg="#F8F9FC",
        fg=MUTED,
        font=(FONT_NAME, 9),
    ).pack()

    value = tk.Label(
        tile,
        text=initial,
        bg="#F8F9FC",
        fg=color,
        font=(FONT_NAME, 17, "bold"),
    )

    value.pack(pady=(5, 0))

    return value


tasks_value = create_stat_tile(
    stats, 0, "Tasks", "0/0", PRIMARY
)

sessions_value = create_stat_tile(
    stats, 1, "Sessions", "0", GREEN
)

focus_value = create_stat_tile(
    stats, 2, "Focus time", "0 min", ORANGE
)

progress_row = tk.Frame(dashboard_card, bg=CARD)
progress_row.pack(
    fill="x",
    padx=18,
    pady=(4, 18),
)

progress_top = tk.Frame(progress_row, bg=CARD)
progress_top.pack(fill="x")

progress_caption = tk.Label(
    progress_top,
    text="Today's tasks completed",
    bg=CARD,
    fg=MUTED,
    font=(FONT_NAME, 9),
)

progress_caption.pack(side="left")

progress_percent = tk.Label(
    progress_top,
    text="0%",
    bg=CARD,
    fg=PRIMARY,
    font=(FONT_NAME, 10, "bold"),
)

progress_percent.pack(side="right")

progress_bar = ttk.Progressbar(
    progress_row,
    maximum=100,
    mode="determinate",
)

progress_bar.pack(fill="x", pady=(8, 0))

# ---------------- TASK CARD ----------------

tasks_card = create_card(right_column)
tasks_card.pack(fill="both", expand=True, pady=(0, 14))

tasks_heading = tk.Frame(tasks_card, bg=CARD)
tasks_heading.pack(
    fill="x",
    padx=18,
    pady=(18, 12),
)

tk.Label(
    tasks_heading,
    text="Today's tasks",
    bg=CARD,
    fg=TEXT,
    font=(FONT_NAME, 16, "bold"),
).pack(side="left")

task_count_label = tk.Label(
    tasks_heading,
    text="0 tasks",
    bg="#F3F4F6",
    fg=MUTED,
    font=(FONT_NAME, 9, "bold"),
    padx=9,
    pady=4,
)

task_count_label.pack(side="right")

task_form = tk.Frame(tasks_card, bg=CARD)
task_form.pack(
    fill="x",
    padx=18,
    pady=(0, 14),
)

task_entry = tk.Entry(
    task_form,
    font=(FONT_NAME, 10),
    relief="flat",
    bg="#F8F9FC",
    fg=TEXT,
    insertbackground=TEXT,
    highlightthickness=1,
    highlightbackground=BORDER,
)

task_entry.pack(
    fill="x",
    ipady=10,
    pady=(0, 9),
)

task_entry.bind("<Return>", add_task)

form_bottom = tk.Frame(task_form, bg=CARD)
form_bottom.pack(fill="x")

priority_var = tk.StringVar(value="Medium")

priority_menu = ttk.Combobox(
    form_bottom,
    textvariable=priority_var,
    values=list(PRIORITIES.keys()),
    state="readonly",
    width=12,
)

priority_menu.pack(side="left")

create_button(
    form_bottom,
    "+ Add task",
    add_task,
).pack(side="right")

tk.Frame(
    tasks_card,
    bg=BORDER,
    height=1,
).pack(fill="x", padx=18)

# Scrollable task list
task_canvas = tk.Canvas(
    tasks_card,
    bg=CARD,
    highlightthickness=0,
)

task_scrollbar = ttk.Scrollbar(
    tasks_card,
    orient="vertical",
    command=task_canvas.yview,
)

task_list = tk.Frame(task_canvas, bg=CARD)

task_window_id = task_canvas.create_window(
    (0, 0),
    window=task_list,
    anchor="nw",
)

task_canvas.configure(
    yscrollcommand=task_scrollbar.set,
)

task_canvas.pack(
    side="left",
    fill="both",
    expand=True,
    padx=(5, 0),
    pady=(5, 12),
)

task_scrollbar.pack(
    side="right",
    fill="y",
    pady=(5, 12),
)


def update_task_scroll_region(event=None):
    task_canvas.configure(
        scrollregion=task_canvas.bbox("all")
    )


def resize_task_window(event):
    task_canvas.itemconfigure(
        task_window_id,
        width=event.width,
    )


task_list.bind(
    "<Configure>",
    update_task_scroll_region,
)

task_canvas.bind(
    "<Configure>",
    resize_task_window,
)

# ---------------- ACHIEVEMENTS CARD ----------------

achievements_card = create_card(right_column)
achievements_card.pack(fill="x")

achievements_heading = tk.Frame(
    achievements_card,
    bg=CARD,
)

achievements_heading.pack(
    fill="x",
    padx=18,
    pady=(16, 4),
)

tk.Label(
    achievements_heading,
    text="Achievements",
    bg=CARD,
    fg=TEXT,
    font=(FONT_NAME, 14, "bold"),
).pack(side="left")

tk.Label(
    achievements_heading,
    text="Keep your streak going",
    bg=CARD,
    fg=MUTED,
    font=(FONT_NAME, 9),
).pack(side="right")

badge_grid = tk.Frame(achievements_card, bg=CARD)
badge_grid.pack(
    fill="x",
    padx=10,
    pady=(4, 12),
)

for column in range(4):
    badge_grid.columnconfigure(column, weight=1)


# =========================================================
# STARTUP AND SHUTDOWN
# =========================================================

load_data()
render_tasks()
refresh_dashboard()
update_timer_display()


def close_app():
    global timer_running, timer_after_id

    timer_running = False

    if timer_after_id is not None:
        try:
            root.after_cancel(timer_after_id)
        except tk.TclError:
            pass

    save_data()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", close_app)
root.mainloop()
