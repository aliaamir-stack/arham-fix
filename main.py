import json
import os
from datetime import datetime, timedelta, date
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import matplotlib.backends.backend_tkagg as tkagg
from matplotlib.figure import Figure

DATA_FILE = "data.json"

# ─────────────────────────────────────────────
# THEME SYSTEM
# ─────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":            "#0f1117",
        "surface":       "#1a1d27",
        "surface2":      "#22263a",
        "border":        "#2e3350",
        "accent":        "#6c63ff",
        "accent2":       "#ff6584",
        "accent3":       "#43d8c9",
        "text":          "#e8eaf6",
        "text_sub":      "#8b8fa8",
        "text_disabled": "#4a4d6a",
        "success":       "#43d8a0",
        "warning":       "#ffd166",
        "danger":        "#ef476f",
        "card_shadow":   "#00000066",
    },
    "light": {
        "bg":            "#f0f2ff",
        "surface":       "#ffffff",
        "surface2":      "#e8eaf6",
        "border":        "#c5c8e8",
        "accent":        "#5b54e8",
        "accent2":       "#e8476e",
        "accent3":       "#1ab8a8",
        "text":          "#1a1d3a",
        "text_sub":      "#5a5d7a",
        "text_disabled": "#a0a3c0",
        "success":       "#1db87a",
        "warning":       "#d4a017",
        "danger":        "#d93060",
        "card_shadow":   "#b0b4d033",
    }
}

# ─────────────────────────────────────────────
# DATA LAYER
# ─────────────────────────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"subjects": [], "timetable": {}, "sessions_log": {}, "goals": {}, "notes": {}, "theme": "dark"}
    with open(DATA_FILE, "r") as f:
        raw = json.load(f)
    raw.setdefault("sessions_log", {})
    raw.setdefault("goals", {})
    raw.setdefault("notes", {})
    raw.setdefault("theme", "dark")
    return raw

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
current_theme = data.get("theme", "dark")

def t(key):
    return THEMES[current_theme][key]

# ─────────────────────────────────────────────
# PRIORITY ALGORITHM
# ─────────────────────────────────────────────
def calculate_priority(subject, current_date=None):
    if current_date is None:
        current_date = date.today()
    exam = datetime.strptime(subject["exam_date"], "%Y-%m-%d").date()
    days_left = max((exam - current_date).days, 1)
    logged = sum(data["sessions_log"].get(subject["name"], {}).values())
    goal = data["goals"].get(subject["name"], 10)
    deficit = max(goal - logged / 60, 0)
    return (subject["difficulty"] * 2 + deficit) / days_left

# ─────────────────────────────────────────────
# TIMETABLE GENERATION
# ─────────────────────────────────────────────
def generate_timetable():
    if not data["subjects"]:
        messagebox.showwarning("No Subjects", "Add subjects before generating a timetable.")
        return

    today = date.today()
    # Preserve past schedules, overwrite from today onwards
    timetable = {
        k: v for k, v in data["timetable"].items()
        if datetime.strptime(k, "%Y-%m-%d").date() < today
    }
    
    last_exam = max(
        datetime.strptime(s["exam_date"], "%Y-%m-%d").date()
        for s in data["subjects"]
    )

    active = [
        s for s in data["subjects"]
        if datetime.strptime(s["exam_date"], "%Y-%m-%d").date() >= today
    ]

    current = today
    while current <= last_exam:
        day_str = str(current)
        is_weekend = current.weekday() >= 5
        total_minutes = 180 if is_weekend else 120

        ranked = sorted(active, key=lambda s: calculate_priority(s, current), reverse=True)

        sessions = []
        remaining = total_minutes
        i = 0
        while remaining >= 30 and ranked:
            s = ranked[i % len(ranked)]
            exam_date = datetime.strptime(s["exam_date"], "%Y-%m-%d").date()
            if exam_date < current:
                ranked.remove(s)
                continue
            sessions.append({"subject": s["name"], "minutes": 30, "done": False})
            remaining -= 30
            i += 1

        timetable[day_str] = sessions
        current += timedelta(days=1)

    data["timetable"] = timetable
    save_data(data)
    refresh_dashboard()
    messagebox.showinfo("✓ Done", "Timetable generated successfully!")

# ─────────────────────────────────────────────
# SESSION LOG
# ─────────────────────────────────────────────
def log_session(subject_name, minutes, day_str=None):
    if not day_str:
        day_str = str(date.today())
    data["sessions_log"].setdefault(subject_name, {})
    prev = data["sessions_log"][subject_name].get(day_str, 0)
    data["sessions_log"][subject_name][day_str] = prev + minutes
    save_data(data)

