
import os
import json
import random
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date

from dotenv import load_dotenv
import requests
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas as pdf_canvas

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_MODEL = "gemini-3.8-flash"

PROGRESS_FILE = "focusai_progress.json"
CERTIFICATE_DIR = "focusai_certificates"

BG = "#0B1120"
PANEL = "#151E32"
CARD = "#1B2740"
ACCENT = "#818CF8"
TEXT = "#F1F5F9"
MUTED = "#A6B2C8"
GREEN = "#34D399"

# ============================================================
# DATA STORAGE
# ============================================================

def load_data():
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            result = json.load(f)
            return result if isinstance(result, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


data = load_data()
current_skill = ""
course = None
current_level = 0
busy = False


def save_data():
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as error:
        messagebox.showerror("Save error", str(error))


def skill_record(skill):
    return data.setdefault(skill, {
        "completed": [],
        "passed_levels": [],
        "final_passed": False,
        "certificate": None,
        "course": None
    })


# ============================================================
# GEMINI API
# ============================================================

def validate_question(question):
    if not isinstance(question.get("question"), str):
        raise ValueError("An exam question is missing its text.")

    options = question.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("Every exam question must have four options.")

    answer = question.get("answer")
    if not isinstance(answer, int) or answer not in range(4):
        raise ValueError("An answer must be a number from 0 to 3.")

    question.setdefault("explanation", "Review the lesson for more information.")


def gemini_json(prompt):
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is missing from your .env file."
        )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    response = requests.post(
        url,
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.4
            }
        },
        timeout=90
    )

    if not response.ok:
        raise RuntimeError(
            f"Gemini API error ({response.status_code}): "
            f"{response.text[:800]}"
        )

    result = response.json()

    try:
        output = result["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(output)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(
            "Gemini returned an invalid or unexpected response. Try again."
        ) from error


def generate_course(skill):
    prompt = f"""
Create a course for the skill: {skill}.

Return ONLY valid JSON with this structure:
{{
  "levels": [
    {{
      "title": "Beginner",
      "topics": [
        {{
          "title": "Specific topic",
          "description": "What the learner will learn",
          "video_query": "Specific YouTube tutorial search phrase"
        }}
      ],
      "exam": [
        {{
          "question": "Question text",
          "options": ["A", "B", "C", "D"],
          "answer": 0,
          "explanation": "Explanation"
        }}
      ]
    }}
  ],
  "final_exam": [
    {{
      "question": "Question text",
      "options": ["A", "B", "C", "D"],
      "answer": 0,
      "explanation": "Explanation"
    }}
  ]
}}

Requirements:
- Exactly 3 levels: Beginner, Intermediate, Advanced.
- Exactly 5 distinct topics per level.
- Exactly 5 questions per level exam.
- Exactly 10 questions in the final exam.
- Exactly 4 options per question.
- Answer is the zero-based index of the correct option.
- Topics and questions must be specific to {skill}.
- Topics must follow a sensible learning order.
- Use clear, simple English.
- Each topic must include a useful video_query.
- Return JSON only, without Markdown fences.
"""

    result = gemini_json(prompt)
    levels = result.get("levels", [])

    if len(levels) != 3:
        raise ValueError("AI must generate exactly three course levels.")

    for level in levels:
        if len(level.get("topics", [])) != 5:
            raise ValueError("Each level must contain five topics.")

        if len(level.get("exam", [])) < 5:
            raise ValueError("A level exam contains fewer than five questions.")

        level["exam"] = level["exam"][:5]

        for question in level["exam"]:
            validate_question(question)

    if len(result.get("final_exam", [])) < 10:
        raise ValueError("The final exam contains fewer than ten questions.")

    result["final_exam"] = result["final_exam"][:10]

    for question in result["final_exam"]:
        validate_question(question)

    return result


# ============================================================
# YOUTUBE VIDEO SEARCH
# ============================================================

