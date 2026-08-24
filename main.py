from tkinter import *
import math
import json
from pathlib import Path
from datetime import date, datetime
from urllib import response
from winotify import Notification
import os
from dotenv import load_dotenv
from google import genai
import webbrowser
from urllib.parse import quote
from google.genai import types
# ---------------------------- CONSTANTS ------------------------------- #

PINK = "#e2979c"
RED = "#e7305b"
GREEN = "#9bdeac"
YELLOW = "#f7f5dd"
ORANGE = "#FFA500"
FONT_NAME = "Courier"

WORK_MIN = 1
SHORT_BREAK_MIN = 5
LONG_BREAK_MIN = 20

today = date.today().isoformat()

reps = 0
timer = None

task_count = 0
completed_tasks = 0
completed_sessions = 0
focus_minutes = 0

TASK_FILE = Path(__file__).resolve().parent / "tasks.json"

badges = {
    "first_task": False,
    "task_crusher": False,
    "productivity_pro": False,
    "focus_starter": False,
    "deep_focus": False,
    "focus_master": False,
    "perfect_day": False
}
load_dotenv()

gemini_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)
# ---------------------------- TASK PROGRESS ------------------------------- #

def update_task_progress():

    task_progress.config(
        text=f"Tasks Completed: {completed_tasks}/{task_count}"
    )

    update_dashboard()


# ---------------------------- SESSION / FOCUS ------------------------------- #

def update_session_count():

    session_label.config(
        text=f"🍅 Sessions: {completed_sessions}"
    )

    update_dashboard()


def update_focus_time():

    focus_time_label.config(
        text=f"⏱ Focus Time: {focus_minutes} min"
    )

    update_dashboard()


# ---------------------------- DASHBOARD ------------------------------- #

def update_dashboard():

    if task_count > 0:
        progress = int((completed_tasks / task_count) * 100)
    else:
        progress = 0

    dashboard_sessions.config(
        text=f"🍅 Sessions Completed: {completed_sessions}"
    )

    dashboard_focus.config(
        text=f"⏱ Focus Time: {focus_minutes} min"
    )

    dashboard_tasks.config(
        text=f"✅ Tasks Completed: {completed_tasks}/{task_count}"
    )

    dashboard_progress.config(
        text=f"📊 Today's Progress: {progress}%"
    )

    update_progress_bar()


# ---------------------------- PROGRESS BAR ------------------------------- #

def update_progress_bar():

    if task_count > 0:
        progress = completed_tasks / task_count
    else:
        progress = 0

    progress_bar.delete("all")

    # Background
    progress_bar.create_rectangle(
        0,
        0,
        300,
        25,
        fill="#dddddd",
        outline=""
    )

    # Progress
    progress_bar.create_rectangle(
        0,
        0,
        300 * progress,
        25,
        fill=GREEN,
        outline=""
    )

    progress_bar.create_text(
        150,
        12,
        text=f"{int(progress * 100)}%",
        fill="#333333",
        font=(FONT_NAME, 10, "bold")
    )


# ---------------------------- SAVE TASKS ------------------------------- #

def save_tasks():

    tasks = []

    for widget in main_frame.winfo_children():

        if isinstance(widget, Label):

            text = widget.cget("text")

            if "☐" in text or "✅" in text:
                tasks.append(text)

    # Read existing history
    if TASK_FILE.exists():

        with open(TASK_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

    else:
        data = {}

    # Save today's complete information
    data[today] = {
        "tasks": tasks,
        "sessions": completed_sessions,
        "focus_minutes": focus_minutes
    }

    with open(TASK_FILE, "w", encoding="utf-8") as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )


# ---------------------------- LOAD TASKS ------------------------------- #