def mark_done(day, idx):
    sessions = data["timetable"].get(day, [])
    if idx < len(sessions):
        sessions[idx]["done"] = True
        log_session(sessions[idx]["subject"], sessions[idx]["minutes"], day_str=day)
        save_data(data)

# ─────────────────────────────────────────────
# STREAK CALCULATION
# ─────────────────────────────────────────────
def get_streak():
    streak = 0
    d = date.today()
    while True:
        day_str = str(d)
        sessions = data["timetable"].get(day_str, [])
        if not sessions:
            d -= timedelta(days=1)
            if (date.today() - d).days > 60:
                break
            continue
        if any(s.get("done") for s in sessions):
            streak += 1
            d -= timedelta(days=1)
        else:
            if d < date.today():
                break
            d -= timedelta(days=1)
    return streak

# ─────────────────────────────────────────────
# DAYS UNTIL NEXT EXAM
# ─────────────────────────────────────────────
def next_exam_info():
    today = date.today()
    upcoming = [
        s for s in data["subjects"]
        if datetime.strptime(s["exam_date"], "%Y-%m-%d").date() >= today
    ]
    if not upcoming:
        return None, None
    next_s = min(upcoming, key=lambda x: x["exam_date"])
    days = (datetime.strptime(next_s["exam_date"], "%Y-%m-%d").date() - today).days
    return next_s["name"], days

# ─────────────────────────────────────────────
# RESCHEDULE MISSED SESSION
# ─────────────────────────────────────────────
def reschedule_missed(day, idx):
    sessions = data["timetable"].get(day, [])
    if idx >= len(sessions):
        return
    missed = sessions.pop(idx)
    current = datetime.strptime(day, "%Y-%m-%d").date()
    for _ in range(30):
        current += timedelta(days=1)
        next_day = str(current)
        data["timetable"].setdefault(next_day, [])
        if len(data["timetable"][next_day]) < 8:
            data["timetable"][next_day].append(missed)
            break
    save_data(data)
    messagebox.showinfo("Rescheduled", f"'{missed['subject']}' moved to {current}.")
    refresh_dashboard()

# ─────────────────────────────────────────────
# HELPER: difficulty stars
# ─────────────────────────────────────────────
def stars(n):
    return "★" * n + "☆" * (5 - n)

# ─────────────────────────────────────────────
# GUI ROOT
# ─────────────────────────────────────────────
root = tk.Tk()
root.title("StudyFlow — Smart Study Planner")
root.geometry("1100x720")
root.minsize(900, 600)
root.configure(bg=t("bg"))

def font(size=11, weight="normal", family="Helvetica Neue"):
    return (family, size, weight)

# ─────────────────────────────────────────────
# REUSABLE WIDGET BUILDERS
# ─────────────────────────────────────────────
def make_card(parent, **kwargs):
    f = tk.Frame(parent, bg=t("surface"), relief="flat", bd=0, **kwargs)
    f.configure(highlightbackground=t("border"), highlightthickness=1)
    return f

def get_bg(widget):
    """Safely retrieve background color from any widget."""
    try:
        return widget.cget("bg")
    except Exception:
        return t("bg")

def label(parent, text, size=11, weight="normal", color=None, **kwargs):
    color = color or t("text")
    return tk.Label(parent, text=text, bg=get_bg(parent), fg=color,
                    font=font(size, weight), **kwargs)

def sublabel(parent, text, size=10, **kwargs):
    return tk.Label(parent, text=text, bg=get_bg(parent), fg=t("text_sub"),
                    font=font(size), **kwargs)

def _lighten(hex_color, amount=20):
    hex_color = hex_color.lstrip("#")
    r = min(int(hex_color[0:2], 16) + amount, 255)
    g = min(int(hex_color[2:4], 16) + amount, 255)
    b = min(int(hex_color[4:6], 16) + amount, 255)
    return f"#{r:02x}{g:02x}{b:02x}"

def pill_button(parent, text, cmd, color=None, text_color=None, width=18):
    color = color or t("accent")
    text_color = text_color or "#ffffff"
    btn = tk.Button(
        parent, text=text, command=cmd, width=width,
        bg=color, fg=text_color, activebackground=color,
        activeforeground=text_color, relief="flat", bd=0,
        font=font(10, "bold"), cursor="hand2",
        padx=10, pady=6
    )
    btn.bind("<Enter>", lambda e: btn.configure(bg=_lighten(color)))
    btn.bind("<Leave>", lambda e: btn.configure(bg=color))
    return btn

# ─────────────────────────────────────────────
# MAIN LAYOUT (sidebar + content)
# ─────────────────────────────────────────────
sidebar = tk.Frame(root, bg=t("surface"), width=200)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