def find_one_video(query):
    if not YOUTUBE_API_KEY:
        raise ValueError(
            "YOUTUBE_API_KEY is missing from your .env file."
        )

    response = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "order": "relevance",
            "safeSearch": "strict",
            "relevanceLanguage": "en",
            "key": YOUTUBE_API_KEY
        },
        timeout=20
    )

    if not response.ok:
        raise RuntimeError(
            f"YouTube API error ({response.status_code}): "
            f"{response.text[:800]}"
        )

    items = response.json().get("items", [])

    if not items:
        raise ValueError("No matching YouTube video was found.")

    item = items[0]
    video_id = item["id"]["videoId"]
    title = item["snippet"]["title"]

    return title, f"https://www.youtube.com/watch?v={video_id}"


def watch_video(query):
    def worker():
        try:
            title, url = find_one_video(query)
            root.after(
                0,
                lambda t=title, u=url: open_video_result(t, u)
            )
        except Exception as error:
            message = str(error)
            root.after(
                0,
                lambda m=message: messagebox.showerror("Video error", m)
            )

    threading.Thread(target=worker, daemon=True).start()


def open_video_result(title, url):
    if messagebox.askokcancel(
        "Selected lesson",
        f"{title}\n\nOpen this video on YouTube?"
    ):
        webbrowser.open_new_tab(url)


# ============================================================
# COURSE GENERATION
# ============================================================

def start_course(event=None):
    global busy

    skill = skill_entry.get().strip()

    if not skill:
        messagebox.showinfo("Enter a skill", "Type a skill or hobby first.")
        return

    if busy:
        return

    record = skill_record(skill)
    saved_course = record.get("course")

    if isinstance(saved_course, dict) and len(saved_course.get("levels", [])) == 3:
        show_course(skill, saved_course)
        status_label.config(text="Loaded your saved course.")
        return

    busy = True
    search_button.config(state="disabled")
    status_label.config(text=f"Creating your {skill} course with AI...")

    def worker():
        try:
            result = generate_course(skill)
            root.after(
                0,
                lambda s=skill, r=result: show_course(s, r)
            )
        except Exception as error:
            message = str(error)
            root.after(0, lambda m=message: course_error(m))

    threading.Thread(target=worker, daemon=True).start()


def course_error(error):
    global busy

    busy = False
    search_button.config(state="normal")
    status_label.config(text="Could not create the course.")

    messagebox.showerror(
        "Course generation failed",
        f"{error}\n\nCheck your .env keys, internet connection, API access and quota."
    )


def show_course(skill, result):
    global current_skill, course, current_level, busy

    current_skill = skill
    course = result
    current_level = 0
    busy = False

    record = skill_record(skill)
    record.setdefault("completed", [])
    record.setdefault("passed_levels", [])
    record.setdefault("final_passed", False)
    record["course"] = result
    save_data()

    search_button.config(state="normal")
    skill_title.config(text=f"Your {skill} course")
    status_label.config(text="Complete the topics and pass the exams to earn your certificate.")

    render_level()


# ============================================================
# LEVEL AND TOPIC DISPLAY
# ============================================================

def clear_lessons():
    for widget in lesson_frame.winfo_children():
        widget.destroy()