def load_tasks():

    global task_count
    global completed_tasks
    global completed_sessions
    global focus_minutes

    if not TASK_FILE.exists():
        return

    with open(TASK_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    today_data = data.get(today, {})

    # ------------------------------------------------
    # Handle OLD format:
    # "2026-08-23": ["☐ Task 1", "✅ Task 2"]
    # ------------------------------------------------

    if isinstance(today_data, list):

        tasks = today_data

        saved_sessions = 0
        saved_focus = 0

    # ------------------------------------------------
    # Handle NEW format:
    # "2026-08-23": {
    #     "tasks": [...],
    #     "sessions": 2,
    #     "focus_minutes": 2
    # }
    # ------------------------------------------------

    elif isinstance(today_data, dict):

        tasks = today_data.get("tasks", [])

        saved_sessions = today_data.get(
            "sessions",
            0
        )

        saved_focus = today_data.get(
            "focus_minutes",
            0
        )

    else:

        tasks = []
        saved_sessions = 0
        saved_focus = 0

    # Restore today's productivity data
    completed_sessions = saved_sessions
    focus_minutes = saved_focus

    # ------------------------------------------------
    # Restore tasks
    # ------------------------------------------------

    for text in tasks:

        # Make sure task is actually a string
        if not isinstance(text, str):
            continue

        task_count += 1

        if "✅" in text:
            completed_tasks += 1

        current_row = 9 + task_count

        # ---------------- PRIORITY ---------------- #

        if "🔥" in text:

            priority_color = RED

        elif "🟡" in text:

            priority_color = ORANGE

        else:

            priority_color = GREEN

        priority_label = Label(
            main_frame,
            text="●",
            fg=priority_color,
            bg=YELLOW,
            font=(FONT_NAME, 15, "bold")
        )

        priority_label.grid(
            column=0,
            row=current_row,
            padx=(0, 5),
            pady=3,
            sticky="e"
        )

        # ---------------- TASK ---------------- #

        if "✅" in text:

            task_fg = "#888888"
            task_font = (
                FONT_NAME,
                12,
                "overstrike"
            )

        else:

            task_fg = "#333333"
            task_font = (
                FONT_NAME,
                12
            )

        task_label = Label(
            main_frame,
            text=text,
            fg=task_fg,
            bg=YELLOW,
            font=task_font,
            cursor="hand2"
        )

        task_label.grid(
            column=1,
            row=current_row,
            pady=3,
            sticky="w"
        )

        task_label.bind(
            "<Button-1>",
            lambda event, label=task_label:
            complete_task(label)
        )

        # ---------------- DELETE BUTTON ---------------- #

        delete_button = Button(
            main_frame,
            text="🗑",
            font=(FONT_NAME, 9),
            highlightthickness=0
        )

        delete_button.config(
            command=lambda
            label=task_label,
            priority=priority_label,
            button=delete_button:
            delete_task(
                label,
                priority,
                button
            )
        )

        delete_button.grid(
            column=2,
            row=current_row,
            padx=5
        )

        # ---------------- EDIT BUTTON ---------------- #

        edit_button = Button(
            main_frame,
            text="✏️",
            font=(FONT_NAME, 9),
            highlightthickness=0
        )

        edit_button.config(
            command=lambda
            label=task_label,
            priority=priority_label:
            edit_task(
                label,
                priority
            )
        )

        edit_button.grid(
            column=3,
            row=current_row,
            padx=3
        )

    update_task_progress()
    update_session_count()
    update_focus_time()

# ---------------------------- BADGES ------------------------------- #

def check_badges():

    new_badge = None

    # 🌱 First Step
    if completed_tasks >= 1 and not badges["first_task"]:

        badges["first_task"] = True

        new_badge = (
            "🌱 FIRST STEP",
            "You completed your first task! 🚀"
        )

    # 🔥 Task Crusher
    elif completed_tasks >= 5 and not badges["task_crusher"]:

        badges["task_crusher"] = True

        new_badge = (
            "🔥 TASK CRUSHER",
            "You completed 5 tasks! You're on fire! 🔥"
        )

    # ⚡ Productivity Pro
    elif completed_tasks >= 10 and not badges["productivity_pro"]:

        badges["productivity_pro"] = True

        new_badge = (
            "⚡ PRODUCTIVITY PRO",
            "10 tasks completed! Amazing productivity! 💪"
        )

    # 🍅 Focus Starter
    elif completed_sessions >= 1 and not badges["focus_starter"]:

        badges["focus_starter"] = True

        new_badge = (
            "🍅 FOCUS STARTER",
            "You completed your first focus session!"
        )

    # 🧠 Deep Focus
    elif completed_sessions >= 5 and not badges["deep_focus"]:

        badges["deep_focus"] = True

        new_badge = (
            "🧠 DEEP FOCUS",
            "5 focus sessions completed! 🧠🔥"
        )

    # 🚀 Focus Master
    elif completed_sessions >= 10 and not badges["focus_master"]:

        badges["focus_master"] = True

        new_badge = (
            "🚀 FOCUS MASTER",
            "10 focus sessions completed! You're unstoppable!"
        )

    # 💯 Perfect Day
    elif (
        task_count > 0
        and completed_tasks == task_count
        and not badges["perfect_day"]
    ):

        badges["perfect_day"] = True

        new_badge = (
            "💯 PERFECT DAY",
            "All today's tasks are complete! 🎉"
        )

    # Show notification
    if new_badge:

        title, message = new_badge

        send_notification(
            f"🏆 Badge Unlocked: {title}",
            message
        )

    update_badges_ui()
# ---------------------------- COMPLETE TASK ------------------------------- #

def complete_task(label):

    global completed_tasks

    current_text = label.cget("text")

    if "☐" in current_text:

        label.config(
            text=current_text.replace("☐", "✅", 1),
            fg="#888888",
            font=(FONT_NAME, 12, "overstrike")
        )

        completed_tasks += 1

        # Check if a new badge was earned
        check_badges()

    else:

        label.config(
            text=current_text.replace("✅", "☐", 1),
            fg="#333333",
            font=(FONT_NAME, 12)
        )

        completed_tasks -= 1

    update_task_progress()
    save_tasks()
   

# ---------------------------- DELETE TASK ------------------------------- #

def delete_task(task_label, priority_label, delete_button):

    global task_count
    global completed_tasks

    current_text = task_label.cget("text")

    # If task was completed, decrease completed count
    if "✅" in current_text:
        completed_tasks -= 1

    # Remove widgets
    task_label.destroy()
    priority_label.destroy()
    delete_button.destroy()

    task_count -= 1

    update_task_progress()
    save_tasks()


# ---------------------------- EDIT TASK ------------------------------- #

def edit_task(task_label, priority_label):

    current_text = task_label.cget("text")

    # Remove priority icon and checkbox
    task_text = current_text

    for icon in ["🔥", "🟡", "🟢", "☐", "✅"]:
        task_text = task_text.replace(icon, "")

    task_text = task_text.strip()

    # Edit window
    edit_window = Toplevel(window)

    edit_window.title("Edit Task")
    edit_window.geometry("350x220")
    edit_window.config(bg=YELLOW)

    Label(
        edit_window,
        text="✏️ Edit Task",
        bg=YELLOW,
        fg=RED,
        font=(FONT_NAME, 18, "bold")
    ).pack(pady=15)

    edit_entry = Entry(
        edit_window,
        width=30,
        font=(FONT_NAME, 11)
    )

    edit_entry.insert(0, task_text)
    edit_entry.pack(pady=10)

    # Priority
    edit_priority = StringVar()

    if "🔥" in current_text:
        edit_priority.set("High")

    elif "🟡" in current_text:
        edit_priority.set("Medium")

    else:
        edit_priority.set("Low")

    priority_menu = OptionMenu(
        edit_window,
        edit_priority,
        "High",
        "Medium",
        "Low"
    )

    priority_menu.pack(pady=5)

    def save_edit():

        new_task = edit_entry.get().strip()
        new_priority = edit_priority.get()

        if not new_task:
            return

        if new_priority == "High":

            icon = "🔥"
            color = RED

        elif new_priority == "Medium":

            icon = "🟡"
            color = ORANGE

        else:

            icon = "🟢"
            color = GREEN

        # Preserve completed state
        if "✅" in current_text:
            checkbox = "✅"

        else:
            checkbox = "☐"

        task_label.config(
            text=f"{icon} {checkbox} {new_task}"
        )

        # Update priority dot
        priority_label.config(
            fg=color
        )

        # Update completed styling
        if checkbox == "✅":

            task_label.config(
                fg="#888888",
                font=(FONT_NAME, 12, "overstrike")
            )

        else:

            task_label.config(
                fg="#333333",
                font=(FONT_NAME, 12)
            )

        save_tasks()

        edit_window.destroy()

    Button(
        edit_window,
        text="Save",
        font=(FONT_NAME, 11, "bold"),
        highlightthickness=0,
        command=save_edit
    ).pack(pady=10)


# ---------------------------- SMART FOCUS ------------------------------- #

def get_priority(text):

    if "🔥" in text:
        return 3

    elif "🟡" in text:
        return 2

    elif "🟢" in text:
        return 1

    else:
        return 0


def smart_focus():

    pending_tasks = []

    for widget in main_frame.winfo_children():

        if isinstance(widget, Label):

            text = widget.cget("text")

            if "☐" in text:
                pending_tasks.append(text)

    if not pending_tasks:

        smart_focus_label.config(
            text="🤖 No pending tasks!\nYou're all caught up 🎉",
            fg=GREEN
        )

        return

    # Highest priority task first
    recommended_task = max(
        pending_tasks,
        key=get_priority
    )

    # Remove icons so only task name is displayed
    task_name = recommended_task

    task_name = task_name.replace("🔥", "")
    task_name = task_name.replace("🟡", "")
    task_name = task_name.replace("🟢", "")
    task_name = task_name.replace("☐", "")

    task_name = task_name.strip()

    if "🔥" in recommended_task:

        priority_text = "HIGH PRIORITY 🔥"

    elif "🟡" in recommended_task:

        priority_text = "MEDIUM PRIORITY 🟡"

    else:

        priority_text = "LOW PRIORITY 🟢"

    smart_focus_label.config(
        text=f"🤖 Recommended Focus\n\n"
             f"{task_name}\n\n"
             f"{priority_text}",
        fg="#333333"
    )


# ---------------------------- ADD TASK ------------------------------- #

def add_task():

    global task_count

    task = task_entry.get().strip()

    priority = priority_var.get()

    if priority == "High":

        priority_icon = "🔥"
        priority_color = RED

    elif priority == "Medium":

        priority_icon = "🟡"
        priority_color = ORANGE

    else:

        priority_icon = "🟢"
        priority_color = GREEN

    if task:

        task_count += 1
        current_row = 9 + task_count

        # Priority colored dot
        priority_label = Label(
            main_frame,
            text="●",
            fg=priority_color,
            bg=YELLOW,
            font=(FONT_NAME, 15, "bold")
        )

        priority_label.grid(
            column=0,
            row=9 + task_count,
            padx=(0, 5),
            pady=3,
            sticky="e"
        )

        # Task label
        task_label = Label(
            main_frame,
            text=f"{priority_icon} ☐ {task}",
            fg="#333333",
            bg=YELLOW,
            font=(FONT_NAME, 12),
            cursor="hand2"
        )

        task_label.grid(
            column=1,
            columnspan=1,
            row=9 + task_count,
            pady=3,
            sticky="w"
        )

        task_label.bind(
            "<Button-1>",
            lambda event, label=task_label:
            complete_task(label)
        )

        # Delete button
        delete_button = Button(
            main_frame,
            text="🗑",
            font=(FONT_NAME, 9),
            highlightthickness=0
        )

        delete_button.config(
            command=lambda
            label=task_label,
            priority=priority_label,
            button=delete_button:
            delete_task(
                label,
                priority,
                button
            )
        )

        delete_button.grid(
            column=2,
            row=current_row,
            padx=5
        )

        # Edit button
        edit_button = Button(
            main_frame,
            text="✏️",
            font=(FONT_NAME, 9),
            highlightthickness=0,
            command=lambda
            label=task_label,
            priority=priority_label:
            edit_task(
                label,
                priority
            )
        )

        edit_button.grid(
            column=3,
            row=current_row,
            padx=3
        )

        task_entry.delete(
            0,
            END
        )

        update_task_progress()
        save_tasks()


# ---------------------------- NOTIFICATION ------------------------------- #

def send_notification(title, message):

    toast = Notification(
        app_id="Focus Mode",
        title=title,
        msg=message
    )

    toast.show()


# ---------------------------- TIMER RESET ------------------------------- #

def reset_timer():

    global reps
    global timer

    if timer is not None:

        window.after_cancel(timer)

        timer = None

    canvas.itemconfig(
        timer_text,
        text="00:00"
    )

    title_label.config(
        text="FOCUS MODE",
        fg=GREEN
    )

    check_mark.config(
        text=""
    )

    # Reset only the timer.
    # Keep today's completed sessions and focus time.
    reps = 0

    update_session_count()
    update_focus_time()


# ---------------------------- TIMER START ------------------------------- #

def start_timer():

    global reps

    reps += 1

    work_sec = WORK_MIN * 60
    short_break_sec = SHORT_BREAK_MIN * 60
    long_break_sec = LONG_BREAK_MIN * 60

    if reps % 8 == 0:

        title_label.config(
            text="Long Break",
            fg=RED
        )

        count_down(long_break_sec)

    elif reps % 2 == 0:

        title_label.config(
            text="Short Break",
            fg=PINK
        )

        count_down(short_break_sec)

    else:

        title_label.config(
            text="Work",
            fg=GREEN
        )

        count_down(work_sec)


# ---------------------------- COUNTDOWN ------------------------------- #

def count_down(count):

    global timer
    global completed_sessions
    global focus_minutes

    count_min = math.floor(count / 60)

    count_sec = count % 60

    if count_sec < 10:
        count_sec = f"0{count_sec}"

    canvas.itemconfig(
        timer_text,
        text=f"{count_min}:{count_sec}"
    )

    if count > 0:

        timer = window.after(
            1000,
            count_down,
            count - 1
        )

    else:

        if reps % 2 == 1:

            completed_sessions += 1

            focus_minutes += WORK_MIN

            update_session_count()
            update_focus_time()
            save_tasks()

            send_notification(
                "🎉 Focus Session Complete!",
                "Great job! Time for a break."
            )

        else:

            send_notification(
                "⏰ Break Finished!",
                "Your break is over. Ready to focus?"
            )

        marks = ""

        work_sessions = math.floor(reps / 2)

        for _ in range(work_sessions):
            marks += "✔"

        check_mark.config(
            text=marks
        )

        start_timer()
        update_session_count()
        update_focus_time()

        check_badges()

        save_tasks()

# ---------------------------- SCROLL ------------------------------- #
# ---------------------------- WINDOW + SCROLL ------------------------------- #

window = Tk()

window.title("Pomodoro")

window.geometry("700x700")

window.config(
    bg=YELLOW
)


# ---------------------------- MAIN CANVAS ------------------------------- #

main_canvas = Canvas(
    window,
    bg=YELLOW,
    highlightthickness=0
)

main_canvas.pack(
    side="left",
    fill="both",
    expand=True
)


# ---------------------------- SCROLLBAR ------------------------------- #

scrollbar = Scrollbar(
    window,
    orient="vertical",
    command=main_canvas.yview
)

scrollbar.pack(
    side="right",
    fill="y"
)


# Connect scrollbar to canvas

main_canvas.configure(
    yscrollcommand=scrollbar.set
)


# ---------------------------- MAIN FRAME ------------------------------- #

main_frame = Frame(
    main_canvas,
    bg=YELLOW
)

main_canvas.create_window(
    (0, 0),
    window=main_frame,
    anchor="nw"
)


# ---------------------------- UPDATE SCROLL REGION ------------------------------- #

def update_scrollregion(event):

    main_canvas.configure(
        scrollregion=main_canvas.bbox("all")
    )


main_frame.bind(
    "<Configure>",
    update_scrollregion
)


# ---------------------------- MOUSE SCROLL ------------------------------- #

def scroll_with_mouse(event):

    main_canvas.yview_scroll(
        int(-1 * (event.delta / 120)),
        "units"
    )


main_canvas.bind_all(
    "<MouseWheel>",
    scroll_with_mouse
)


    # ---------------------------- AI ROADMAP ------------------------------- #
def generate_ai_roadmap():

    topic = roadmap_entry.get().strip()

    if not topic or topic == "What do you want to learn?":

        roadmap_output.config(
            text="⚠️ Please enter a topic first."
        )

        return

    roadmap_output.config(
        text="🤖 Gemini is creating your roadmap..."
    )

    window.update_idletasks()

    try:

        prompt = f"""
Create a beginner-friendly learning roadmap for:

{topic}

The learner is preparing for interviews.

Create 5 phases.

For every phase give:

PHASE X: Phase Name

Topics:
1. Topic
2. Topic
3. Topic
4. Topic

Estimated Time:
1. XX minutes
2. XX minutes
3. XX minutes
4. XX minutes

Pomodoro Sessions: X

YouTube Search:
Give one YouTube search query.

At the end give:

🎯 FINAL GOAL:
What the learner should be able to do after completing this roadmap.

Rules:
- Start from beginner level.
- Gradually move to advanced topics.
- Focus on practical learning.
- Give realistic estimated time for every topic.
- The learner can modify the suggested time according to their needs.
- Do not create fake YouTube URLs.
- Give YouTube search queries only.
"""

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                )
            )
        )

        roadmap_output.config(
            text=response.text
        )

    except Exception as e:

        print("GEMINI ERROR:", e)

        roadmap_output.config(
            text="⚠️ Gemini limit reached or an error occurred. Please try again later."
        )

