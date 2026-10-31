"""The data-dictionary ERD (#379): a third format beside the entity and full views, for reading a source's tables
with their data. Tables sit in titled subject areas. Each table's header gives its name, its row count and what one
row is. Each column row gives the name, the type and meaning, and its profile (nulls, distinct values, and every
value's count when there are few, else the most common, from table_profile.py, one fact per line), or says it isn't
measured yet.

Each table is as wide as its own content: each of its three columns is sized to its longest line, within limits.
Rows are grey-banded with vertical column lines and no horizontal borders. Lines run right-angled from the side of
the foreign-key row to the side of the key row it points at, with crow's feet and no labels (dashed: matched, not
a key).

Colours: green header fact table, orange header dimension; name in blue primary key, purple foreign key, red would
hold PHI in a real extract (de-identify), grey not linked; red text an open question or issue.
Each model declares GROUPS, KINDS, PHI and QUESTIONS beside its TABLES.
Run: python3 silver_erd.py (writes these too), then render with drawio_render.js (render.md).
"""
import math
from pathlib import Path

from gold_erd import CARD, INK, MUTED, Diagram

SRC = Path(__file__).resolve().parent.parent / "silver" / "source"
LIMITS = ((90, 170), (80, 220), (110, 210))     # min, max width of: name, type and meaning, profile
CHAR, LINE, PAD, GAP, HEAD_LINE, LANE = 5.6, 13, 28, 120, 14, 7
FACT, DIM, AREA, BAND = "#E3F8DF", "#FFD9A8", "#FDF8C8", "#E6E6E6"
PK, FK, PHI_RED, PLAIN, QUESTION = "#1F5FBF", "#6A3FB5", "#C62828", "#4B5563", "#C62828"
NOT_YET = "not profiled yet"


def _lines(text, width):
    """Lines a wrapped cell needs: about CHAR px per character at 10 px Helvetica, newlines kept."""
    per = max(1, int((width - 8) / CHAR))
    return sum(max(1, math.ceil(len(part) / per)) for part in text.split("\n"))


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")


def _cells(m, table, col, tstats):
    """name, meaning (type, then what it means, one per line), question or None, profile."""
    meaning = f"{col.type};\n{col.description}"
    profile = (tstats or {}).get("columns", {}).get(col.name, NOT_YET)
    return col.name, meaning, m.QUESTIONS.get((table, col.name)), profile


def _fit(texts, lo, hi):
    longest = max((len(line) for t in texts for line in t.split("\n")), default=0)
    return int(min(hi, max(lo, longest * CHAR + 12)))


def table_widths(m, stats):
    """{table: (name, meaning, profile) widths}: each column sized to its own longest line, within LIMITS."""
    out = {}
    for name, t in m.TABLES.items():
        rows = [_cells(m, name, c, stats.get(name)) for c in t.columns]
        out[name] = (_fit([r[0] for r in rows], *LIMITS[0]),
                     _fit([r[1] for r in rows] + [r[2] or "" for r in rows], *LIMITS[1]),
                     _fit([r[3] for r in rows], *LIMITS[2]))
    return out


def _head_text(m, name, stats):
    rows = (stats.get(name) or {}).get("rows")
    return name, (f"{rows:,}" if rows is not None else "rows not measured yet"), m.TABLES[name].description


def _head_height(m, name, stats, width):
    desc = _head_text(m, name, stats)[2]
    return (2 + _lines(desc, width)) * HEAD_LINE + 10


def _row_height(cells, widths):
    name, meaning, question, profile = cells
    lines = max(_lines(name, widths[0]), _lines(meaning + ("\n" + question if question else ""), widths[1]),
                _lines(profile, widths[2]))
    return lines * LINE + 6


def _size(m, name, stats, widths):
    w = sum(widths)
    rows = [_cells(m, name, c, stats.get(name)) for c in m.TABLES[name].columns]
    return w, _head_height(m, name, stats, w) + sum(_row_height(r, widths) for r in rows)


def _key_colour(m, table, col):
    if (table, col.name) in m.PHI:
        return PHI_RED, True
    if "PK" in col.key:
        return PK, True
    if "FK" in col.key:
        return FK, True
    return PLAIN, False