def render_level():
    if not course:
        return

    clear_lessons()

    record = skill_record(current_skill)
    passed = set(record.get("passed_levels", []))
    completed = set(record.get("completed", []))
    level = course["levels"][current_level]

    level_title.config(
        text=f"Level {current_level + 1}: {level['title']}"
    )

    for index, item in enumerate(level["topics"]):
        topic_id = f"{current_level}:{index}"

        card = tk.Frame(
            lesson_frame, bg=CARD, padx=16, pady=14
        )
        card.pack(fill="x", padx=4, pady=6)

        tk.Label(
            card,
            text=f"{index + 1:02d}  {item['title']}",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
            wraplength=650,
            justify="left"
        ).pack(fill="x")

        tk.Label(
            card,
            text=item.get("description", ""),
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=650
        ).pack(fill="x", pady=(7, 12))

        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x")

        tk.Button(
            row,
            text="▶ Watch One Video",
            command=lambda q=item.get("video_query", item["title"]): watch_video(q),
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=8
        ).pack(side="left")

        variable = tk.BooleanVar(value=topic_id in completed)

        tk.Checkbutton(
            row,
            text="Mark completed",
            variable=variable,
            command=lambda tid=topic_id, v=variable: mark_topic(tid, v.get()),
            bg=CARD,
            fg=GREEN,
            selectcolor=PANEL,
            activebackground=CARD,
            activeforeground=GREEN
        ).pack(side="right")

    all_done = all(
        f"{current_level}:{index}" in completed
        for index in range(5)
    )
    level_passed = current_level in passed

    exam_button.config(
        state="normal" if all_done or level_passed else "disabled",
        text="Retake Level Exam" if level_passed else "Take Level Exam"
    )

    prev_button.config(
        state="normal" if current_level > 0 else "disabled"
    )

    if current_level < 2:
        next_button.config(
            state="normal" if current_level in passed else "disabled"
        )
    else:
        next_button.config(state="disabled")

    update_progress_display()


def mark_topic(topic_id, is_completed):
    record = skill_record(current_skill)
    completed = record.setdefault("completed", [])

    if is_completed and topic_id not in completed:
        completed.append(topic_id)
    elif not is_completed and topic_id in completed:
        completed.remove(topic_id)

    save_data()
    render_level()


def update_progress_display():
    # Use the existing progress_text widget.
    record = skill_record(current_skill)

    total = 15
    completed = min(len(set(record.get("completed", []))), total)
    percentage = int(completed * 100 / total)

    progress_text.config(
        text=f"Course progress: {percentage}%  •  "
             f"{completed}/{total} topics completed"
    )

    progress_canvas.delete("all")
    progress_canvas.update_idletasks()
    width = max(progress_canvas.winfo_width(), 1)

    progress_canvas.create_rectangle(
        0, 0, width, 10,
        fill="#29354C",
        outline=""
    )
    progress_canvas.create_rectangle(
        0, 0, width * percentage / 100, 10,
        fill=GREEN,
        outline=""
    )


def previous_level():
    global current_level

    if current_level > 0:
        current_level -= 1
        render_level()


def next_level():
    global current_level

    record = skill_record(current_skill)

    # The current level must be passed before moving forward.
    if current_level < 2 and current_level in record.get("passed_levels", []):
        current_level += 1
        render_level()


# ============================================================
# EXAMS
# ============================================================

def start_level_exam():
    if not course:
        return

    record = skill_record(current_skill)
    required = {f"{current_level}:{i}" for i in range(5)}

    if not required.issubset(set(record.get("completed", []))):
        messagebox.showinfo(
            "Finish your lessons",
            "Complete all five topics in this level before taking the exam."
        )
        return

    run_exam(
        course["levels"][current_level]["exam"][:5],
        f"{course['levels'][current_level]['title']} Exam",
        finish_level_exam
    )


def finish_level_exam(score):
    record = skill_record(current_skill)

    if score >= 4:
        passed = record.setdefault("passed_levels", [])

        if current_level not in passed:
            passed.append(current_level)

        save_data()
        render_level()

        messagebox.showinfo(
            "Level passed!",
            f"You scored {score}/5 and passed this level."
        )

        if len(set(passed)) == 3:
            maybe_final_exam()
    else:
        messagebox.showwarning(
            "Try again",
            f"You scored {score}/5. You need at least 4 correct answers. "
            "Review your lessons and retake the exam."
        )


def maybe_final_exam():
    record = skill_record(current_skill)

    if (
        len(set(record.get("passed_levels", []))) == 3
        and not record.get("final_passed")
    ):
        if messagebox.askyesno(
            "Final exam unlocked",
            "You passed all three levels!\n\nTake the final exam now?"
        ):
            run_exam(
                course["final_exam"][:10],
                "Final Course Exam",
                finish_final_exam
            )


