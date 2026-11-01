"""gold_model.py -> the gold ERDs, drawn from the declaration so the diagrams are the tables, not a drawing of them.
Writes   ../gold/source/gold_data_model_full.{mmd,drawio}     every column, logical keys marked
         ../gold/source/gold_data_model_entity.{mmd,drawio}   tables and relationships only
         ../gold/data_model.md                                both as Mermaid (GitHub renders them) and every column
Table style and the crossing-minimising grid layout follow jcbowyer/DE_Assessment scripts/shared/diagrams/drawio_erd.py.
Run: python3 gold_erd.py   (then render: render.md)
"""
import random
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape

from gold_model import AREAS, RELATIONSHIPS, TABLES

# the model a diagram draws: gold by default; silver_erd.py passes others (spec 029)
GOLD = SimpleNamespace(TABLES=TABLES, RELATIONSHIPS=RELATIONSHIPS, AREAS=AREAS)

OUT = Path(__file__).resolve().parent.parent / "gold"
SRC = OUT / "source"
INK, MUTED = "#1B3139", "#5B6B73"
FONT = "fontFamily=Helvetica;html=1;whiteSpace=wrap;"
CARD = {"||": "ERmandOne", "|o": "ERzeroToOne", "o|": "ERzeroToOne", "o{": "ERzeroToMany", "}o": "ERzeroToMany",
        "|{": "ERoneToMany", "}|": "ERoneToMany"}
HEAD, RH = 46, 22
WIDTHS = (56, 190, 80, 380)        # keys, column, type, description
SCHEMA = "health_transformation_lab.gold_perio_bench"


# ---------- Mermaid ----------
def mermaid(full: bool, m=GOLD) -> str:
    out = ["erDiagram"]
    for r in m.RELATIONSHIPS:
        out.append(f'    {r.parent} {r.cardinality} {r.child} : "{r.label}"')
    for name, t in m.TABLES.items():
        if full:
            out.append(f"    {name} {{")
            for c in t.columns:
                key = f" {c.key.replace(',', ', ')}" if c.key else ""
                out.append(f'        {c.type} {c.name}{key} "{c.description.replace(chr(34), chr(39))}"')
            out.append("    }")
        else:
            out.append(f"    {name}")
    return "\n".join(out) + "\n"


def markdown() -> str:
    lines = [f"# Gold data model: `{SCHEMA}`", "",
             ("Generated from [`_build/gold_model.py`](../_build/gold_model.py) by `_build/gold_erd.py`; "
             "`python/tests/test_gold_model.py` checks the columns against the CSV twins and `results_store`. "
             "Names follow AGENTS.md, SQL and data names (spec 018). Keys are logical: Delta enforces none. Solid lines are keys; dashed lines are summaries or matches, not keys. "
             "PNGs are in this folder; the draw.io and Mermaid sources are in `source/`. "
             "Who writes each table and why: [docs/gold_tables.md](../../docs/gold_tables.md). Synthetic data only."), "",
             "![entity](gold_data_model_entity.png)", "",
             "## Tables and relationships (entity)", "", "```mermaid", mermaid(False).rstrip(), "```", "",
             "## Every column (full)", "", "![full](gold_data_model_full.png)", "",
             "```mermaid", mermaid(True).rstrip(), "```", ""]
    for name, t in TABLES.items():
        lines += [f"### `{name}`", "", f"{t.description}. Written by: {t.writer}.", "",
                  "| Key | Column | Type | Description |", "|---|---|---|---|"]
        lines += [f"| {c.key} | `{c.name}` | {c.type} | {c.description} |" for c in t.columns]
        lines.append("")
    return "\n".join(lines)


