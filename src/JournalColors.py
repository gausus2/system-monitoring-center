"""Presentation-only syntax colors for system and kernel journals.

No journalctl query is changed. The token spans follow the same generic
Kate-inspired rules as the Other logs text-file viewer.
"""
from . import LogHighlight

STYLES = {
    "normal": "#cccccc",
    "error": "#e05a60",
    "warning": "#dca640",
    "success": "#65c76b",
    "timestamp": "#91b9e9",
    "ip": "#c6a0e9",
    "hex": "#c6a0e9",
    "path": "#7cbacb",
    "quoted": "#b1c68c",
    "key": "#74c4bd",
}


def advanced_line(when, priority, sender, message):
    """Return (display text, base style, highlighted spans).

    Preserve the same columns and newline replacement as Current colors.
    Span offsets index Unicode characters in the returned display text.
    """
    names = ("EMERG", "ALERT", "CRIT", "ERROR", "WARN",
             "NOTICE", "INFO", "DEBUG")
    priority = max(0, min(7, priority))
    line = (when + "  %-6s " % names[priority] + "%-26s " % sender
            + message.replace("\r", "").replace("\n", " ⏎ ") + "\n")
    base = LogHighlight.classify_line(line)
    return line, base, LogHighlight.highlight_spans(line)
