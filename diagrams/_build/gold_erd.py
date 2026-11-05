"""gold_model.py -> the gold ERDs, drawn from the declaration so the diagrams are the tables, not a drawing of them.
Writes   ../gold/source/gold_data_model_full.{mmd,drawio}     every column, logical keys marked
         ../gold/source/gold_data_model_entity.{mmd,drawio}   tables and relationships only
         ../gold/data_model.md                                both as Mermaid (GitHub renders them) and every column
The draw.io views are in the owner's data-dictionary format (dictionary_erd.py, #601): subject areas, each table's
grain and every column; the entity view has the same layout, each table cut to its header and key columns. This
module keeps the Mermaid writer, data_model.md, and the draw.io Diagram and line ends dictionary_erd.py builds on,
following jcbowyer/DE_Assessment scripts/shared/diagrams/drawio_erd.py.
Run: python3 gold_erd.py   (then render: render.md)
"""
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
             "The PNGs are in the data-dictionary format: tables in subject areas (green fact, orange dimension, blue "
             "summary), and the entity view has the full view's layout with each table's header and keys only. "
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


if __name__ == "__main__":
    import dictionary_erd  # imported here: it builds on this module's Diagram and line ends
    import gold_model
    SRC.mkdir(parents=True, exist_ok=True)
    for stem, full in (("gold_data_model_entity", False), ("gold_data_model_full", True)):
        (SRC / f"{stem}.mmd").write_text(mermaid(full))
    # the draw.io views in the owner's data-dictionary format (#601): the full view, and the entity view in its layout
    for path in dictionary_erd.write("gold_data_model", gold_model, None, SRC):
        print("wrote", path.relative_to(OUT.parent.parent))
    (OUT / "data_model.md").write_text(markdown())
    print("wrote diagrams/gold/data_model.md")