def _draw_table(d, m, name, x, y, stats, widths, anchors):
    tstats = stats.get(name)
    w, h = _size(m, name, stats, widths)
    head_h = _head_height(m, name, stats, w)
    fill = FACT if m.KINDS[name] == "fact" else DIM
    title, count, desc = _head_text(m, name, stats)
    # the outline: rounded, white body, the header filled
    d.v("", x, y, w, h, f"rounded=1;arcSize=2;absoluteArcSize=1;fillColor=#FFFFFF;strokeColor={INK};strokeWidth=1.5;")
    hid = d.v(f"<b>{_esc(title)}</b><br>{_esc(count)}<br>{_esc(desc)}", x + 1, y + 1, w - 2, head_h - 1,
              f"rounded=1;arcSize=2;absoluteArcSize=1;fillColor={fill};strokeColor=none;fontSize=10;fontColor={INK};"
              "align=center;verticalAlign=top;spacingTop=2;")
    anchors[(name, None)] = (hid, x, y, w, head_h)
    d.v("", x, y + head_h, w, 1.5, f"rounded=0;fillColor={INK};strokeColor=none;")
    cy = y + head_h
    for i, col in enumerate(m.TABLES[name].columns):
        cells = _cells(m, name, col, tstats)
        rh = _row_height(cells, widths)
        band = f"fillColor={BAND};" if i % 2 else "fillColor=none;"
        colour, bold = _key_colour(m, name, col)
        cell = f"rounded=0;strokeColor=none;fontSize=10;align=left;verticalAlign=middle;spacingLeft=3;{band}"
        cx = x + 1
        name_text = f"<b>{_esc(col.name)}</b>" if bold else _esc(col.name)
        meaning = _esc(cells[1]) + (f"<br><span style='color:{QUESTION}'>{_esc(cells[2])}</span>" if cells[2] else "")
        for (text, colour_), cw in zip(((name_text, colour), (meaning, INK),
                                        (_esc(cells[3]), MUTED if cells[3] == NOT_YET else INK)), widths):
            d.v(text, cx, cy, cw - (2 if cx + cw >= x + w - 1 else 0), rh, cell + f"fontColor={colour_};")
            cx += cw
        # an invisible box the width of the table, so lines meet the side of this row
        anchors[(name, col.name)] = (d.v("", x, cy, w, rh, "fillColor=none;strokeColor=none;"), x, cy, w, rh)
        cy += rh
    vx = x
    for cw in widths[:-1]:                     # the vertical column lines
        vx += cw
        d.v("", vx, y + head_h, 1.5, h - head_h, f"rounded=0;fillColor={INK};strokeColor=none;")
    return w, h


def _legend(d, x, y):
    items = [(FACT, INK, "green header = FACT table (one row per event)"),
             (DIM, INK, "orange header = DIMENSION table (one row per thing)"),
             ("#FFFFFF", PK, "blue name = primary key"),
             ("#FFFFFF", FK, "purple name = foreign key"),
             ("#FFFFFF", PHI_RED, "red name = would hold PHI in a real extract: de-identify"),
             ("#FFFFFF", PLAIN, "grey name = not linked"),
             ("#FFFFFF", QUESTION, "red text in the meaning = an open question or issue"),
             ("#FFFFFF", INK, "profile: null=n (p%); n_distinct=k; values or top results, from the data (synthetic)"),
             ("#FFFFFF", INK, "lines: crow's foot = many, bar = one; dashed = matched, not a key")]
    h = 34 + 22 * len(items)
    d.v("<b>Legend</b>", x, y, 500, h, f"rounded=1;fillColor=#EEF0FA;strokeColor={INK};fontSize=13;verticalAlign=top;")
    for i, (fill, colour, text) in enumerate(items):
        d.v(text, x + 12, y + 30 + 22 * i, 476, 18, f"rounded=0;fillColor={fill};strokeColor={INK};fontSize=10;fontColor={colour};align=left;spacingLeft=4;")
    return h


def _layout(tables, sizes):
    """Two tables a row: the rows, and the subject area's width and height."""
    rows = [tables[i:i + 2] for i in range(0, len(tables), 2)]
    gw = max(sum(sizes[n][0] for n in row) + PAD * (len(row) + 1) for row in rows)
    gh = 46 + sum(max(sizes[n][1] for n in row) + PAD for row in rows)
    return rows, gw, gh


def group_tops(m, stats, top=0):
    """{subject area: y}: stacked down each column, the column then placed by COLUMN_ALIGN (top, middle or bottom)
    against the tallest column."""
    widths = table_widths(m, stats)
    sizes = {n: _size(m, n, stats, widths[n]) for n in m.TABLES}
    heights = {}
    for title, c, tables in m.GROUPS:
        heights.setdefault(c, []).append((title, _layout(tables, sizes)[2]))
    tallest = max(sum(h for _, h in col) + GAP * (len(col) - 1) for col in heights.values())
    tops = {}
    for c, col in heights.items():
        span = sum(h for _, h in col) + GAP * (len(col) - 1)
        align = getattr(m, "COLUMN_ALIGN", {}).get(c, "top")
        y = top + {"top": 0, "middle": (tallest - span) / 2, "bottom": tallest - span}[align]
        for title, h in col:
            tops[title] = y
            y += h + GAP
    return tops


