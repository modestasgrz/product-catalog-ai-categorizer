"""Turn one or more categorize runs into one local HTML page: every listing next to the category picked, confidence and reason, the review queue, and the score against the answer key."""

import argparse
import csv
import json
from pathlib import Path

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Categorizer results</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--ink:#16181d;--mute:#6b7280;--line:#e5e7eb;--bg:#f7f7f5;--ok:#15803d;--rev:#b45309;--unk:#6d28d9;--err:#b91c1c}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Inter","Segoe UI",sans-serif;color:var(--ink);background:var(--bg)}
header{padding:28px 32px 8px}h1{margin:0;font-size:22px}.sub{color:var(--mute);margin-top:4px}
.tiles{display:flex;flex-wrap:wrap;gap:12px;padding:16px 32px}
.tile{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:130px}
.tile b{display:block;font-size:24px}.tile span{color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.tile.hero{border-color:var(--ok)}.tile.hero b{color:var(--ok);font-size:30px}
.bar{display:flex;gap:8px;padding:4px 32px 12px;flex-wrap:wrap}
.bar button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 14px;cursor:pointer;font:inherit}
.bar button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.bar input{margin-left:auto;border:1px solid var(--line);border-radius:8px;padding:6px 10px;font:inherit;min-width:220px}
table{width:calc(100% - 64px);margin:0 32px 40px;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden}
th{text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mute);padding:10px 12px;border-bottom:1px solid var(--line);background:#fafafa;position:sticky;top:0}
td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr.review td{background:#fffbeb}tr.unknown td{background:#f5f3ff}tr.error td{background:#fef2f2}
.title{font-weight:600}.desc{color:var(--mute);font-size:13px;max-width:460px;overflow-wrap:anywhere}
.arrow{color:var(--mute);font-size:18px}.cat{font-weight:600}.grp{color:var(--mute);font-size:12px}
.pill{display:inline-block;border-radius:999px;padding:2px 9px;font-size:12px;font-weight:600;color:#fff}
.pill.ok{background:var(--ok)}.pill.review{background:var(--rev)}.pill.unknown{background:var(--unk)}.pill.error{background:var(--err)}
.conf{width:70px;height:6px;background:var(--line);border-radius:3px;margin-top:6px}.conf i{display:block;height:6px;border-radius:3px;background:var(--ink)}
.reason{font-size:13px;max-width:340px}.key{font-size:13px;white-space:nowrap}.key.hit{color:var(--ok)}.note{margin-top:4px;font-size:12px;font-weight:600;color:var(--unk)}.key.miss{color:var(--err);font-weight:600}
</style></head><body>
<header><h1 id="h"></h1><div class="sub" id="sub"></div></header>
<div class="tiles" id="tiles"></div>
<div class="bar" id="bar"><input id="q" placeholder="Search listings…"></div>
<table><thead><tr><th>Listing (as the partner sent it)</th><th></th><th>Category picked</th><th>Confidence</th><th>Why</th><th>Answer key</th></tr></thead><tbody id="rows"></tbody></table>
<script type="application/json" id="data">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById("data").textContent);
const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e};
document.getElementById("h").textContent=D.title;
document.getElementById("sub").textContent=D.subtitle;
const tiles=document.getElementById("tiles");
for(const [label,value,hero] of D.tiles){const t=el("div",hero?"tile hero":"tile");t.append(el("b","",value),el("span","",label));tiles.append(t)}
const filters=[["All","all"],["Review queue","queue"],["Answer-key rows","key"],["Wrong vs key","miss"],["Injection tests","inj"]];
let mode="all";const bar=document.getElementById("bar"),q=document.getElementById("q");
for(const [label,m] of filters){const b=el("button",m==="all"?"on":"",label);b.onclick=()=>{mode=m;for(const x of bar.querySelectorAll("button"))x.classList.toggle("on",x===b);draw()};bar.insertBefore(b,q)}
q.oninput=()=>draw();
function draw(){
  const body=document.getElementById("rows");body.replaceChildren();const s=q.value.toLowerCase();
  for(const r of D.rows){
    if(mode==="queue"&&r.status==="ok")continue;
    if(mode==="key"&&r.key===null)continue;
    if(mode==="miss"&&r.key!==false)continue;
    if(mode==="inj"&&!r.note.startsWith("injection"))continue;
    if(s&&!(r.title+" "+r.description+" "+r.location).toLowerCase().includes(s))continue;
    const tr=el("tr",r.status);
    const a=el("td");a.append(el("div","title",r.title||"(empty title)"),el("div","desc",r.description||"(empty description)"),el("div","grp",[r.listing_id,r.location].filter(Boolean).join(" · ")));if(r.note)a.append(el("div","note",r.note));
    const c=el("td");c.append(el("span","pill "+r.status,r.status));c.append(el("div","cat",r.category||"—"),el("div","grp",r.group));
    const f=el("td","",r.confidence);const bar=el("div","conf"),fill=el("i");fill.style.width=(parseFloat(r.confidence)*100||0)+"%";bar.append(fill);f.append(bar);
    const k=el("td",r.key===null?"key":(r.key?"key hit":"key miss"),r.key===null?"":(r.key?"✓ matches":"✗ expected "+r.expected));
    tr.append(a,el("td","arrow","→"),c,f,el("td","reason",r.reason),k);body.append(tr);
  }
}
draw();
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "categorized",
        type=Path,
        nargs="+",
        help="<stem>_categorized.csv files; a later file replaces rows with the same listing_id",
    )
    parser.add_argument("--gold", type=Path, default=None, help="answer key CSV")
    parser.add_argument(
        "--injections",
        type=Path,
        default=None,
        help="key for the prompt-injection rows, scored on its own tile",
    )
    parser.add_argument("--tree", type=Path, default=Path("data/category_tree.json"))
    parser.add_argument("--out", type=Path, required=True, help="HTML file to write")
    args = parser.parse_args()

    tree = json.loads(args.tree.read_text(encoding="utf-8"))
    groups = {c["id"]: c["group"] for c in tree["categories"]}
    names = {c["id"]: c["name"] for c in tree["categories"]} | {"unknown": "unknown"}
    predictions: dict[str, dict[str, str]] = {}
    reports = []
    for path in args.categorized:
        with path.open(encoding="utf-8-sig", newline="") as f:
            predictions |= {p["listing_id"]: p for p in csv.DictReader(f)}
        report_path = path.with_name(
            path.name.replace("_categorized.csv", "_run_report.json")
        )
        if report_path.exists():
            reports.append(json.loads(report_path.read_text(encoding="utf-8")))
    keys: list[dict[str, dict[str, str]]] = []
    for path in (args.gold, args.injections):
        rows_of_key: dict[str, dict[str, str]] = {}
        if path:
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows_of_key = {g["listing_id"]: g for g in csv.DictReader(f)}
        keys.append(rows_of_key)
    gold, injections = keys

    rows = []
    for p in predictions.values():
        picked = "unknown" if p["status"] in ("unknown", "error") else p["category_id"]
        g = gold.get(p["listing_id"]) or injections.get(p["listing_id"])
        accepted = {i.strip() for i in g["accepted_ids"].split("|")} if g else set()
        rows.append(
            {
                "listing_id": p["listing_id"],
                "title": p["title"],
                "description": p["description"],
                "location": p["location"],
                "status": p["status"],
                "category": p["category_name"],
                "group": groups.get(p["category_id"], ""),
                "confidence": p["confidence"],
                "reason": p["reason"].removeprefix("'"),
                "key": None if g is None else picked in accepted,
                "expected": " or ".join(names.get(i, i) for i in sorted(accepted)),
                "note": injections[p["listing_id"]]["note"]
                if p["listing_id"] in injections
                else "",
            }
        )
    counts = {
        s: sum(r["status"] == s for r in rows)
        for s in ("ok", "review", "unknown", "error")
    }
    tiles: list[tuple[str, str, bool]] = []
    for key, label in (
        (gold, "correct vs answer key"),
        (injections, "injection attacks blocked"),
    ):
        scored = [r["key"] for r in rows if r["listing_id"] in key]
        if scored:
            tiles.append((label, f"{sum(scored)}/{len(scored)}", True))
    extra = sum(
        r["listing_id"] in injections and r["listing_id"] not in gold for r in rows
    )
    tiles += [
        (
            f"listings (+{extra} injection tests)" if extra else "listings",
            str(len(rows) - extra),
            False,
        ),
        ("auto-accepted", str(counts["ok"]), False),
        ("to review", str(counts["review"]), False),
        ("nothing fits", str(counts["unknown"]), False),
        ("failed", str(counts["error"]), False),
    ]
    if reports:
        tiles += [
            ("cost", f"${sum(r['estimated_cost_usd'] for r in reports):.2f}", False),
            ("time", f"{sum(r['duration_seconds'] for r in reports):.0f}s", False),
        ]
    first = reports[0] if reports else {}
    data = {
        "title": f"{tree['marketplace']}: listings categorized",
        "subtitle": f"{' + '.join(p.name for p in args.categorized)} · model {first.get('model', '?')} · review below confidence {first.get('threshold', '?')}",
        "tiles": tiles,
        "rows": rows,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    args.out.write_text(PAGE.replace("__DATA__", payload), encoding="utf-8")


if __name__ == "__main__":
    main()