# ---------- draw.io ----------
class Diagram:
    def __init__(self):
        self.cells, self.n = [], 0

    def v(self, value, x, y, w, h, style, parent="1", extra=""):
        self.n += 1
        cid = f"c{self.n}"
        self.cells.append(f'<mxCell id="{cid}" value="{escape(value, {chr(34): "&quot;"})}" style="{FONT}{style}" vertex="1" parent="{parent}">'
                          f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry">{extra}</mxGeometry></mxCell>')
        return cid

    def e(self, src, tgt, style, value=""):
        # labels 35% of the way from the source, so labels on crossing lines don't land on the same spot
        self.n += 1
        self.cells.append(f'<mxCell id="c{self.n}" value="{escape(value)}" style="{FONT}{style}" edge="1" parent="1" source="{src}" target="{tgt}">'
                          '<mxGeometry x="-0.3" relative="1" as="geometry"/></mxCell>')

    def xml(self, name):
        return (f'<mxfile host="drawio"><diagram name="{name}" id="{name}"><mxGraphModel grid="0" page="0" background="#FFFFFF"><root>'
                '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(self.cells) + "</root></mxGraphModel></diagram></mxfile>")


HDR = (f"shape=table;startSize={HEAD};container=1;collapsible=0;childLayout=tableLayout;fixedRows=1;rowLines=0;fontStyle=1;align=center;"
       f"resizeLast=1;fontSize=14;strokeColor={INK};swimlaneFillColor=#FFFFFF;fontColor={INK};")
ROW = ("shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;collapsible=0;dropTarget=0;points=[[0,0.5],[1,0.5]];"
       "portConstraint=eastwest;top=0;left=0;right=0;bottom=0;")
CELL = "shape=partialRectangle;connectable=0;fillColor=none;top=0;left=0;bottom=0;right=0;overflow=hidden;fontSize=11;align=left;spacingLeft=5;"


def full_size(name, m=GOLD):
    return sum(WIDTHS), HEAD + RH * len(m.TABLES[name].columns)


# layout: grid positions with the fewest crossings. score = 100 per pair of crossing lines + 150 per line over
# another table + line length + spread
def _cross(p1, p2, p3, p4):
    def o(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return (v > 1e-9) - (v < -1e-9)
    return o(p1, p2, p3) * o(p1, p2, p4) < 0 and o(p3, p4, p1) * o(p3, p4, p2) < 0


def _hits_box(a, b, box, pad=6):
    x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    for k in range(1, 40):
        t = k / 40
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        if x0 < x < x1 and y0 < y < y1:
            return True
    return False


def _pixels(pos, sizes, gapx=130, gapy=110):
    cols, rows = sorted({c for c, _ in pos.values()}), sorted({r for _, r in pos.values()})
    colw = {c: max(sizes[n][0] for n, p in pos.items() if p[0] == c) for c in cols}
    rowh = {r: max(sizes[n][1] for n, p in pos.items() if p[1] == r) for r in rows}
    cx, x = {}, 10
    for c in cols:
        cx[c] = x; x += colw[c] + gapx
    ry, y = {}, 10
    for r in rows:
        ry[r] = y; y += rowh[r] + gapy
    return {n: (cx[c], ry[r], cx[c] + sizes[n][0], ry[r] + sizes[n][1]) for n, (c, r) in pos.items()}, x, y


def score(pos, edges, sizes):
    boxes, W, H = _pixels(pos, sizes)
    ctr = {n: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for n, b in boxes.items()}
    segs = [(a, b, ctr[a], ctr[b]) for a, b in edges]
    sc = 0.0
    for i, (a1, b1, p1, q1) in enumerate(segs):
        sc += 0.02 * ((p1[0] - q1[0]) ** 2 + (p1[1] - q1[1]) ** 2) ** 0.5
        sc += sum(150 for n, box in boxes.items() if n not in (a1, b1) and _hits_box(p1, q1, box))
        for a2, b2, p2, q2 in segs[i + 1:]:
            if not {a1, b1} & {a2, b2} and _cross(p1, q1, p2, q2):
                sc += 100
    return sc + 0.00002 * W * H


def arrange(names, edges, sizes, seed=7):
    rnd = random.Random(seed)
    cols, rows = max(3, (len(names) + 2) // 2), 4
    cells = [(c, r) for r in range(rows) for c in range(cols)]
    best, best_sc = None, float("inf")
    for _ in range(16):
        pos = dict(zip(names, rnd.sample(cells, len(names))))
        cur = score(pos, edges, sizes)
        for _ in range(1200):
            n, target = rnd.choice(names), rnd.choice(cells)
            other = next((m for m, p in pos.items() if p == target), None)
            old = pos[n]
            pos[n] = target
            if other:
                pos[other] = old
            new = score(pos, edges, sizes)
            if new <= cur:
                cur = new
            else:
                pos[n] = old
                if other:
                    pos[other] = target
        if cur < best_sc:
            best, best_sc = dict(pos), cur
    used_c, used_r = sorted({p[0] for p in best.values()}), sorted({p[1] for p in best.values()})
    grid = [[None] * len(used_c) for _ in used_r]
    for n, (c, r) in best.items():
        grid[used_r.index(r)][used_c.index(c)] = n
    return grid


def build(grid, full, m=GOLD):
    d = Diagram()
    size = {n: full_size(n, m) if full else (220, 56) for n in m.TABLES}
    ncol = len(grid[0])
    colw = [max((size[r[c]][0] for r in grid if r[c]), default=220) for c in range(ncol)]
    gapx, gapy = (130, 110) if full else (120, 100)
    ids, y = {}, 10
    for row in grid:
        x, rowh = 10, 0
        for c, n in enumerate(row):
            if n:
                t = m.TABLES[n]
                fill = m.AREAS[t.area][0]
                w, h = size[n]
                if full:
                    label = n + f"<br><span style='font-weight:normal;font-size:11px;color:{MUTED}'>{t.description}</span>"
                    tid = d.v(label, x, y, w, h, HDR + f"fillColor={fill};")
                    for i, col in enumerate(t.columns):
                        r = d.v("", 0, HEAD + i * RH, w, RH, ROW + ("fillColor=#F6F8F9;" if i % 2 else "fillColor=none;"), parent=tid)
                        cx = 0
                        for j, (cw, val) in enumerate(zip(WIDTHS, (col.key, col.name, col.type, col.description))):
                            st = CELL + ("fontStyle=1;" if j == 0 else f"fontColor={MUTED};fontStyle=2;fontSize=10;" if j == 3 else f"fontColor={INK};")
                            d.v(val, cx, 0, cw, RH, st, parent=r, extra=f'<mxRectangle width="{cw}" height="{RH}" as="alternateBounds"/>')
                            cx += cw
                    ids[n] = tid
                else:
                    ids[n] = d.v(f"<b>{n}</b><br><span style='font-size:10px;color:{MUTED}'>{t.description}</span>", x, y, w, h,
                                 f"rounded=1;arcSize=10;strokeColor={INK};strokeWidth=1.5;fontColor={INK};fontSize=13;fillColor={fill};")
                rowh = max(rowh, h)
            x += colw[c] + gapx
        y += rowh + gapy
    er = f"edgeStyle=none;strokeColor={INK};strokeWidth=1.3;endFill=0;startFill=0;fontSize=10;fontColor={MUTED};labelBackgroundColor=#FFFFFF;"
    for r in m.RELATIONSHIPS:
        a, b = r.cardinality[:2], r.cardinality[-2:]
        dash = f"dashed=1;dashPattern=6 4;strokeColor={MUTED};" if r.derived else ""
        d.e(ids[r.parent], ids[r.child], er + dash + f"startArrow={CARD[a]};endArrow={CARD[b]};", r.label)
    lx = 10
    for fill, text in m.AREAS.values():
        d.v(text, lx, y - gapy + 30, 270, 22, f"rounded=1;fillColor={fill};strokeColor={INK};fontSize=11;fontColor={INK};")
        lx += 280
    d.v("solid line: key · dashed line: summarised from or matched on, not a key · keys are logical (Delta enforces none)",
        lx, y - gapy + 30, 620, 22, f"text;align=left;fontSize=11;fontColor={MUTED};")
    return d


if __name__ == "__main__":
    SRC.mkdir(parents=True, exist_ok=True)
    names = list(TABLES)
    edges = [(r.parent, r.child) for r in RELATIONSHIPS if r.parent != r.child]
    grid = arrange(names, edges, {n: full_size(n) for n in names})   # laid out with the full sizes; the entity view reuses it
    for stem, full in (("gold_data_model_entity", False), ("gold_data_model_full", True)):
        (SRC / f"{stem}.mmd").write_text(mermaid(full))
        (SRC / f"{stem}.drawio").write_text(build(grid, full).xml(stem))
        print("wrote", f"diagrams/gold/source/{stem}.drawio, .mmd")
    (OUT / "data_model.md").write_text(markdown())
    print("wrote diagrams/gold/data_model.md")
