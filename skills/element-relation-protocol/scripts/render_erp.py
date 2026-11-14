#!/usr/bin/env python3
"""要素・関連・プロトコルの図を、JSON から SVG に描く。

Graphviz (dot) で自動配置し、形・線種・色・凡例・フォントを揃える。
座標を手で決める必要がなく、ラベルの重なりも dot が避ける。

使い方:
    python3 render_erp.py input.json output.svg
    python3 render_erp.py input.json output.svg --png output.png   # rsvg-convert があれば確認用 PNG も出す

入力 JSON の形は SKILL.md の「図を描く」節を参照。dot が無ければ終了コード 2 で終わるので、
その場合は手で SVG を描く。
"""
import html
import json
import re
import shutil
import subprocess
import sys

FONT = "Noto Sans CJK JP"
FONT_STACK = "'Noto Sans CJK JP','Hiragino Sans','Yu Gothic','Meiryo',sans-serif"

BLUE = "#1f5fbf"
ORANGE = "#d9730d"
GRAY = "#8a8a8a"
INK = "#222222"
SUB = "#555555"

STRENGTH = {
    "forced": dict(style="solid", color=BLUE),
    "written": dict(style="dotted", color=BLUE),
    "implicit": dict(style="dashed", color=ORANGE),
}
KIND_WIDTH = {"invoke": "2.4", "rw": "1.2", "ref": "1.2"}
KIND_HEAD = {"invoke": "normal", "rw": "vee", "ref": "onormal"}

RESOURCE_SHAPE = {"doc": "note", "data": "cylinder", "folder": "folder", "box": "box"}

CIRCLED = "⓪①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def esc(s):
    return html.escape(str(s or ""), quote=False)


def node_label(e):
    order = e.get("order")
    prefix = (CIRCLED[order] + " ") if isinstance(order, int) and 0 < order < len(CIRCLED) else ""
    name_color = GRAY if e.get("kind") == "external" else INK
    rows = [f'<tr><td><font point-size="13" color="{name_color}"><b>{prefix}{esc(e["name"])}</b></font></td></tr>']
    for d in [x for x in str(e.get("desc", "")).split("\n") if x][:2]:
        rows.append(f'<tr><td><font point-size="10" color="{SUB}">{esc(d)}</font></td></tr>')
    return '<<table border="0" cellborder="0" cellspacing="3" cellpadding="0">' + "".join(rows) + "</table>>"


def edge_label(r):
    parts = []
    strength = r.get("strength", "written")
    lab_color = ORANGE if strength == "implicit" else BLUE
    for line in [x for x in str(r.get("label", "")).split("\n") if x]:
        parts.append(f'<tr><td><font point-size="10" color="{lab_color}">{esc(line)}</font></td></tr>')
    for line in [x for x in str(r.get("note", "")).split("\n") if x]:
        parts.append(f'<tr><td><font point-size="9.5" color="{ORANGE}">{esc(line)}</font></td></tr>')
    return ('<<table border="0" cellborder="0" cellspacing="2" cellpadding="0" bgcolor="white">' + "".join(parts) + "</table>>") if parts else '""'


def node_attrs(e):
    kind = e.get("kind", "actor")
    a = dict(label=node_label(e), fontname=FONT, margin="0.2,0.12", penwidth="1.6", color=INK,
             fillcolor="white", style="filled")
    if kind == "actor":
        a.update(shape="box", style="rounded,filled")
    elif kind == "resource":
        a.update(shape=RESOURCE_SHAPE.get(e.get("shape", "doc"), "note"))
    else:  # external
        a.update(shape="box", style="rounded,dashed,filled", color=GRAY, fillcolor="#f2f2f2")
    if e.get("zoom"):
        a["peripheries"] = "2"
    return a


def attrs_str(d):
    out = []
    for k, v in d.items():
        if isinstance(v, str) and v.startswith("<") and v.endswith(">"):
            out.append(f"{k}={v}")
        else:
            out.append(f'{k}="{v}"')
    return ", ".join(out)