def build(m, stats=None):
    """m: a model with TABLES, RELATIONSHIPS, GROUPS, KINDS, PHI, QUESTIONS. stats: table_profile.profile() output;
    a table missing from it says its rows aren't measured yet."""
    stats = stats or {}
    d = Diagram()
    legend_h = _legend(d, 10, 10)
    widths = table_widths(m, stats)
    sizes = {n: _size(m, n, stats, widths[n]) for n in m.TABLES}

    def layout(tables):
        return _layout(tables, sizes)

    columns = sorted({c for _, c, _ in m.GROUPS})
    col_w = {c: max(layout(t)[1] for _, gc, t in m.GROUPS if gc == c) for c in columns}
    col_x, x = {}, GAP                      # a margin on the left for column 0's loops
    for c in columns:
        col_x[c] = x
        x += col_w[c] + GAP
    top = 10 + legend_h + GAP               # the corridor above the subject areas runs just above this
    tops = group_tops(m, stats, top)
    anchors, place = {}, {}                 # place: table -> (column, group, row in group)
    for title, c, tables in m.GROUPS:
        rows, _, gh = layout(tables)
        gx, gy = col_x[c], tops[title]
        d.v(f"{_esc(title)}", gx, gy, col_w[c], gh,
            f"rounded=1;arcSize=1;absoluteArcSize=1;fillColor={AREA};strokeColor={INK};fontSize=20;fontColor={INK};verticalAlign=top;spacingTop=6;")
        ty = gy + 46
        for i, row in enumerate(rows):
            tx = gx + PAD
            for n in row:
                w, _ = _draw_table(d, m, n, tx, ty, stats, widths[n], anchors)
                place[n] = (c, title, i)
                tx += w + PAD
            ty += max(sizes[n][1] for n in row) + PAD
    lanes = {}

    def lane(key, base, step):              # the next free lane in a channel, so lines don't overlap
        k = lanes[key] = lanes.get(key, -1) + 1
        return base + step * k

    for r in m.RELATIONSHIPS:
        src = anchors.get((r.child, r.child_cols[0] if r.child_cols else None)) or anchors[(r.child, None)]
        tgt = anchors.get((r.parent, r.parent_cols[0] if r.parent_cols else None)) or anchors[(r.parent, None)]
        sid, sx, sy, sw, sh = src
        tid, tx_, ty_, tw, th = tgt
        s_mid, t_mid = sy + sh / 2, ty_ + th / 2
        sc, sg, srow = place[r.child]
        tc, tg, trow = place[r.parent]
        if sg == tg and srow == trow:                    # side by side in one subject area: straight across
            right = tx_ > sx
            gap_x = (sx + sw + tx_) / 2 if right else (tx_ + tw + sx) / 2
            pts, ex, en = [(gap_x, s_mid), (gap_x, t_mid)], (1 if right else 0), (0 if right else 1)
        elif sc == tc:                                    # same column: loop round its left margin
            ch = lane(("left", sc), col_x[sc] - 14, -LANE)
            pts, ex, en = [(ch, s_mid), (ch, t_mid)], 0, 0
        elif abs(sc - tc) == 1:                           # neighbouring columns: the channel between them
            left_col = min(sc, tc)
            gap_left = col_x[left_col] + col_w[left_col]
            ch = lane(("gap", left_col), gap_left + 14, LANE)
            right = tc > sc
            pts, ex, en = [(ch, s_mid), (ch, t_mid)], (1 if right else 0), (0 if right else 1)
        else:                                             # further apart: up to the corridor, across, down
            right = tc > sc
            s_gap = col_x[sc] + col_w[sc] + 14 if right else col_x[sc] - 14
            t_gap = col_x[tc] - 14 if right else col_x[tc] + col_w[tc] + 14
            c1 = lane(("gap", sc if right else sc - 1), s_gap, LANE if right else -LANE)
            c2 = lane(("gap", tc - 1 if right else tc), t_gap, -LANE if right else LANE)
            cy = lane("corridor", top - 18, -LANE)
            pts = [(c1, s_mid), (c1, cy), (c2, cy), (c2, t_mid)]
            ex, en = (1 if right else 0), (0 if right else 1)
        a, b = r.cardinality[:2], r.cardinality[-2:]
        dash = f"dashed=1;dashPattern=6 4;strokeColor={MUTED};" if r.derived else ""
        style = (f"edgeStyle=none;rounded=0;strokeColor={INK};strokeWidth=1.3;endFill=0;startFill=0;endSize=10;"
                 f"startSize=10;exitX={ex};exitY=0.5;exitPerimeter=0;entryX={en};entryY=0.5;entryPerimeter=0;{dash}"
                 f"startArrow={CARD[b]};endArrow={CARD[a]};")
        d.n += 1
        points = "".join(f'<mxPoint x="{px:.0f}" y="{py:.0f}"/>' for px, py in pts)
        d.cells.append(f'<mxCell id="c{d.n}" value="" style="html=1;{style}" edge="1" parent="1" source="{sid}" '
                       f'target="{tid}"><mxGeometry relative="1" as="geometry"><Array as="points">{points}</Array>'
                       "</mxGeometry></mxCell>")
    return d


def write(prefix, m, stats=None):
    SRC.mkdir(parents=True, exist_ok=True)
    stem = f"{prefix}_dictionary"
    (SRC / f"{stem}.drawio").write_text(build(m, stats).xml(stem))
    return SRC / f"{stem}.drawio"