content_area = tk.Frame(root, bg=t("bg"))
content_area.pack(side="left", fill="both", expand=True)

pages = {}

def show_page(name):
    for p in pages.values():
        try:
            p.pack_forget()
        except Exception:
            pass
    if name in pages:
        pages[name].pack(fill="both", expand=True)
    refresh_active_nav(name)

nav_buttons = {}

def make_nav_btn(parent, icon, label_text, page_name):
    frame = tk.Frame(parent, bg=t("surface"), cursor="hand2")
    frame.pack(fill="x", pady=2)

    inner = tk.Frame(frame, bg=t("surface"))
    inner.pack(fill="x", padx=10, pady=6)

    icon_lbl = tk.Label(inner, text=icon, bg=t("surface"), fg=t("text_sub"), font=font(14))
    icon_lbl.pack(side="left", padx=(4, 8))

    txt_lbl = tk.Label(inner, text=label_text, bg=t("surface"), fg=t("text_sub"), font=font(10))
    txt_lbl.pack(side="left")

    def on_click(e=None):
        show_page(page_name)

    all_widgets = (frame, inner, icon_lbl, txt_lbl)
    for w in all_widgets:
        w.bind("<Button-1>", on_click)
        w.bind("<Enter>", lambda e, ws=all_widgets, pn=page_name: [
            w.configure(bg=t("surface2"))
            for w in ws
            if nav_buttons.get("active") != pn
        ])
        w.bind("<Leave>", lambda e, ws=all_widgets, pn=page_name: [
            w.configure(bg=t("surface"))
            for w in ws
            if nav_buttons.get("active") != pn
        ])

    nav_buttons[page_name] = (frame, inner, icon_lbl, txt_lbl)
    return frame

# FIX: safely skip non-tuple entries (e.g. the "active" string key)
def refresh_active_nav(active_name):
    nav_buttons["active"] = active_name
    for name, value in nav_buttons.items():
        if name == "active" or not isinstance(value, tuple):
            continue
        frame, inner, icon_lbl, txt_lbl = value
        if name == active_name:
            for w in (frame, inner):
                w.configure(bg=t("accent"))
            icon_lbl.configure(bg=t("accent"), fg="#ffffff")
            txt_lbl.configure(bg=t("accent"), fg="#ffffff", font=font(10, "bold"))
        else:
            for w in (frame, inner):
                w.configure(bg=t("surface"))
            icon_lbl.configure(bg=t("surface"), fg=t("text_sub"), font=font(14))
            txt_lbl.configure(bg=t("surface"), fg=t("text_sub"), font=font(10))

# ─────────────────────────────────────────────
# SIDEBAR CONTENT (rebuilt on theme change)
# ─────────────────────────────────────────────
sidebar_widgets = []  # track so we can destroy & rebuild

def build_sidebar():
    """Build (or rebuild) all sidebar content."""
    global sidebar_widgets
    for w in sidebar_widgets:
        try:
            w.destroy()
        except Exception:
            pass
    sidebar_widgets.clear()
    # also clear old nav_button entries (keep "active")
    active = nav_buttons.get("active", "dashboard")
    for k in [k for k in nav_buttons if k != "active"]:
        del nav_buttons[k]

    def add(w):
        sidebar_widgets.append(w)
        return w

    add(tk.Frame(sidebar, bg=t("accent"), height=4)).pack(fill="x")
    add(tk.Label(sidebar, text="StudyFlow", bg=t("surface"), fg=t("accent"),
                 font=font(15, "bold"))).pack(pady=(18, 4))
    add(tk.Label(sidebar, text="Smart Study Planner", bg=t("surface"), fg=t("text_sub"),
                 font=font(8))).pack(pady=(0, 20))

    sep1 = ttk.Separator(sidebar, orient="horizontal")
    sep1.pack(fill="x", padx=10, pady=4)
    sidebar_widgets.append(sep1)

    add(make_nav_btn(sidebar, "◈", "Dashboard", "dashboard"))
    add(make_nav_btn(sidebar, "⊞", "Subjects",  "subjects"))
    add(make_nav_btn(sidebar, "⊟", "Timetable", "timetable"))
    add(make_nav_btn(sidebar, "⊡", "Progress",  "progress"))
    add(make_nav_btn(sidebar, "⊠", "Notes",     "notes"))

    sep2 = ttk.Separator(sidebar, orient="horizontal")
    sep2.pack(fill="x", padx=10, pady=12)
    sidebar_widgets.append(sep2)

    theme_label = "☀  Light Mode" if current_theme == "dark" else "🌙  Dark Mode"
    theme_btn = tk.Button(
        sidebar, text=theme_label,
        bg=t("surface2"), fg=t("text"),
        relief="flat", font=font(9), cursor="hand2", command=toggle_theme,
        activebackground=t("border"), activeforeground=t("text")
    )
    theme_btn.pack(fill="x", padx=14, pady=4)
    sidebar_widgets.append(theme_btn)

    # Restore active highlight
    refresh_active_nav(active)

