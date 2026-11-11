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
<title>Systemd boot timeline</title>
<style>
:root {font-family:system-ui,-apple-system,sans-serif;color:#dce4f0;background:#111721}
*{box-sizing:border-box}body{margin:0}button,input,select{font:inherit}
header{position:sticky;top:0;z-index:10;background:#1b2432;border-bottom:1px solid #344257;padding:12px 18px}
.top{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
h1{font-size:18px;margin:0 0 3px;font-weight:650}.sub{font-size:12px;color:#9daec6}
.controls{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:12px}
button,select,input{color:#e4ecf8;background:#293649;border:1px solid #43536a;border-radius:6px;padding:7px 10px}
button{cursor:pointer}button:hover{background:#344960}button.active{background:#214c7c;border-color:#4793dd}
input{min-width:230px;flex:1;max-width:390px}
label{display:flex;align-items:center;gap:6px;font-size:13px;color:#c4d0e1}
label input{min-width:auto;flex:none}#status{color:#b5c8e5;font-size:13px}
main{padding:12px 16px}#timeline{border:1px solid #334154;border-radius:10px;overflow:auto;height:calc(100vh - 168px);background:#17202d}
#rows{width:max-content;min-width:100%;position:relative}
.row{display:flex;min-height:26px;border-bottom:1px solid #28384a;align-items:center;font-size:12px}
.row:nth-child(even){background:#1d2938}.row:hover{background:#2b3b51}
.row.selected{background:#163e6d;outline:1px solid #4da5ff;outline-offset:-1px}
.label{position:sticky;left:0;z-index:2;width:360px;min-width:360px;max-width:360px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:5px 12px;border-right:1px solid #3b4d63;background:inherit}
.row.selected .label{font-weight:700;color:#78bfff}.plotbar{position:relative;height:25px;flex:none;background-image:linear-gradient(to right,transparent calc(100% - 1px),#334458 calc(100% - 1px));background-size:100px 100%}
.seg{position:absolute;top:6px;height:12px;border-radius:3px;min-width:2px;opacity:.91;background:#5b98d9}
.seg:hover{outline:2px solid #d7e8ff;z-index:3}
.axis{display:flex;background:#202e3e;border-bottom:1px solid #4a6077;position:sticky;top:0;z-index:4;min-height:34px}
.axis .label{background:#202e3e}
.ticks{position:relative;height:34px;flex:none;background:repeating-linear-gradient(to right,transparent 0,transparent 99px,#3b526b 100px)}
.tick{position:absolute;top:8px;font-size:10px;color:#b9c9dd;white-space:nowrap}
#original{position:absolute;left:-100000px;top:0;visibility:hidden;overflow:auto;height:calc(100vh - 168px);border:1px solid #334154;border-radius:10px;background:white}
#original svg{display:block;max-width:none}
.notice{padding:26px;color:#a9bed7}
@media(max-width:680px){.label{width:200px;min-width:200px;max-width:200px}main{padding:6px}header{padding:10px}#timeline,#original{height:calc(100vh - 200px)}}
</style></head>
<body>
<header>
<div class="top"><div><h1>Systemd boot timeline</h1><div class="sub" id="chosen"></div></div>
<div id="status">Preparing timeline…</div></div>
<div class="controls">
<input id="search" type="search" placeholder="Find a service or unit…" aria-label="Search units">
<label for="unit-type">Unit type</label>
<select id="unit-type" aria-label="Filter by unit type"><option value="service">Services</option><option value="all">All units</option></select>
<button id="focus" type="button">Focus selected</button>
<button id="minus" type="button">− Zoom</button>
<button id="plus" type="button">+ Zoom</button>
<button id="toggle" type="button">Original SVG</button>
</div>
</header>
<main>
<div id="timeline"><div id="rows"></div></div>
<div id="original">__SVG__</div>
</main>
<script>
"use strict";
const selected = __SERVICE__;
document.getElementById("chosen").textContent = "Selected: " + selected;
const original = document.getElementById("original");
const svg = original.querySelector("svg");
const timeline = document.getElementById("timeline");
const rowsNode = document.getElementById("rows");
const search = document.getElementById("search");
const unitType = document.getElementById("unit-type");
const status = document.getElementById("status");
const toggle = document.getElementById("toggle");
let zoom = 1;
let raw = false;
const unitRe = /^(.+?\.(?:service|socket|target|mount|automount|device|timer|path|swap|slice|scope))(?:\s+\(.*\))?$/;
const entries = [];
// The SVG is the sole data source. Read the row label and corresponding
// bar geometry directly; no timings are invented by the viewer.
try {
  const texts = Array.from(svg.querySelectorAll("text"));
  const rects = Array.from(svg.querySelectorAll("rect")).map(el => {
    let b;
    try { b = el.getBBox(); } catch (_) { return null; }
    if (!b || b.width <= 0 || b.height < 2 || b.height > 30) return null;
    return {x:b.x,y:b.y,w:b.width,h:b.height,
            color:el.getAttribute("fill") || getComputedStyle(el).fill};
  }).filter(Boolean);
  for (const el of texts) {
    const label = (el.textContent || "").trim();
    const match = label.match(unitRe);
    if (!match) continue;
    let b;
    try { b = el.getBBox(); } catch (_) { continue; }
    const mid = b.y + b.height/2;
    const nearby = rects.filter(r => Math.abs(r.y + r.h/2 - mid) < 7);
    entries.push({name: match[1], caption:label, bars:nearby});
  }
} catch (e) { status.textContent = "Could not interpret SVG: " + e.message; }
// SVG geometry must be measured while rendered. Hide the raw plot only after reading it.
original.style.display = "none";
original.style.visibility = "visible";
original.style.position = "static";
original.style.left = "auto";
original.style.top = "auto";
// Populate the unit-type filter from the actual SVG labels.
const typeNames = {
  service:"Services", mount:"Mounts", device:"Devices", socket:"Sockets",
  target:"Targets", timer:"Timers", slice:"Slices", path:"Paths",
  automount:"Automounts", scope:"Scopes", swap:"Swap"
};
const typeOrder = ["service","mount","automount","device","socket","target",
                   "timer","path","swap","slice","scope"];
const counts = new Map();
for(const entry of entries) {
  const type=entry.name.split(".").pop();
  counts.set(type,(counts.get(type)||0)+1);
}
unitType.replaceChildren();
const makeOption=(value,name,count)=>{
  const opt=document.createElement("option");
  opt.value=value;
  opt.textContent=name+" ("+count+")";
  unitType.appendChild(opt);
};
makeOption("all","All units",entries.length);
for(const type of typeOrder) {
  if(counts.has(type)) makeOption(type,typeNames[type]||type,counts.get(type));
}
unitType.value=counts.has("service")?"service":"all";
const allBars = entries.flatMap(e => e.bars);
const left = allBars.length ? Math.min(...allBars.map(b=>b.x)) : 0;
const right = allBars.length ? Math.max(...allBars.map(b=>b.x+b.w)) : 1;
const span = Math.max(right-left, 1);
const baseWidth = 1500;
function div(cls,text) { const e=document.createElement("div");e.className=cls;if(text!==undefined)e.textContent=text;return e; }
function render() {
  const term=search.value.trim().toLowerCase();
  const filtered=entries.filter(e=>(unitType.value==="all" || e.name.endsWith("."+unitType.value)) &&
                                   (!term || e.name.toLowerCase().includes(term)));
  const width=baseWidth*zoom;
  rowsNode.replaceChildren();
  const axis=div("axis");
  axis.appendChild(div("label","UNIT / STARTUP"));
  const ticks=div("ticks");
  ticks.style.width=width+"px";
  // Relative SVG horizontal position, intentionally not presented as seconds:
  // exact time conversion depends on the original graph's units and origin.
  for(let i=0;i<=10;i++){
    const tick=div("tick",i*10+"%");
    tick.style.left=(width*i/10)+"px";
    ticks.appendChild(tick);
  }
  axis.appendChild(ticks);rowsNode.appendChild(axis);
  for(const entry of filtered){
    const row=div("row");
    row.dataset.unit=entry.name;
    if(entry.name===selected)row.classList.add("selected");
    const label=div("label",entry.name);
    label.title=entry.caption;
    row.appendChild(label);
    const graph=div("plotbar");
    graph.style.width=width+"px";
    for(const bar of entry.bars){
      const segment=div("seg");
      segment.style.left=((bar.x-left)/span*width)+"px";
      segment.style.width=Math.max(2,bar.w/span*width)+"px";
      // The source SVG supplies the original phase colors.
      if(bar.color && bar.color!=="none" && bar.color!=="transparent")
        segment.style.backgroundColor=bar.color;
      segment.title=entry.caption;
      graph.appendChild(segment);
    }
    row.appendChild(graph);rowsNode.appendChild(row);
    row.onclick=()=>{document.querySelectorAll(".row.selected").forEach(n=>n.classList.remove("selected"));row.classList.add("selected");};
  }
  status.textContent=filtered.length+" units displayed / "+entries.length+" found";
  if(!filtered.length)rowsNode.appendChild(div("notice","No matching units. Try disabling Services only or changing the search."));
}
function focus(){
  if(raw){raw=false;original.style.display="none";timeline.style.display="block";toggle.textContent="Original SVG";}
  const selectedType=selected.split(".").pop();
  if(unitType.value!=="all" && unitType.value!==selectedType)
    unitType.value=counts.has(selectedType)?selectedType:"all";
  if(search.value && !selected.toLowerCase().includes(search.value.toLowerCase()))search.value="";
  render();
  const row=Array.from(rowsNode.querySelectorAll(".row")).find(r=>r.dataset.unit===selected);
  if(!row){status.textContent="Selected unit is not in the boot timing SVG.";return;}
  timeline.scrollTop=Math.max(0,row.offsetTop-timeline.clientHeight/2);
  const bar=entries.find(e=>e.name===selected)?.bars[0];
  timeline.scrollLeft=bar?Math.max(0,(bar.x-left)/span*baseWidth*zoom-300):0;
}
search.addEventListener("input",render);
unitType.addEventListener("change",render);
document.getElementById("focus").onclick=focus;
document.getElementById("minus").onclick=()=>{zoom=Math.max(.5,zoom/1.25);render();focus();};
document.getElementById("plus").onclick=()=>{zoom=Math.min(5,zoom*1.25);render();focus();};
toggle.onclick=()=>{
  raw=!raw;
  original.style.display=raw?"block":"none";
  timeline.style.display=raw?"none":"block";
  toggle.textContent=raw?"Compact timeline":"Original SVG";
};
render();
requestAnimationFrame(()=>requestAnimationFrame(focus));
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