def finish_final_exam(score):
    record = skill_record(current_skill)

    if score >= 8:
        record["final_passed"] = True
        save_data()

        messagebox.showinfo(
            "Course completed!",
            f"You scored {score}/10 and passed the final exam."
        )
        generate_certificate()
    else:
        messagebox.showwarning(
            "Final exam not passed",
            f"You scored {score}/10. You need at least 8 correct answers. "
            "Review the course and try again."
        )


def run_exam(questions, title, callback):
    if not questions:
        messagebox.showerror("Exam error", "No exam questions are available.")
        return

    shuffled = list(questions)
    random.shuffle(shuffled)

    window = tk.Toplevel(root)
    window.title(title)
    window.geometry("760x650")
    window.minsize(600, 450)
    window.configure(bg=BG)
    window.transient(root)

    tk.Label(
        window,
        text=title,
        bg=BG,
        fg=TEXT,
        font=("Segoe UI", 19, "bold")
    ).pack(pady=(18, 4))

    tk.Label(
        window,
        text=f"{len(shuffled)} questions • Select one answer per question",
        bg=BG,
        fg=MUTED
    ).pack(pady=(0, 10))

    outer = tk.Frame(window, bg=BG)
    outer.pack(fill="both", expand=True, padx=15)

    exam_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(
        outer, orient="vertical", command=exam_canvas.yview
    )
    questions_frame = tk.Frame(exam_canvas, bg=BG)

    questions_frame.bind(
        "<Configure>",
        lambda event: exam_canvas.configure(
            scrollregion=exam_canvas.bbox("all")
        )
    )

    frame_id = exam_canvas.create_window(
        (0, 0), window=questions_frame, anchor="nw"
    )

    exam_canvas.bind(
        "<Configure>",
        lambda event: exam_canvas.itemconfigure(
            frame_id, width=event.width
        )
    )

    exam_canvas.configure(yscrollcommand=scrollbar.set)
    exam_canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    answers = []

    for number, question in enumerate(shuffled, start=1):
        card = tk.Frame(
            questions_frame, bg=CARD, padx=12, pady=12
        )
        card.pack(fill="x", pady=6, padx=4)

        tk.Label(
            card,
            text=f"{number}. {question['question']}",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 11, "bold"),
            wraplength=640,
            justify="left"
        ).pack(anchor="w", pady=(0, 8))

        variable = tk.IntVar(value=-1)
        answers.append((variable, question))

        for option_index, option in enumerate(question["options"]):
            tk.Radiobutton(
                card,
                text=option,
                variable=variable,
                value=option_index,
                bg=CARD,
                fg=TEXT,
                selectcolor=PANEL,
                activebackground=CARD,
                activeforeground=TEXT,
                wraplength=620,
                justify="left",
                anchor="w"
            ).pack(fill="x", anchor="w", pady=2)

    def submit_exam():
        unanswered = sum(
            1 for variable, _ in answers if variable.get() == -1
        )

        if unanswered and not messagebox.askyesno(
            "Unanswered questions",
            f"{unanswered} question(s) are unanswered. Submit anyway?",
            parent=window
        ):
            return

        score = sum(
            1 for variable, question in answers
            if variable.get() == question.get("answer", -99)
        )

        explanations = "\n\n".join(
            f"{i}. {question.get('explanation', '')}"
            for i, (_, question) in enumerate(answers, start=1)
        )

        window.destroy()

        messagebox.showinfo(
            "Exam result",
            f"Your score: {score}/{len(answers)}\n\n"
            f"Review:\n{explanations[:2500]}"
        )

        callback(score)

    tk.Button(
        window,
        text="Submit Exam",
        command=submit_exam,
        bg=GREEN,
        fg="#06251D",
        relief="flat",
        font=("Segoe UI", 11, "bold"),
        padx=18,
        pady=10
    ).pack(pady=14)


# ============================================================
# PDF CERTIFICATE
# ============================================================