def toggle_theme():
    global current_theme
    current_theme = "light" if current_theme == "dark" else "dark"
    data["theme"] = current_theme
    save_data(data)
    rebuild_ui()

# ─────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────
def build_dashboard():
    page = tk.Frame(content_area, bg=t("bg"))
    pages["dashboard"] = page

    hdr = tk.Frame(page, bg=t("bg"))
    hdr.pack(fill="x", padx=24, pady=(20, 4))
    label(hdr, "Dashboard", 18, "bold").pack(side="left")
    sublabel(hdr, date.today().strftime("%A, %d %B %Y")).pack(side="right", pady=8)

    # Stat cards
    stats_row = tk.Frame(page, bg=t("bg"))
    stats_row.pack(fill="x", padx=24, pady=8)

    def stat_card(parent, icon, value_text, lbl_text, color):
        card = make_card(parent)
        card.pack(side="left", fill="both", expand=True, padx=6, pady=4)
        tk.Label(card, text=icon,       bg=t("surface"), fg=color,      font=font(22)).pack(pady=(14, 2))
        tk.Label(card, text=value_text, bg=t("surface"), fg=t("text"),  font=font(20, "bold")).pack()
        tk.Label(card, text=lbl_text,   bg=t("surface"), fg=t("text_sub"), font=font(9)).pack(pady=(0, 14))

    streak          = get_streak()
    total_subjects  = len(data["subjects"])
    next_name, next_days = next_exam_info()
    today_sessions  = data["timetable"].get(str(date.today()), [])
    done_today      = sum(1 for s in today_sessions if s.get("done"))

    stat_card(stats_row, "🔥", str(streak),         "Day Streak",      t("warning"))
    stat_card(stats_row, "📚", str(total_subjects),  "Subjects",        t("accent"))
    stat_card(stats_row, "✓",  f"{done_today}/{len(today_sessions)}", "Today's Sessions", t("success"))
    stat_card(stats_row, "📅",
              f"{next_days}d" if next_days is not None else "—",
              f"Until {next_name}" if next_name else "No exams",
              t("accent2"))

    # Middle columns
    mid = tk.Frame(page, bg=t("bg"))
    mid.pack(fill="both", expand=True, padx=24, pady=8)

    left_col = tk.Frame(mid, bg=t("bg"))
    left_col.pack(side="left", fill="both", expand=True, padx=(0, 8))

    right_col = tk.Frame(mid, bg=t("bg"))
    right_col.pack(side="left", fill="y", ipadx=8)

    # Today's schedule card
    today_card = make_card(left_col)
    today_card.pack(fill="both", expand=True, pady=4)
    label(today_card, "  Today's Schedule", 12, "bold").pack(anchor="w", pady=(12, 4))
    ttk.Separator(today_card).pack(fill="x", padx=10)

    scroll_frame = tk.Frame(today_card, bg=t("surface"))
    scroll_frame.pack(fill="both", expand=True, padx=10, pady=6)

    if not today_sessions:
        sublabel(scroll_frame, "No sessions scheduled today.").pack(pady=20)
    else:
        for i, s in enumerate(today_sessions):
            row_bg = t("surface2") if i % 2 == 0 else t("surface")
            row = tk.Frame(scroll_frame, bg=row_bg)
            row.pack(fill="x", pady=1)
            done_icon = "✅" if s.get("done") else "○"
            tk.Label(row, text=done_icon,    bg=row_bg, fg=t("success"),  font=font(11)).pack(side="left", padx=8, pady=4)
            tk.Label(row, text=s["subject"], bg=row_bg, fg=t("text"),     font=font(10)).pack(side="left")
            tk.Label(row, text=f"{s['minutes']} min", bg=row_bg, fg=t("text_sub"), font=font(9)).pack(side="right", padx=8)

    # Quick actions card
    qa_card = make_card(right_col, width=200)
    qa_card.pack(fill="x", pady=4)
    qa_card.pack_propagate(False)
    label(qa_card, "  Quick Actions", 11, "bold").pack(anchor="w", pady=(12, 6))
    ttk.Separator(qa_card).pack(fill="x", padx=10)
    pill_button(qa_card, "＋ Add Subject",      open_add_subject_dialog, t("accent"),   width=22).pack(pady=6, padx=10)
    pill_button(qa_card, "⚙ Generate Timetable", generate_timetable,    t("accent3"), text_color=t("bg"), width=22).pack(pady=6, padx=10)
    pill_button(qa_card, "⊞ View Progress",     lambda: show_page("progress"), t("surface2"), text_color=t("text"), width=22).pack(pady=6, padx=10)

    return page