# ---------------------------- YOUTUBE SEARCH ------------------------------- #

def open_youtube_search():

    query = roadmap_entry.get().strip()

    if query and query != "What do you want to learn?":

        url = (
            "https://www.youtube.com/results?search_query="
            + query.replace(" ", "+")
        )

        webbrowser.open(url)

def generate_job_roadmap():

    job = job_entry.get().strip()

    if not job:
        job_output.config(
            text="⚠️ Please enter a job role."
        )
        return

    job_output.config(
        text="🤖 Gemini is analyzing the job requirements..."
    )

    window.update()

    prompt = f"""
You are an expert career advisor and job market analyst.

The user wants to prepare for this job:

{job}

Create a beginner-friendly preparation roadmap based on the skills
normally required for this role.

Give the answer in this format:

🎯 TARGET ROLE
Job role

📚 MUST LEARN
1. Skill
2. Skill
3. Skill
4. Skill
5. Skill

💻 PROGRAMMING
- Languages to learn

🧠 DSA
- Important DSA topics

🗄 DATABASE
- Important database topics

⚙️ FRAMEWORKS
- Important frameworks

☁️ TOOLS
- Git
- Docker
- Cloud
- Other important tools

📖 CORE CS
- OOP
- DBMS
- OS
- Computer Networks
- Other relevant subjects

🤖 AI SKILLS
Mention useful AI skills if relevant to this job.

🚀 PROJECTS
Give 3 projects that would strengthen the resume.

🎤 INTERVIEW PREPARATION
Give important interview topics.

⭐ PRIORITY ORDER
Tell the user what to learn first, second, third, etc.

⏱ STUDY PLAN
Give an approximate 8-12 week learning plan.

Keep it practical and beginner friendly.
"""

    try:

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt
        )

        job_output.config(
            text=response.text
        )

    except Exception as e:

        job_output.config(
            text=f"❌ Gemini Error:\n{e}"
        )