def generate_certificate():
    if not current_skill:
        messagebox.showinfo("Choose a course", "Create or open a course first.")
        return

    record = skill_record(current_skill)

    if not record.get("final_passed"):
        messagebox.showwarning(
            "Not available",
            "Pass all three level exams and the final exam first."
        )
        return

    name = simpledialog.askstring(
        "Certificate",
        "Enter the name to print on your certificate:",
        parent=root
    )

    if not name or not name.strip():
        return

    os.makedirs(CERTIFICATE_DIR, exist_ok=True)

    safe_name = "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in name.strip()
    )
    safe_skill = "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in current_skill
    )

    path = os.path.abspath(os.path.join(
        CERTIFICATE_DIR,
        f"{safe_name}_{safe_skill}_certificate.pdf"
    ))

    pdf = pdf_canvas.Canvas(path, pagesize=landscape(A4))
    width, height = landscape(A4)

    pdf.setFillColorRGB(0.05, 0.09, 0.17)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    pdf.setStrokeColorRGB(0.51, 0.53, 0.97)
    pdf.setLineWidth(4)
    pdf.rect(24, 24, width - 48, height - 48, fill=0, stroke=1)

    pdf.setFillColorRGB(0.75, 0.79, 1.0)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(width / 2, height - 95, "FOCUSAI")

    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(
        width / 2, height - 155, "CERTIFICATE OF COMPLETION"
    )

    pdf.setFillColorRGB(0.72, 0.77, 0.85)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(
        width / 2, height - 205, "This certificate is awarded to"
    )

    pdf.setFillColorRGB(0.45, 0.9, 0.72)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(width / 2, height - 250, name.strip()[:50])

    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(
        width / 2, height - 295,
        f"For completing the {current_skill[:70]} course"
    )

    pdf.setFillColorRGB(0.72, 0.77, 0.85)
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(
        width / 2, height - 330,
        "All three levels completed and final exam passed"
    )

    pdf.drawCentredString(
        width / 2, 80,
        f"Completion date: {date.today().strftime('%d %B %Y')}"
    )

    pdf.save()

    record["certificate"] = path
    save_data()

    messagebox.showinfo(
        "Certificate created",
        f"Your certificate was saved here:\n\n{path}"
    )

    try:
        os.startfile(path)
    except (AttributeError, OSError):
        webbrowser.open_new_tab("file:///" + path.replace("\\", "/"))


# ============================================================
# USER INTERFACE
# ============================================================

root = tk.Tk()
root.title("FocusAI | Learn Anything")
root.geometry("1000x820")
root.minsize(760, 650)
root.configure(bg=BG)

style = ttk.Style()
style.theme_use("clam")
style.configure(
    "Vertical.TScrollbar",
    background=PANEL,
    troughcolor=BG
)

header = tk.Frame(root, bg=BG, padx=26, pady=20)
header.pack(fill="x")

tk.Label(
    header,
    text="✦ FocusAI",
    bg=BG,
    fg=TEXT,
    font=("Segoe UI", 25, "bold")
).pack(anchor="w")

tk.Label(
    header,
    text="Learn any skill, topic by topic.",
    bg=BG,
    fg=MUTED,
    font=("Segoe UI", 11)
).pack(anchor="w", pady=(3, 0))

search_panel = tk.Frame(root, bg=PANEL, padx=18, pady=18)
search_panel.pack(fill="x", padx=26, pady=(0, 18))

tk.Label(
    search_panel,
    text="WHAT DO YOU WANT TO LEARN?",
    bg=PANEL,
    fg=MUTED,
    font=("Segoe UI", 9, "bold")
).pack(anchor="w", pady=(0, 10))

search_row = tk.Frame(search_panel, bg=PANEL)
search_row.pack(fill="x")

skill_entry = tk.Entry(
    search_row,
    bg="#202C43",
    fg=TEXT,
    insertbackground=TEXT,
    relief="flat",
    font=("Segoe UI", 12)
)
skill_entry.pack(
    side="left", fill="x", expand=True, ipady=12, padx=(0, 12)
)
skill_entry.insert(0, "Java")
skill_entry.bind("<Return>", start_course)

