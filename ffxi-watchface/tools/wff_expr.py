"""Watch Face Format expressions shared by watchface.xml (XML-escaped, ready to paste).

All times are seconds. UTC_TIMESTAMP may be seconds or milliseconds depending on the
runtime, so T normalises it. The UTC time of day is rebuilt from the exact local
[SECONDS_IN_DAY] minus the zone offset (derived from T and rounded to 15 minutes), so
it stays exact even if large timestamps are evaluated in single precision.

Vana'diel time runs at 25x; one Earth day is exactly 25 Vana'diel days (86400 / 3456),
so the Vana'diel time of day depends only on the UTC time of day. Vana'diel midnight
falls at UTC 15:00 + n * 57.6 min (phase 2160 s). The weekday counts Vana'diel days
since 2002-06-23 15:00 UTC (1024844400), offset 6, mod 8 (Firesday = 0).
These were checked against the standard Vana'diel clock algorithm over 20,000 random
times and time zones, in double and single precision.
"""
T = "([UTC_TIMESTAMP] &gt; 100000000000 ? [UTC_TIMESTAMP] / 1000 : [UTC_TIMESTAMP])"
OFF = f"(round(([SECONDS_IN_DAY] - ({T} % 86400)) / 900) * 900)"
UTC = f"((([SECONDS_IN_DAY] - {OFF}) % 86400 + 86400) % 86400)"   # UTC seconds of day
V = f"((({UTC} - 2160) % 3456 + 3456) % 3456)"                     # Earth s into the Vana'diel day
VH = f"floor({V} / 144)"                                           # Vana'diel hour 0-23
VM = f"floor(({V} % 144) / 2.4)"                                   # Vana'diel minute 0-59
WD = f"((round((({T} - 1024844400) - {V}) / 3456) + 6) % 8)"       # weekday 0-7, Firesday = 0
VANA_ANGLE = f"{V} / 9.6"                                          # 24h dial: one turn per Vana'diel day
JST = f"(({UTC} + 32400) % 86400)"                                 # Japan (UTC+9, no DST)
JST_H = f"floor({JST} / 3600)"
JST_M = f"floor(({JST} % 3600) / 60)"


def reference(t):
    """(hour, minute, weekday) by the usual Vana'diel clock algorithm, for a UTC timestamp."""
    v = (t - 1024844400) * 25 + (898 * 360 + 30) * 86400
    return int(v % 86400 // 3600), int(v % 3600 // 60), int(v // 86400) % 8
