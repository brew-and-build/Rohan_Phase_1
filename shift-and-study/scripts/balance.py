#!/usr/bin/env python3
"""Fit a working student's study tasks around classes and job shifts, and flag crunch days.

Commands:
  python3 scripts/balance.py shifts --set "Tue 16:00-21:00 Library desk; Thu 16:00-21:00 Library desk"
  python3 scripts/balance.py shifts --show | --clear
  python3 scripts/balance.py plan --input week.json --now 14:30
  python3 scripts/balance.py plan --sample        # bundled example; saved shifts are left alone

Saved shifts live in ~/.config/shift-and-study/shifts.json. Pass --now as the student's local
time: the sandbox clock may be in another time zone.
Exit codes: 0 ok, 2 bad input, 3 nothing to plan.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.expanduser("~/.config/shift-and-study")
SHIFTS_FILE = os.path.join(STATE_DIR, "shifts.json")
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MIN_BLOCK = 30  # minutes; shorter gaps are not worth a study block
MAX_BLOCK = 120  # minutes per sitting
BREAK = 10  # minutes between blocks
BUFFER = 20  # minutes of travel/rest around a shift or class


def fail(code, msg):
    print(msg)
    sys.exit(code)


def to_min(hhmm):
    try:
        h, m = hhmm.split(":")
        v = int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        fail(2, f"Bad time {hhmm!r}: use HH:MM, for example 16:00")
    if not 0 <= v <= 1440:
        fail(2, f"Bad time {hhmm!r}")
    return v


def fmt(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_date(s):
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        fail(2, f"Bad date {s!r}: use YYYY-MM-DD")


def parse_due(s):
    """Return (date, minute-of-day). A bare date means end of that day."""
    if "T" in s:
        d, t = s.split("T", 1)
        return parse_date(d), to_min(t[:5])
    return parse_date(s), 23 * 60 + 59


def parse_shifts(raw):
    shifts = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        bits = part.split(None, 2)
        if len(bits) < 2 or "-" not in bits[1] or bits[0][:3].title() not in WEEKDAYS:
            fail(2, f"Bad shift {part!r}: use 'Tue 16:00-21:00 Library desk'")
        start, end = bits[1].split("-", 1)
        s, e = to_min(start), to_min(end)
        if e <= s:
            e = 1440  # an overnight shift counts until midnight
        shifts.append({"weekday": bits[0][:3].title(), "start": fmt(s), "end": fmt(e),
                       "title": bits[2] if len(bits) > 2 else "Work"})
    if not shifts:
        fail(2, "No shifts given")
    return shifts


def cmd_shifts(a):
    if a.set:
        shifts = parse_shifts(a.set)
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(SHIFTS_FILE, "w") as f:
            json.dump(shifts, f)
    elif a.clear:
        if os.path.exists(SHIFTS_FILE):
            os.remove(SHIFTS_FILE)
        print("Saved shifts cleared.")
        return
    shifts = load_saved_shifts()
    if not shifts:
        fail(3, "No shifts saved yet.")
    for s in shifts:
        print(f"{s['weekday']} {s['start']}-{s['end']} {s['title']}")


def load_saved_shifts():
    try:
        with open(SHIFTS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def merge(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def free_windows(day_start, day_end, busy):
    """Gaps between busy intervals (each padded by BUFFER), inside the awake window."""
    padded = merge([(max(0, s - BUFFER), min(1440, e + BUFFER)) for s, e in busy])
    wins, cur = [], day_start
    for s, e in padded:
        if s > cur:
            wins.append([cur, min(s, day_end)])
        cur = max(cur, e)
    if cur < day_end:
        wins.append([cur, day_end])
    return [w for w in wins if w[1] - w[0] >= MIN_BLOCK]


def build(data, now_min):
    today = parse_date(data.get("today"))
    n_days = int(data.get("days", 7))
    wake, sleep = to_min(data.get("wake", "07:30")), to_min(data.get("sleep", "23:30"))
    cap = float(data.get("max_study_hours_per_day", 4)) * 60

    days = []
    for i in range(n_days):
        d = today + timedelta(days=i)
        events = []
        for b in data.get("busy", []):
            if parse_date(b["date"]) == d:
                events.append((to_min(b["start"]), to_min(b["end"]), b.get("kind", "busy"), b["title"]))
        for s in data.get("shifts", []):
            if s["weekday"] == WEEKDAYS[d.weekday()]:
                e = to_min(s["end"])
                st = to_min(s["start"])
                events.append((st, e if e > st else 1440, "work", s.get("title", "Work")))
        events.sort()
        wins = free_windows(wake, sleep, [(s, e) for s, e, _, _ in events])
        if i == 0 and now_min is not None:  # nothing before the current time is free
            wins = [[max(w[0], now_min), w[1]] for w in wins if w[1] - max(w[0], now_min) >= MIN_BLOCK]
        days.append({"date": d, "events": events, "wins": wins, "blocks": [], "study": 0.0})

    tasks = []
    for t in data.get("tasks", []):
        dd, dm = parse_due(t["due"])
        tasks.append({**t, "due_d": dd, "due_m": dm, "left": float(t.get("hours", 1)) * 60})
    tasks.sort(key=lambda t: (t["due_d"], t["due_m"]))

    for t in tasks:  # earliest deadline first
        for day in days:
            if t["left"] <= 0 or day["date"] > t["due_d"]:
                break
            for w in day["wins"]:
                limit = w[1] if day["date"] < t["due_d"] else min(w[1], t["due_m"])
                while t["left"] > 0 and limit - w[0] >= MIN_BLOCK and day["study"] < cap:
                    take = min(t["left"], MAX_BLOCK, limit - w[0], cap - day["study"])
                    if take < MIN_BLOCK and take < t["left"]:
                        break
                    day["blocks"].append((w[0], w[0] + take, t))
                    day["study"] += take
                    t["left"] -= take
                    w[0] += take + BREAK
    return today, days, tasks


def render(today, days, tasks):
    out = [f"Week of {today.isoformat()}"]
    crunch = []
    for day in days:
        d = day["date"]
        label = f"{WEEKDAYS[d.weekday()]} {d.month:02d}-{d.day:02d}"
        parts = [f"{k} {fmt(s)}-{fmt(e)}" for s, e, k, _ in day["events"]]
        work_h = sum(e - s for s, e, k, _ in day["events"] if k == "work") / 60
        class_h = sum(e - s for s, e, k, _ in day["events"] if k == "class") / 60
        out.append(f"{label}: " + ("; ".join(parts) if parts else "nothing fixed"))
        for s, e, t in sorted(day["blocks"], key=lambda b: b[0]):
            course = f" ({t['course']})" if t.get("course") else ""
            out.append(f"  study {fmt(int(s))}-{fmt(int(e))} {t['title']}{course}")
        due_today = [t for t in tasks if t["due_d"] == d]
        load = work_h + class_h + day["study"] / 60
        if due_today and (work_h >= 4 or load >= 9):
            crunch.append(f"{label}: {work_h:g}h work + {', '.join(t['title'] for t in due_today)} due")
        elif load >= 11:
            crunch.append(f"{label}: {load:.0f}h committed")
    short = [t for t in tasks if t["left"] > 1]
    if crunch:
        out.append("Crunch days:")
        out += [f"- {c}" for c in crunch]
    if short:
        out.append("Could not fit before the deadline:")
        out += [f"- {t['title']}: {t['left'] / 60:.1f}h short, due {t['due']}" for t in short]
    if not crunch and not short:
        out.append("Everything fits.")
    return "\n".join(out)


def cmd_plan(a):
    if a.sample:
        with open(os.path.join(HERE, "..", "assets", "sample_input.json")) as f:
            data = json.load(f)
    else:
        if not a.input:
            fail(2, "Need --input FILE (or --sample)")
        try:
            with open(a.input) as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            fail(2, f"Cannot read {a.input}: {e}")
        data.setdefault("shifts", load_saved_shifts())
    if not data.get("tasks"):
        fail(3, "No tasks to plan: nothing is due and no lectures to catch up on.")
    now_min = to_min(a.now) if a.now else None
    print(render(*build(data, now_min)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("shifts")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--set")
    g.add_argument("--show", action="store_true")
    g.add_argument("--clear", action="store_true")
    p = sub.add_parser("plan")
    p.add_argument("--input")
    p.add_argument("--now", help="student's local time, HH:MM")
    p.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    cmd_shifts(a) if a.cmd == "shifts" else cmd_plan(a)


if __name__ == "__main__":
    main()