# ---------------------------- PRIORITY ------------------------------- #
priority_var = StringVar()
priority_var.set("Medium")

priority_menu = OptionMenu(
    main_frame,
    priority_var,
    "High",
    "Medium",
    "Low"
)

priority_menu.config(
    font=(FONT_NAME, 10, "bold"),
    highlightthickness=0
)

priority_menu.grid(
    column=1,
    row=9,
    padx=5
)


# ---------------------------- HEADER ------------------------------- #

title_label = Label(
    main_frame,
    text="FOCUS MODE",
    fg=GREEN,
    font=(FONT_NAME, 40, "bold"),
    bg=YELLOW
)

title_label.grid(
    column=1,
    row=0
)


subtitle_label = Label(
    main_frame,
    text=f"Stay focused. You've got this! 🍅  |  {today}",
    fg="#555555",
    font=(FONT_NAME, 12),
    bg=YELLOW
)

subtitle_label.grid(
    column=1,
    row=1,
    pady=(0, 20)
)


# ---------------------------- TIMER CANVAS ------------------------------- #

canvas = Canvas(
    main_frame,
    width=300,
    height=300,
    bg=YELLOW,
    highlightthickness=0
)

tomato_img = PhotoImage(
    file="tomato.png",
     master=window
)

canvas.create_image(
    150,
    150,
    image=tomato_img
)