def build_dot(spec):
    rankdir = spec.get("rankdir", "TB")
    lines = [
        "digraph ERP {",
        f'  graph [rankdir="{rankdir}", fontname="{FONT}", nodesep="0.6", ranksep="0.75", pad="0.3", '
        f'splines="true", newrank="true", compound="true"];',
        f'  node [fontname="{FONT}"];',
        f'  edge [fontname="{FONT}", arrowsize="0.8"];',
    ]
    groups = {g["id"]: g for g in spec.get("groups", [])}
    members = {gid: [] for gid in groups}
    loose = []
    for e in spec["elements"]:
        (members[e["group"]] if e.get("group") in groups else loose).append(e)
    for gid, g in groups.items():
        lines.append(f'  subgraph "cluster_{gid}" {{')
        lines.append(f'    label=<<font point-size="11" color="{SUB}">{esc(g.get("label", ""))}</font>>; '
                     f'labeljust="l"; style="rounded"; color="#bbbbbb"; bgcolor="#fafafa";')
        for e in members[gid]:
            lines.append(f'    "{e["id"]}" [{attrs_str(node_attrs(e))}];')
        lines.append("  }")
    for e in loose:
        lines.append(f'  "{e["id"]}" [{attrs_str(node_attrs(e))}];')
    ids = {e["id"] for e in spec["elements"]}
    for r in spec.get("relations", []):
        if r["from"] not in ids or r["to"] not in ids:
            sys.exit(f"relation の from/to が elements にありません: {r}")
        st = STRENGTH.get(r.get("strength", "written"), STRENGTH["written"])
        kind = r.get("kind", "rw")
        a = dict(style=st["style"], color=st["color"], penwidth=KIND_WIDTH.get(kind, "1.2"),
                 arrowhead=KIND_HEAD.get(kind, "vee"), label=edge_label(r))
        if r.get("constraint") is False:
            a["constraint"] = "false"
        lines.append(f'  "{r["from"]}" -> "{r["to"]}" [{attrs_str(a)}];')
    for rank in spec.get("same_rank", []):
        lines.append("  { rank=same; " + " ".join(f'"{i}";' for i in rank) + " }")
    lines.append("}")
    return "\n".join(lines)


def legend_svg(width, used):
    """凡例。図で実際に使った種類だけを出す。"""
    rows_left, rows_mid, rows_right = [], [], []
    y0 = 34

    def shape_row(kind, label):
        return (kind, label)

    if "actor" in used["kinds"]:
        rows_left.append(shape_row("actor", "実行主体（角丸の箱）"))
    if "resource" in used["kinds"]:
        rows_left.append(shape_row("resource", "リソース（書類・円柱・フォルダ形）"))
    if "external" in used["kinds"]:
        rows_left.append(shape_row("external", "範囲の外（灰色の破線枠）"))
    if used["zoom"]:
        rows_left.append(shape_row("zoom", "二重枠＝ズームイン候補"))
    if used["order"]:
        rows_left.append(shape_row("order", "①②…＝読む順番"))
    for s, text in (("forced", "強制：仕組みで守られる"), ("written", "記述：書いてあるだけ（守らなくても止まらない）"),
                    ("implicit", "暗黙：どこにも書かれていない")):
        if s in used["strengths"]:
            rows_mid.append(s)
    for k, text in (("invoke", "太線：起動・呼び出し"), ("rw", "細線：読む・書く"), ("ref", "白抜き矢じり：参照・前提")):
        if k in used["kinds_rel"]:
            rows_right.append((k, text))
    if used["note"]:
        rows_mid.append("note")

    n = max(len(rows_left), len(rows_mid), len(rows_right), 1)
    h = y0 + n * 26 + 14
    col = width / 3
    g = [f'<g font-family="{FONT_STACK}">',
         f'<rect x="10" y="4" width="{width - 20}" height="{h - 8}" rx="8" fill="#fbfbfb" stroke="#cccccc"/>',
         f'<text x="26" y="26" font-size="13" font-weight="bold" fill="{INK}">凡例</text>']
    for i, (kind, label) in enumerate(rows_left):
        y = y0 + i * 26
        x = 26
        if kind == "actor":
            g.append(f'<rect x="{x}" y="{y}" width="34" height="18" rx="5" fill="white" stroke="{INK}" stroke-width="1.4"/>')
        elif kind == "resource":
            g.append(f'<path d="M{x},{y} h26 l8,6 v12 h-34 z" fill="white" stroke="{INK}" stroke-width="1.4"/>')
        elif kind == "external":
            g.append(f'<rect x="{x}" y="{y}" width="34" height="18" rx="5" fill="#f2f2f2" stroke="{GRAY}" stroke-dasharray="4 3"/>')
        elif kind == "zoom":
            g.append(f'<rect x="{x}" y="{y}" width="34" height="18" rx="5" fill="white" stroke="{INK}"/>'
                     f'<rect x="{x + 3}" y="{y + 3}" width="28" height="12" rx="3" fill="none" stroke="{INK}"/>')
        elif kind == "order":
            g.append(f'<text x="{x + 4}" y="{y + 14}" font-size="13" fill="{INK}">①</text>')
        g.append(f'<text x="{x + 44}" y="{y + 14}" font-size="12" fill="{INK}">{esc(label)}</text>')
    for i, s in enumerate(rows_mid):
        y = y0 + i * 26 + 9
        x = col + 10
        if s == "note":
            g.append(f'<text x="{x}" y="{y + 5}" font-size="12" fill="{ORANGE}">橙の文字</text>'
                     f'<text x="{x + 66}" y="{y + 5}" font-size="12" fill="{INK}">＝矢印に付いた暗黙の前提</text>')
            continue
        st = STRENGTH[s]
        dash = {"solid": "", "dotted": ' stroke-dasharray="2 3"', "dashed": ' stroke-dasharray="7 4"'}[st["style"]]
        text = {"forced": "強制：仕組みで守られる", "written": "記述：書いてあるだけ", "implicit": "暗黙：どこにも書かれていない"}[s]
        g.append(f'<line x1="{x}" y1="{y}" x2="{x + 40}" y2="{y}" stroke="{st["color"]}" stroke-width="2"{dash}/>'
                 f'<path d="M{x + 40},{y - 4} l8,4 l-8,4 z" fill="{st["color"]}"/>'
                 f'<text x="{x + 56}" y="{y + 5}" font-size="12" fill="{INK}">{text}</text>')
    for i, (k, text) in enumerate(rows_right):
        y = y0 + i * 26 + 9
        x = 2 * col + 10
        w = KIND_WIDTH[k]
        head = {"invoke": f'<path d="M{x + 40},{y - 5} l10,5 l-10,5 z" fill="{BLUE}"/>',
                "rw": f'<path d="M{x + 40},{y - 5} l9,5 l-9,5" fill="none" stroke="{BLUE}" stroke-width="1.4"/>',
                "ref": f'<path d="M{x + 40},{y - 5} l9,5 l-9,5 z" fill="white" stroke="{BLUE}" stroke-width="1.2"/>'}[k]
        g.append(f'<line x1="{x}" y1="{y}" x2="{x + 40}" y2="{y}" stroke="{BLUE}" stroke-width="{w}"/>' + head +
                 f'<text x="{x + 58}" y="{y + 5}" font-size="12" fill="{INK}">{esc(text)}</text>')
    g.append("</g>")
    return "\n".join(g), h