# ─────────────────────────────────────────────
# PAGE: SUBJECTS
# ─────────────────────────────────────────────
def build_subjects_page():
    page = tk.Frame(content_area, bg=t("bg"))
    pages["subjects"] = page

    hdr = tk.Frame(page, bg=t("bg"))
    hdr.pack(fill="x", padx=24, pady=(20, 4))
    label(hdr, "Subjects", 18, "bold").pack(side="left")
    pill_button(hdr, "＋ Add Subject", open_add_subject_dialog, t("accent"), width=16).pack(side="right", pady=4)

    list_card = make_card(page)
    list_card.pack(fill="both", expand=True, padx=24, pady=8)

    cols = ("Name", "Exam Date", "Difficulty", "Goal (h)", "Logged (h)", "Days Left")
    tree = ttk.Treeview(list_card, columns=cols, show="headings", height=16)

    style = ttk.Style()
    style.theme_use("default")
    style.configure("Treeview",
                    background=t("surface"),
                    foreground=t("text"),
                    fieldbackground=t("surface"),
                    rowheight=34,
                    font=("Helvetica Neue", 10))
    style.configure("Treeview.Heading",
                    background=t("surface2"),
                    foreground=t("text"),
                    font=("Helvetica Neue", 10, "bold"),
                    relief="flat")
    style.map("Treeview", background=[("selected", t("accent"))])

    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, anchor="center", width=130)
    tree.column("Name", width=180, anchor="w")

    def refresh_subjects():
        tree.delete(*tree.get_children())
        today = date.today()
        for s in data["subjects"]:
            exam_dt   = datetime.strptime(s["exam_date"], "%Y-%m-%d").date()
            days_left = (exam_dt - today).days
            logged_min = sum(data["sessions_log"].get(s["name"], {}).values())
            goal       = data["goals"].get(s["name"], 10)
            tag = "past" if days_left < 0 else ("soon" if days_left <= 7 else "ok")
            tree.insert("", "end", values=(
                s["name"], s["exam_date"], stars(s["difficulty"]),
                goal, round(logged_min / 60, 1), days_left
            ), tags=(tag,))
        tree.tag_configure("past", foreground=t("text_disabled"))
        tree.tag_configure("soon", foreground=t("danger"))
        tree.tag_configure("ok",   foreground=t("text"))

    refresh_subjects()
    tree.pack(fill="both", expand=True, padx=10, pady=10)

    btn_row = tk.Frame(page, bg=t("bg"))
    btn_row.pack(fill="x", padx=24, pady=(0, 12))

    def delete_selected():
        sel = tree.selection()
        if not sel:
            return
        name = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Delete", f"Remove '{name}'?"):
            data["subjects"] = [s for s in data["subjects"] if s["name"] != name]
            save_data(data)
            refresh_subjects()
            refresh_dashboard()

    def edit_goal():
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Hint", "Select a subject first.")
            return
        name = tree.item(sel[0])["values"][0]
        g = simpledialog.askinteger("Study Goal", f"Hours goal for '{name}':", minvalue=1, maxvalue=500)
        if g:
            data["goals"][name] = g
            save_data(data)
            refresh_subjects()

    pill_button(btn_row, "🗑 Delete Selected", delete_selected, t("danger"),  width=18).pack(side="left", padx=4)
    pill_button(btn_row, "🎯 Set Study Goal",  edit_goal,       t("accent3"), text_color=t("bg"), width=18).pack(side="left", padx=4)

    return page