timer_text = canvas.create_text(
    150,
    170,
    text="00:00",
    fill="white",
    font=(FONT_NAME, 28, "bold")
)

canvas.grid(
    column=1,
    row=2
)


# ---------------------------- BUTTONS ------------------------------- #

start_button = Button(
    main_frame,
    text="Start",
    highlightthickness=0,
    font=(FONT_NAME, 18, "bold"),
    command=start_timer
)

start_button.grid(
    column=0,
    row=3
)


reset_button = Button(
    main_frame,
    text="Reset",
    highlightthickness=0,
    font=(FONT_NAME, 18, "bold"),
    command=reset_timer
)

reset_button.grid(
    column=2,
    row=3
)


# ---------------------------- SESSION MARKS ------------------------------- #

check_mark = Label(
    main_frame,
    fg=GREEN,
    bg=YELLOW,
    font=(FONT_NAME, 18, "bold")
)

check_mark.grid(
    column=1,
    row=4
)


# ---------------------------- TASK SECTION ------------------------------- #

task_title = Label(
    main_frame,
    text="Today's Tasks",
    fg=RED,
    bg=YELLOW,
    font=(FONT_NAME, 20, "bold")
)

task_title.grid(
    column=1,
    row=5,
    pady=(30, 10)
)


task_progress = Label(
    main_frame,
    text="Tasks Completed: 0/0",
    fg="#555555",
    bg=YELLOW,
    font=(FONT_NAME, 11)
)

