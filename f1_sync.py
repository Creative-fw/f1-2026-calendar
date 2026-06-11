#!/usr/bin/env python3
"""
F1 2026 -> auto-updating ICS feed.

Source: the open sportstimes/f1 dataset (powers f1calendar.com) --
all sessions in clean UTC, community-updated within hours of FIA
schedule changes. No timezone repairs needed: UTC in, UTC out;
every calendar client converts to local time automatically.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

SOURCE = "https://raw.githubusercontent.com/sportstimes/f1/main/_db/f1/2026.json"

# session key -> (display name, duration minutes, is_race)
SESSIONS = {
    "fp1":              ("Practice 1",        60, False),
    "fp2":              ("Practice 2",        60, False),
    "fp3":              ("Practice 3",        60, False),
    "sprintQualifying": ("Sprint Qualifying", 45, False),
    "sprint":           ("Sprint",            60, True),
    "qualifying":       ("Qualifying",        60, False),
    "gp":               ("Race",             120, True),
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (f1-ics-sync)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def esc(s):
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def main(out_path):
    data = json.loads(fetch(SOURCE))
    races = data["races"]

    events = []
    for r in races:
        gp_name = f"{r['name']} GP"
        loc = r.get("location", "")
        for key, iso in r["sessions"].items():
            if key not in SESSIONS:
                continue  # unknown session type added upstream: skip safely
            name, dur, is_race = SESSIONS[key]
            start = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
            end = start + timedelta(minutes=dur)
            events.append((start, end, gp_name, name, loc, is_race, r["round"]))

    if len(events) < 50:
        print(f"ABORT: only {len(events)} events fetched - refusing to overwrite feed.",
              file=sys.stderr)
        sys.exit(1)

    events.sort(key=lambda e: e[0])
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//LGS//F1 2026 Auto-Sync//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:F1 2026",
             "X-WR-CALDESC:FIA Formula 1 World Championship 2026 - all sessions\\, "
             "auto-synced daily from the open sportstimes/f1 dataset",
             "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
             "X-PUBLISHED-TTL:PT12H"]

    for start, end, gp_name, session, loc, is_race, rnd in events:
        flag = "\U0001F3C1 " if is_race else ""
        uid = re.sub(r"[^a-z0-9]+", "-", f"r{rnd}-{gp_name}-{session}".lower()).strip("-")
        lines += ["BEGIN:VEVENT",
                  f"UID:{uid}@lgs-f1-2026",
                  f"DTSTAMP:{now}",
                  f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}Z",
                  f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}Z",
                  f"SUMMARY:{esc(flag + 'F1 ' + gp_name + ' - ' + session)}",
                  f"LOCATION:{esc(loc)}",
                  "DESCRIPTION:Round " + str(rnd) + ". Times auto-convert to your "
                  "timezone. Auto-synced daily."]
        if is_race:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY",
                      f"DESCRIPTION:{esc(gp_name + ' ' + session)} starts in 1 hour",
                      "TRIGGER:-PT1H", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    with open(out_path, "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")
    print(f"OK: wrote {len(events)} events -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "F1_2026.ics")