search_button = tk.Button(
    search_row,
    text="Create Course →",
    command=start_course,
    bg=ACCENT,
    fg="white",
    activebackground=ACCENT,
    activeforeground="white",
    relief="flat",
    cursor="hand2",
    font=("Segoe UI", 10, "bold"),
    padx=16,
    pady=10
)
search_button.pack(side="right")

skill_title = tk.Label(
    root,
    text="Your learning space",
    bg=BG,
    fg=TEXT,
    font=("Segoe UI", 18, "bold")
)
skill_title.pack(anchor="w", padx=28)

status_label = tk.Label(
    root,
    text="Enter a skill and create your course.",
    bg=BG,
    fg=MUTED,
    font=("Segoe UI", 10)
)
status_label.pack(anchor="w", padx=28, pady=(4, 12))

level_title = tk.Label(
    root,
    text="",
    bg=BG,
    fg=TEXT,
    font=("Segoe UI", 15, "bold")
)
level_title.pack(anchor="w", padx=28, pady=(0, 10))

# This is the progress label used by update_progress_display().
progress_text = tk.Label(
    root,
    text="Course progress: 0%  •  0/15 topics completed",
    bg=BG,
    fg=GREEN,
    font=("Segoe UI", 10, "bold")
)
progress_text.pack(anchor="w", padx=28)

progress_canvas = tk.Canvas(
    root, height=10, bg=BG, highlightthickness=0
)
progress_canvas.pack(fill="x", padx=28, pady=(8, 12))

outer = tk.Frame(root, bg=BG)
outer.pack(fill="both", expand=True, padx=24)

lesson_canvas = tk.Canvas(
    outer,
    bg=BG,
    highlightthickness=0
)

scrollbar = ttk.Scrollbar(
    outer,
    orient="vertical",
    command=lesson_canvas.yview
)

lesson_frame = tk.Frame(lesson_canvas, bg=BG)

lesson_window = lesson_canvas.create_window(
    (0, 0),
    window=lesson_frame,
    anchor="nw"
)

def update_lesson_scroll(event=None):
    lesson_canvas.configure(
        scrollregion=lesson_canvas.bbox("all")
    )

lesson_frame.bind("<Configure>", update_lesson_scroll)

lesson_canvas.bind(
    "<Configure>",
    lambda event: lesson_canvas.itemconfigure(
        lesson_window,
        width=event.width
    )
)

lesson_canvas.configure(yscrollcommand=scrollbar.set)

lesson_canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Enable mouse-wheel scrolling over the lesson area
def scroll_lessons(event):
    lesson_canvas.yview_scroll(
        int(-1 * (event.delta / 120)),
        "units"
    )

lesson_canvas.bind("<MouseWheel>", scroll_lessons)
lesson_frame.bind("<MouseWheel>", scroll_lessons)

footer = tk.Frame(root, bg=BG, padx=24, pady=14)
footer.pack(fill="x")

prev_button = tk.Button(
    footer,
    text="← Previous Level",
    command=previous_level,
    bg=PANEL,
    fg=TEXT,
    relief="flat",
    padx=12,
    pady=9,
    state="disabled"
)
prev_button.pack(side="left")

exam_button = tk.Button(
    footer,
    text="Take Level Exam",
    command=start_level_exam,
    state="disabled",
    bg=GREEN,
    fg="#06251D",
    relief="flat",
    font=("Segoe UI", 10, "bold"),
    padx=14,
    pady=9
)
exam_button.pack(side="left", padx=8)

next_button = tk.Button(
    footer,
    text="Next Level →",
    command=next_level,
    state="disabled",
    bg=ACCENT,
    fg="white",
    relief="flat",
    padx=12,
    pady=9
)
next_button.pack(side="right")

certificate_button = tk.Button(
    footer,
    text="Get Certificate",
    command=generate_certificate,
    bg=PANEL,
    fg=GREEN,
    relief="flat",
    padx=12,
    pady=9
)
certificate_button.pack(side="right", padx=8)

root.mainloop()