task_progress.grid(
    column=1,
    row=6
)


session_label = Label(
    main_frame,
    text="🍅 Sessions: 0",
    fg=RED,
    bg=YELLOW,
    font=(FONT_NAME, 12, "bold")
)

session_label.grid(
    column=1,
    row=7,
    pady=(20, 5)
)


focus_time_label = Label(
    main_frame,
    text="⏱ Focus Time: 0 min",
    fg="#555555",
    bg=YELLOW,
    font=(FONT_NAME, 12, "bold")
)

focus_time_label.grid(
    column=1,
    row=8
)


# ---------------------------- SMART FOCUS UI ------------------------------- #

smart_focus_title = Label(
    main_frame,
    text="🤖 Smart Focus",
    fg=RED,
    bg=YELLOW,
    font=(FONT_NAME, 20, "bold")
)

smart_focus_title.grid(
    column=1,
    row=20,
    pady=(30, 10)
)


smart_focus_label = Label(
    main_frame,
    text="Click below to find your best task to focus on.",
    fg="#555555",
    bg=YELLOW,
    font=(FONT_NAME, 12),
    justify="center"
)

smart_focus_label.grid(
    column=1,
    row=21,
    pady=5
)


smart_focus_button = Button(
    main_frame,
    text="🤖 Find My Focus",
    font=(FONT_NAME, 12, "bold"),
    highlightthickness=0,
    command=smart_focus
)

