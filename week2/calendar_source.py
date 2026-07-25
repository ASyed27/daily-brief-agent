"""Calendar source for the Daily Brief — reads the recipient's secret iCal feed and
returns today's events plus the next few days, with overlap/conflict detection.

Uses `recurring_ical_events` so repeating events (weekly meetings, etc.) are expanded
correctly within the window. Times are normalized to US Eastern.
"""
import requests
import recurring_ical_events
from icalendar import Calendar
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    ET = None


def _t12(dt):
    h = dt.hour % 12 or 12
    return f"{h}:{dt.strftime('%M %p')}"


def _local(dt):
    if isinstance(dt, datetime) and dt.tzinfo is not None and ET is not None:
        return dt.astimezone(ET)
    return dt


def fetch_events(ical_url, days=7, now=None):
    """Return {"today":[...], "upcoming":[...]} for today .. today+days.

    today items:    {all_day, time, title, conflict}
    upcoming items: {date, day, time, title, all_day}
    """
    now = now or datetime.now()
    today = now.date()
    horizon = today + timedelta(days=days)

    resp = requests.get(ical_url, timeout=30)
    resp.raise_for_status()
    cal = Calendar.from_ical(resp.content)
    occurrences = recurring_ical_events.of(cal).between(today, horizon + timedelta(days=1))

    allday_today, timed_today, upcoming = [], [], []
    for ev in occurrences:
        start = ev.get("DTSTART").dt
        end_c = ev.get("DTEND")
        end = end_c.dt if end_c is not None else None
        title = str(ev.get("SUMMARY", "")).strip() or "(no title)"
        all_day = not isinstance(start, datetime)

        s = _local(start)
        e = _local(end) if end is not None else None
        s_date = s.date() if isinstance(s, datetime) else s
        if s_date < today or s_date > horizon:
            continue

        if s_date == today:
            if all_day:
                allday_today.append({"all_day": True, "time": "All day", "title": title})
            else:
                tr = _t12(s) + (" – " + _t12(e) if isinstance(e, datetime) else "")
                timed_today.append({"start": s, "end": e, "time": tr, "title": title})
        else:
            day_label = s_date.strftime("%a ") + s_date.strftime("%b ") + str(s_date.day)
            time_label = "All day" if all_day else _t12(s)
            upcoming.append({"date": s_date.isoformat(), "day": day_label,
                             "time": time_label, "title": title, "all_day": all_day})

    timed_today.sort(key=lambda x: x["start"])
    for i, ev in enumerate(timed_today):
        ev["conflict"] = any(
            i != j and isinstance(ev["end"], datetime) and isinstance(o["end"], datetime)
            and ev["start"] < o["end"] and o["start"] < ev["end"]
            for j, o in enumerate(timed_today)
        )

    today_list = allday_today + [
        {"all_day": False, "time": ev["time"], "title": ev["title"], "conflict": ev["conflict"]}
        for ev in timed_today
    ]
    upcoming.sort(key=lambda x: (x["date"], x["time"]))
    return {"today": today_list, "upcoming": upcoming}


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    data = fetch_events(os.getenv("RECIPIENT_ICAL_URL"))
    print(f"TODAY ({len(data['today'])}):")
    for e in data["today"]:
        flag = "  [conflict]" if e.get("conflict") else ""
        print(f"  {e['time']:22s} {e['title']}{flag}")
    print(f"\nUPCOMING 7 DAYS ({len(data['upcoming'])}):")
    for e in data["upcoming"]:
        print(f"  {e['day']:12s} {e['time']:10s} {e['title']}")
