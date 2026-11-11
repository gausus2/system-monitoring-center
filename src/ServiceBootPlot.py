#!/usr/bin/env python3
"""Open systemd's boot SVG plot in the default browser, focused on a service.

This is a local read-only tool. It uses systemd-analyze plot and does not
contact a server or modify systemd configuration.
"""
import json
import subprocess
import sys
import tempfile
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path


def create_plot(service_name):
    result = subprocess.run(
        ["systemd-analyze", "plot"],
        capture_output=True, text=True, check=True,
    )
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    svg = ET.fromstring(result.stdout)
    if svg.tag != "{http://www.w3.org/2000/svg}svg":
        raise ValueError("systemd-analyze did not return an SVG document")
    svg_markup = ET.tostring(svg, encoding="unicode")

    template = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Systemd boot plot</title>
<style>
html,body { margin:0; height:100%; font:14px sans-serif; background:#f5f5f5; }
header { display:flex; gap:12px; align-items:center; padding:9px 14px;
         background:#252b34; color:white; flex-wrap:wrap; }
header strong { margin-right:10px; }
button { cursor:pointer; padding:5px 12px; }
#message { font-size:13px; }
#viewport { width:100vw; height:calc(100vh - 64px); overflow:auto;
            background:white; }
#viewport svg { display:block; max-width:none; }
</style></head>
<body>
<header>
<strong>Systemd boot plot</strong>
<span id="selected"></span>
<button id="minus" type="button">−</button>
<button id="plus" type="button">+</button>
<button id="focus" type="button">Focus selected</button>
<span id="message"></span>
</header>
<div id="viewport">__SVG__</div>
<script>
"use strict";
const selected = __SERVICE__;
const viewport = document.getElementById("viewport");
const svg = viewport.querySelector("svg");
const message = document.getElementById("message");
document.getElementById("selected").textContent = selected;
const width = parseFloat(svg.getAttribute("width")) || svg.getBBox().width;
const height = parseFloat(svg.getAttribute("height")) || svg.getBBox().height;
let zoom = 1.35;
let target = null;
const texts = svg.querySelectorAll("text");
for (const el of texts) {
  const label = (el.textContent || "").trim();
  if (label === selected || label.startsWith(selected + " ") ||
      label.startsWith(selected + "(")) {
    target = el;
    break;
  }
}
function applyZoom() {
  svg.style.width = (width * zoom) + "px";
  svg.style.height = (height * zoom) + "px";
}
function focusSelected() {
  if (!target) {
    message.textContent = "Unit not present in the boot timing plot.";
    return;
  }
  target.style.fill = "#1565c0";
  target.style.fontWeight = "bold";
  const bounds = target.getBoundingClientRect();
  const vp = viewport.getBoundingClientRect();
  // Keep the left-side unit label visible while centering its row vertically.
  viewport.scrollTop += bounds.top - vp.top - vp.height / 2;
  viewport.scrollLeft = 0;
  message.textContent = "Selected service highlighted";
}
function changeZoom(multiplier) {
  zoom = Math.max(0.4, Math.min(5, zoom * multiplier));
  applyZoom();
  requestAnimationFrame(focusSelected);
}
document.getElementById("minus").onclick = () => changeZoom(1/1.25);
document.getElementById("plus").onclick = () => changeZoom(1.25);
document.getElementById("focus").onclick = focusSelected;
applyZoom();
requestAnimationFrame(() => requestAnimationFrame(focusSelected));
</script></body></html>"""
    html = template.replace("__SVG__", svg_markup).replace(
        "__SERVICE__", json.dumps(service_name).replace("<", "\\u003c")
    )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix="smc-boot-plot-",
        suffix=".html", delete=False,
    ) as output:
        output.write(html)
        return Path(output.name)


def main():
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".service"):
        print("Usage: ServiceBootPlot.py NAME.service", file=sys.stderr)
        return 2
    try:
        path = create_plot(sys.argv[1])
        if not webbrowser.open(path.as_uri()):
            print("Could not open default browser. Plot saved at:", path)
            return 1
    except (OSError, ValueError, subprocess.CalledProcessError, ET.ParseError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr or str(error), file=sys.stderr)
        else:
            print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