smart_focus_button.grid(
    column=1,
    row=22,
    pady=(5, 20)
)
# ---------------------------- AI ROADMAP UI ------------------------------- #

roadmap_title = Label(
    main_frame,
    text="🧠 AI Learning Roadmap",
    fg=RED,
    bg=YELLOW,
    font=(FONT_NAME, 20, "bold")
)

roadmap_title.grid(
    column=1,
    row=24,
    pady=(30, 10)
)


roadmap_entry = Entry(
    main_frame,
    width=25,
    font=(FONT_NAME, 12)
)

roadmap_entry.grid(
    column=1,
    row=26,
    pady=5
)


roadmap_entry.insert(
    0,
    "What do you want to learn?"
)


roadmap_button = Button(
    main_frame,
    text="🤖 Generate AI Roadmap",
    font=(FONT_NAME, 12, "bold"),
    highlightthickness=0,
    command=generate_ai_roadmap
)

roadmap_button.grid(
    column=1,
    row=27,
    pady=10
)


roadmap_output = Label(
    main_frame,
    text="Your personalized roadmap will appear here.",
    fg="#333333",
    bg=YELLOW,
    font=(FONT_NAME, 10),
    justify="left",
    anchor="w",
    wraplength=550
)

roadmap_output.grid(
    column=1,
    row=41,
    pady=10,
    sticky="w"
)
job_title = Label(
    main_frame,
    text="💼 AI Job Analyzer",
    fg=RED,
    bg=YELLOW,
    font=(FONT_NAME, 20, "bold")
)

job_title.grid(
    column=1,
    row=37,
    pady=(30, 10)
)


job_entry = Entry(
    main_frame,
    width=35,
    font=(FONT_NAME, 12)
)

job_entry.grid(
    column=1,
    row=38,
    pady=5
)

job_entry.insert(
    0,
    "Enter target job role..."
)


job_button = Button(
    main_frame,
    text="💼 Analyze Job & Create Roadmap",
    font=(FONT_NAME, 12, "bold"),
    highlightthickness=0,
    command=generate_job_roadmap
)

job_button.grid(
    column=1,
    row=39,
    pady=10
)


job_output = Label(
    main_frame,
    text="Your job preparation roadmap will appear here.",
    fg="#333333",
    bg=YELLOW,
    font=(FONT_NAME, 10),
    justify="left",
    anchor="w",
    wraplength=550
)

job_output.grid(
    column=1,
    row=40,
    pady=10,
    sticky="w"
)


# ---------------------------- ACHIEVEMENTS UI ------------------------------- #

achievement_title = Label(
    main_frame,
    text="🏆 Achievements",
    fg=RED,
    bg=YELLOW,
    font=(FONT_NAME, 20, "bold")
)

achievement_title.grid(
    column=1,
    row=43,
    pady=(30, 10)
)


achievement_subtitle = Label(
    main_frame,
    text="Complete tasks and focus sessions to unlock badges!",
    fg="#555555",
    bg=YELLOW,
    font=(FONT_NAME, 10)
)

achievement_subtitle.grid(
    column=1,
    row=45,
    pady=(0, 15)
)


badges_frame = Frame(
    main_frame,
    bg=YELLOW
)

badges_frame.grid(
    column=1,
    row=46,
    pady=5
)


badge_labels = {}


badge_info = [
    ("first_task", "🌱", "First Step"),
    ("task_crusher", "🔥", "Task Crusher"),
    ("productivity_pro", "⚡", "Productivity Pro"),
    ("focus_starter", "🍅", "Focus Starter"),
    ("deep_focus", "🧠", "Deep Focus"),
    ("focus_master", "🚀", "Focus Master"),
    ("perfect_day", "💯", "Perfect Day")
]