def main():
    args = sys.argv[1:]
    png = None
    if "--png" in args:
        i = args.index("--png")
        png = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    src, dst = args
    if not shutil.which("dot"):
        print("dot (Graphviz) が見つかりません。手で SVG を描いてください。", file=sys.stderr)
        sys.exit(2)
    spec = json.load(open(src, encoding="utf-8"))
    dot_src = build_dot(spec)
    res = subprocess.run(["dot", "-Tsvg"], input=dot_src.encode("utf-8"), capture_output=True)
    if res.returncode != 0:
        sys.stderr.write(res.stderr.decode("utf-8", "replace"))
        sys.stderr.write("\n--- 生成した dot ---\n" + dot_src + "\n")
        sys.exit(1)
    graph = res.stdout.decode("utf-8")
    graph = graph[graph.index("<svg"):]
    m = re.search(r'<svg width="([\d.]+)pt" height="([\d.]+)pt"', graph)
    gw, gh = float(m.group(1)), float(m.group(2))
    graph = re.sub(r'font-family="[^"]*"', f'font-family="{FONT_STACK}"', graph)
    graph = re.sub(r'^<svg width="[\d.]+pt" height="[\d.]+pt"', f'<svg width="{gw}" height="{gh}"', graph)

    used = {
        "kinds": {e.get("kind", "actor") for e in spec["elements"]},
        "zoom": any(e.get("zoom") for e in spec["elements"]),
        "order": any(isinstance(e.get("order"), int) for e in spec["elements"]),
        "strengths": {r.get("strength", "written") for r in spec.get("relations", [])},
        "kinds_rel": {r.get("kind", "rw") for r in spec.get("relations", [])},
        "note": any(r.get("note") for r in spec.get("relations", [])),
    }
    width = max(gw, 900)
    title_h = 0
    head = []
    if spec.get("title"):
        title_h = 40 + (22 if spec.get("subtitle") else 0)
        head.append(f'<text x="16" y="30" font-size="20" font-weight="bold" fill="{INK}" font-family="{FONT_STACK}">{esc(spec["title"])}</text>')
        if spec.get("subtitle"):
            head.append(f'<text x="16" y="54" font-size="12" fill="{SUB}" font-family="{FONT_STACK}">{esc(spec["subtitle"])}</text>')
    leg, lh = legend_svg(width, used)
    total_h = title_h + gh + 10 + lh
    gx = (width - gw) / 2
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{total_h:.0f}" viewBox="0 0 {width:.0f} {total_h:.0f}">',
           f'<rect width="100%" height="100%" fill="white"/>',
           *head,
           f'<g transform="translate({gx:.1f},{title_h})">',
           graph.replace('<svg ', '<svg x="0" y="0" ', 1),
           "</g>",
           f'<g transform="translate(0,{title_h + gh + 10:.1f})">', leg, "</g>",
           "</svg>"]
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    print(f"wrote {dst}")
    if png:
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-z", "2", "-b", "white", dst, "-o", png], check=True)
            print(f"wrote {png}")
        else:
            print("rsvg-convert が無いので PNG は省略", file=sys.stderr)


if __name__ == "__main__":
    main()