# ─────────────────────────────────────────────
# PAGE: TIMETABLE
# ─────────────────────────────────────────────
def build_timetable_page():
    page = tk.Frame(content_area, bg=t("bg"))
    pages["timetable"] = page

    hdr = tk.Frame(page, bg=t("bg"))
    hdr.pack(fill="x", padx=24, pady=(20, 4))
    label(hdr, "Timetable", 18, "bold").pack(side="left")
    pill_button(hdr, "⚙ Generate", generate_timetable, t("accent"), width=14).pack(side="right", pady=4)

    dp_row = tk.Frame(page, bg=t("bg"))
    dp_row.pack(fill="x", padx=24, pady=4)

    selected_date = tk.StringVar(value=str(date.today()))
    sublabel(dp_row, "Viewing date:").pack(side="left")
    tk.Entry(dp_row, textvariable=selected_date, bg=t("surface2"),
             fg=t("text"), insertbackground=t("text"),
             relief="flat", font=font(10), width=14).pack(side="left", padx=8)

    session_frame = tk.Frame(page, bg=t("bg"))
    session_frame.pack(fill="both", expand=True, padx=24, pady=4)

    def load_day_sessions():
        for w in session_frame.winfo_children():
            w.destroy()

        day = selected_date.get().strip()
        sessions = data["timetable"].get(day, [])

        card = make_card(session_frame)
        card.pack(fill="both", expand=True)

        weekday_name = ""
        try:
            weekday_name = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %d %B %Y")
        except Exception:
            pass

        label(card, f"  {weekday_name or day}", 12, "bold").pack(anchor="w", pady=(12, 4))
        ttk.Separator(card).pack(fill="x", padx=10)

        if not sessions:
            sublabel(card, "No sessions for this day.").pack(pady=30)
            return

        try:
            if datetime.strptime(day, "%Y-%m-%d").weekday() >= 5:
                tk.Label(card, text=" WEEKEND — Extended Study Day ",
                         bg=t("accent3"), fg=t("bg"), font=font(8, "bold")).pack(anchor="e", padx=12, pady=4)
        except Exception:
            pass

        for i, s in enumerate(sessions):
            row_bg = t("surface2") if i % 2 == 0 else t("surface")
            row = tk.Frame(card, bg=row_bg, highlightbackground=t("border"), highlightthickness=1)
            row.pack(fill="x", padx=10, pady=2)

            status_color = t("success") if s.get("done") else t("text_sub")
            status_text  = "✅ Done" if s.get("done") else "○ Pending"

            tk.Label(row, text=f"  {i+1}.",      bg=row_bg, fg=t("text_sub"), font=font(9)).pack(side="left", pady=8)
            tk.Label(row, text=s["subject"],      bg=row_bg, fg=t("text"),    font=font(10, "bold")).pack(side="left", padx=8)
            tk.Label(row, text=f"{s['minutes']} min", bg=row_bg, fg=t("accent"),   font=font(9)).pack(side="left")
            tk.Label(row, text=status_text,       bg=row_bg, fg=status_color, font=font(9)).pack(side="right", padx=8)

            if not s.get("done"):
                def make_done_cmd(idx=i, d=day):
                    def cmd():
                        mark_done(d, idx)
                        load_day_sessions()
                        refresh_dashboard()
                    return cmd

                def make_miss_cmd(idx=i, d=day):
                    def cmd():
                        reschedule_missed(d, idx)
                        load_day_sessions()
                    return cmd

                pill_button(row, "Mark Done",   make_done_cmd(), t("success"), text_color=t("bg"), width=10).pack(side="right", padx=4, pady=4)
                pill_button(row, "Reschedule",  make_miss_cmd(), t("warning"), text_color=t("bg"), width=10).pack(side="right", padx=4, pady=4)

    pill_button(dp_row, "Load", load_day_sessions, t("accent"), width=8).pack(side="left", padx=4)

    def nav_day(delta):
        try:
            d = datetime.strptime(selected_date.get(), "%Y-%m-%d").date()
            selected_date.set(str(d + timedelta(days=delta)))
            load_day_sessions()
        except Exception:
            pass

    pill_button(dp_row, "◀ Prev", lambda: nav_day(-1), t("surface2"), text_color=t("text"), width=8).pack(side="left", padx=2)
    pill_button(dp_row, "Next ▶", lambda: nav_day(1),  t("surface2"), text_color=t("text"), width=8).pack(side="left", padx=2)

    load_day_sessions()
    return page

