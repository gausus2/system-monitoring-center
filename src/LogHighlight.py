"""Generic logfile highlighting inspired by Kate's advanced log mode.

A lightweight heuristic lexer: it does not pretend all text logs use the
same grammar or expose authoritative journal priorities.
"""
import re

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TIMESTAMP = re.compile(
    r"\b(?:\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d+)?"
    r"(?:Z|[+-]\d\d:?\d\d)?|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+\d{1,2}\s+\d\d:\d\d:\d\d)\b", re.I)
ERROR = re.compile(r"\b(?:error|err|fatal|critical|crit|failed|failure|"
                   r"denied|panic|exception|traceback|segfault|emerg|alert)\b", re.I)
WARNING = re.compile(r"\b(?:warn(?:ing)?|deprecated|timeout|timed?\s*out|"
                     r"retry|retries|slow|notice)\b", re.I)
SUCCESS = re.compile(r"\b(?:success(?:ful(?:ly)?)?|passed|completed|"
                     r"accepted|connected|listening|started|finished|ok)\b", re.I)
IP_ADDR = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b")
HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
QUOTED = re.compile(r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""")
PATH = re.compile(r"(?<![A-Za-z0-9])/(?:[A-Za-z0-9_.@+%-]+/?){1,12}")
KEY = re.compile(r"\b[A-Za-z_][A-Za-z0-9_.-]{0,49}(?==)")
RULES = (("timestamp", TIMESTAMP), ("error", ERROR),
         ("warning", WARNING), ("success", SUCCESS), ("ip", IP_ADDR),
         ("hex", HEX), ("path", PATH), ("quoted", QUOTED), ("key", KEY))


def classify_line(line):
    """Severity words are visual hints, not verified priority metadata."""
    for tag, regex in (("error", ERROR), ("warning", WARNING),
                       ("success", SUCCESS)):
        if regex.search(line):
            return tag
    return "normal"


def highlight_spans(line):
    """Return non-overlapping, prioritized (start, end, style) tuples."""
    occupied = bytearray(len(line))
    found = []
    for style, pattern in RULES:
        for match in pattern.finditer(line):
            start, end = match.span()
            if start == end or any(occupied[start:end]):
                continue
            occupied[start:end] = b"\x01" * (end - start)
            found.append((start, end, style))
    return sorted(found)