for index, (key, icon, name) in enumerate(badge_info):

    badge = Frame(
        badges_frame,
        bg="#F3F4F7",
        width=130,
        height=85,
        highlightbackground="#DDDDDD",
        highlightthickness=1
    )

    badge.grid(
        row=index // 4,
        column=index % 4,
        padx=5,
        pady=5
    )

    badge.pack_propagate(False)

    icon_label = Label(
        badge,
        text="🔒",
        bg="#F3F4F7",
        fg="#AAAAAA",
        font=(FONT_NAME, 18, "bold")
    )

    icon_label.pack(
        pady=(8, 0)
    )

    name_label = Label(
        badge,
        text=name,
        bg="#F3F4F7",
        fg="#AAAAAA",
        font=(FONT_NAME, 8, "bold")
    )

    name_label.pack()

    badge_labels[key] = (
        badge,
        icon_label,
        name_label
    )


def update_badges_ui():

    for key, icon, name in badge_info:

        badge, icon_label, name_label = badge_labels[key]

        if badges[key]:

            badge.config(
                bg=YELLOW
            )

            icon_label.config(
                text=icon,
                bg=YELLOW,
                fg=RED
            )

            name_label.config(
                fg="#333333",
                bg=YELLOW
            )

        else:

            badge.config(
                bg="#F3F4F7"
            )

            icon_label.config(
                text="🔒",
                bg="#F3F4F7",
                fg="#AAAAAA"
            )

            name_label.config(
                fg="#AAAAAA",
                bg="#F3F4F7"
            )


def update_badges_ui():

    for key, icon, name in badge_info:

        badge, icon_label, name_label = badge_labels[key]

        if badges[key]:

            badge.config(
                bg=YELLOW
            )

            icon_label.config(
                text=icon,
                bg=YELLOW,
                fg=RED
            )

            name_label.config(
                fg="#333333",
                bg=YELLOW
            )

        else:

            badge.config(
                bg="#F3F4F7"
            )

            icon_label.config(
                text="🔒",
                bg="#F3F4F7",
                fg="#AAAAAA"
            )

            name_label.config(
                fg="#AAAAAA",
                bg="#F3F4F7"
            )

# ---------------------------- PRODUCTIVITY DASHBOARD ------------------------------- #

dashboard_title = Label(
    main_frame,
    text="📊 Productivity Dashboard",
    fg=RED,
    bg=YELLOW,
    font=(FONT_NAME, 22, "bold")
)

dashboard_title.grid(
    column=1,
    row=30,
    pady=(40, 15)
)


dashboard_sessions = Label(
    main_frame,
    text="🍅 Sessions Completed: 0",
    fg="#333333",
    bg=YELLOW,
    font=(FONT_NAME, 13, "bold")
)

dashboard_sessions.grid(
    column=1,
    row=31,
    pady=5
)


dashboard_focus = Label(
    main_frame,
    text="⏱ Focus Time: 0 min",
    fg="#333333",
    bg=YELLOW,
    font=(FONT_NAME, 13, "bold")
)

dashboard_focus.grid(
    column=1,
    row=32,
    pady=5
)


dashboard_tasks = Label(
    main_frame,
    text="✅ Tasks Completed: 0/0",
    fg="#333333",
    bg=YELLOW,
    font=(FONT_NAME, 13, "bold")
)

dashboard_tasks.grid(
    column=1,
    row=33,
    pady=5
)


dashboard_progress = Label(
    main_frame,
    text="📊 Today's Progress: 0%",
    fg=GREEN,
    bg=YELLOW,
    font=(FONT_NAME, 15, "bold")
)

dashboard_progress.grid(
    column=1,
    row=34,
    pady=(10, 10)
)


# ---------------------------- PROGRESS BAR ------------------------------- #

progress_bar = Canvas(
    main_frame,
    width=300,
    height=25,
    bg=YELLOW,
    highlightthickness=0
)

progress_bar.grid(
    column=1,
    row=35,
    pady=(0, 30)
)


# ---------------------------- TASK INPUT ------------------------------- #

task_entry = Entry(
    main_frame,
    width=25,
    font=(FONT_NAME, 12)
)

task_entry.grid(
    column=0,
    row=9,
    padx=5
)


add_task_button = Button(
    main_frame,
    text="Add",
    font=(FONT_NAME, 12, "bold"),
    highlightthickness=0,
    command=add_task
)

add_task_button.grid(
    column=2,
    row=9
)


# ---------------------------- LOAD SAVED TASKS ------------------------------- #

load_tasks()


update_badges_ui()

# ---------------------------- INITIAL DASHBOARD ------------------------------- #

update_dashboard()


# ---------------------------- MAIN LOOP ------------------------------- #

window.mainloop()