# ─────────────────────────────────────────────
# PAGE: PROGRESS
# ─────────────────────────────────────────────
def build_progress_page():
    page = tk.Frame(content_area, bg=t("bg"))
    pages["progress"] = page

    hdr = tk.Frame(page, bg=t("bg"))
    hdr.pack(fill="x", padx=24, pady=(20, 4))
    label(hdr, "Progress & Analytics", 18, "bold").pack(side="left")

    # Bar chart card
    chart_card = make_card(page)
    chart_card.pack(fill="both", expand=True, padx=24, pady=8)
    label(chart_card, "  Hours Studied by Subject", 12, "bold").pack(anchor="w", pady=(10, 4))
    ttk.Separator(chart_card).pack(fill="x", padx=10)

    if not data["sessions_log"]:
        sublabel(chart_card, "No study sessions logged yet.").pack(pady=40)
    else:
        totals = {
            subj: sum(days.values()) / 60
            for subj, days in data["sessions_log"].items()
        }

        fig = Figure(figsize=(7, 3.2), dpi=100, facecolor=t("surface"))
        ax  = fig.add_subplot(111)
        ax.set_facecolor(t("surface2"))

        subjects_list = list(totals.keys())
        hours_list    = [totals[s] for s in subjects_list]
        bar_colors    = [t("accent"), t("accent2"), t("accent3"), t("warning"), t("success")]

        bars = ax.bar(
            subjects_list, hours_list,
            color=[bar_colors[i % len(bar_colors)] for i in range(len(subjects_list))],
            edgecolor=t("border"), linewidth=0.8
        )

        ax.set_xlabel("Subjects", color=t("text_sub"), fontsize=9)
        ax.set_ylabel("Hours",    color=t("text_sub"), fontsize=9)
        ax.tick_params(colors=t("text_sub"), labelsize=8)

        # FIX: ax.spines is a dict-like object — iterate with .values()
        for spine in ax.spines.values():
            spine.set_color(t("border"))

        for bar, val in zip(bars, hours_list):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    f"{val:.1f}h", ha="center", va="bottom",
                    color=t("text"), fontsize=8)

        fig.tight_layout()
        canvas = tkagg.FigureCanvasTkAgg(fig, master=chart_card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    # Goal progress bars
    goal_card = make_card(page)
    goal_card.pack(fill="x", padx=24, pady=(0, 12))
    label(goal_card, "  Goal Progress", 12, "bold").pack(anchor="w", pady=(10, 4))
    ttk.Separator(goal_card).pack(fill="x", padx=10)

    gp_frame = tk.Frame(goal_card, bg=t("surface"))
    gp_frame.pack(fill="x", padx=10, pady=8)

    for s in data["subjects"]:
        name       = s["name"]
        goal_h     = data["goals"].get(name, 10)
        logged_min = sum(data["sessions_log"].get(name, {}).values())
        logged_h   = logged_min / 60
        pct        = min(logged_h / goal_h, 1.0) if goal_h > 0 else 0

        row = tk.Frame(gp_frame, bg=t("surface"))
        row.pack(fill="x", pady=3)

        tk.Label(row, text=name, bg=t("surface"), fg=t("text"),
                 font=font(9), width=18, anchor="w").pack(side="left")

        bar_bg = tk.Canvas(row, bg=t("surface2"), height=12, width=240, highlightthickness=0)
        bar_bg.pack(side="left", padx=6)
        fill_w = int(240 * pct)
        bar_color = t("success") if pct >= 1 else (t("warning") if pct > 0.5 else t("accent"))
        bar_bg.create_rectangle(0, 0, fill_w, 12, fill=bar_color, outline="")

        tk.Label(row, text=f"{logged_h:.1f}/{goal_h}h  ({int(pct*100)}%)",
                 bg=t("surface"), fg=t("text_sub"), font=font(8)).pack(side="left", padx=4)

    return page

# ─────────────────────────────────────────────
# PAGE: NOTES
# ─────────────────────────────────────────────
def build_notes_page():
    page = tk.Frame(content_area, bg=t("bg"))
    pages["notes"] = page

    hdr = tk.Frame(page, bg=t("bg"))
    hdr.pack(fill="x", padx=24, pady=(20, 4))
    label(hdr, "Study Notes", 18, "bold").pack(side="left")

    sel_row = tk.Frame(page, bg=t("bg"))
    sel_row.pack(fill="x", padx=24, pady=4)
    sublabel(sel_row, "Subject:").pack(side="left")

    subject_names    = [s["name"] for s in data["subjects"]] or ["No subjects"]
    selected_subject = tk.StringVar(value=subject_names[0])

    subject_menu = ttk.Combobox(sel_row, textvariable=selected_subject,
                                values=subject_names, state="readonly", width=20)
    subject_menu.pack(side="left", padx=8)

    note_card = make_card(page)
    note_card.pack(fill="both", expand=True, padx=24, pady=8)
    label(note_card, "  Notes", 12, "bold").pack(anchor="w", pady=(10, 4))
    ttk.Separator(note_card).pack(fill="x", padx=10)

    text_area = tk.Text(note_card, bg=t("surface2"), fg=t("text"),
                        insertbackground=t("text"), relief="flat",
                        font=font(10), wrap="word", padx=12, pady=8,
                        selectbackground=t("accent"), selectforeground="#ffffff")
    text_area.pack(fill="both", expand=True, padx=10, pady=10)

    def load_note(*args):
        text_area.delete("1.0", "end")
        note = data["notes"].get(selected_subject.get(), "")
        text_area.insert("1.0", note)

    def save_note():
        data["notes"][selected_subject.get()] = text_area.get("1.0", "end").strip()
        save_data(data)
        messagebox.showinfo("Saved", "Note saved!")

    subject_menu.bind("<<ComboboxSelected>>", load_note)
    load_note()

    btn_row = tk.Frame(page, bg=t("bg"))
    btn_row.pack(fill="x", padx=24, pady=(0, 12))
    pill_button(btn_row, "💾 Save Note", save_note, t("accent"), width=16).pack(side="left", padx=4)

    return page

# ─────────────────────────────────────────────
# ADD SUBJECT DIALOG
# ─────────────────────────────────────────────
def open_add_subject_dialog():
    dialog = tk.Toplevel(root)
    dialog.title("Add Subject")
    dialog.geometry("420x380")
    dialog.resizable(False, False)
    dialog.configure(bg=t("bg"))
    dialog.grab_set()

    label(dialog, "Add New Subject", 15, "bold").pack(pady=(20, 4))
    sublabel(dialog, "Fill in the details below").pack(pady=(0, 16))

    form = tk.Frame(dialog, bg=t("bg"))
    form.pack(fill="x", padx=30)

    def form_row(lbl_text, default=""):
        r = tk.Frame(form, bg=t("bg"))
        r.pack(fill="x", pady=4)
        tk.Label(r, text=lbl_text, bg=t("bg"), fg=t("text_sub"),
                 font=font(9), width=18, anchor="w").pack(side="left")
        entry = tk.Entry(r, bg=t("surface2"), fg=t("text"),
                         insertbackground=t("text"), relief="flat",
                         font=font(10), width=22)
        if default:
            entry.insert(0, default)
        entry.pack(side="left", padx=6, ipady=4)
        return entry

    name_e = form_row("Subject Name")
    exam_e = form_row("Exam Date (YYYY-MM-DD)")
    diff_e = form_row("Difficulty (1–5)")
    goal_e = form_row("Study Goal (hours)", "10")

    def submit():
        name     = name_e.get().strip()
        exam     = exam_e.get().strip()
        diff_raw = diff_e.get().strip()
        goal_raw = goal_e.get().strip()

        if not name or not exam or not diff_raw:
            messagebox.showerror("Error", "All fields are required.", parent=dialog)
            return
        try:
            datetime.strptime(exam, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.", parent=dialog)
            return
        try:
            diff = int(diff_raw)
            assert 1 <= diff <= 5
        except (ValueError, AssertionError):
            messagebox.showerror("Error", "Difficulty must be a number between 1 and 5.", parent=dialog)
            return
        try:
            goal = int(goal_raw) if goal_raw else 10
        except ValueError:
            goal = 10

        if any(s["name"] == name for s in data["subjects"]):
            messagebox.showerror("Error", f"Subject '{name}' already exists.", parent=dialog)
            return

        data["subjects"].append({"name": name, "exam_date": exam, "difficulty": diff})
        data["goals"][name] = goal
        save_data(data)
        dialog.destroy()
        refresh_all_pages()
        messagebox.showinfo("Success", f"'{name}' added!")

    tk.Frame(dialog, bg=t("bg")).pack(pady=8)
    pill_button(dialog, "＋ Add Subject", submit,         t("accent"),   width=22).pack(pady=4)
    pill_button(dialog, "Cancel",         dialog.destroy, t("surface2"), text_color=t("text"), width=22).pack(pady=4)

# ─────────────────────────────────────────────
# REFRESH HELPERS
# ─────────────────────────────────────────────
def refresh_dashboard():
    old = pages.pop("dashboard", None)
    if old:
        try:
            old.destroy()
        except Exception:
            pass
    build_dashboard()
    if nav_buttons.get("active") == "dashboard":
        show_page("dashboard")

def refresh_all_pages():
    for pg in list(pages.values()):
        try:
            pg.destroy()
        except Exception:
            pass
    pages.clear()
    build_all_pages()
    show_page(nav_buttons.get("active", "dashboard"))

def build_all_pages():
    build_dashboard()
    build_subjects_page()
    build_timetable_page()
    build_progress_page()
    build_notes_page()

def rebuild_ui():
    """Full rebuild on theme toggle — sidebar + all pages."""
    sidebar.configure(bg=t("surface"))
    content_area.configure(bg=t("bg"))
    root.configure(bg=t("bg"))
    build_sidebar()
    refresh_all_pages()

# ─────────────────────────────────────────────
# BOOT
# ─────────────────────────────────────────────
build_sidebar()
build_all_pages()
show_page("dashboard")

root.mainloop()