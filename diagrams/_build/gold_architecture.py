"""../gold/source/gold_logical_architecture.drawio and gold_physical_architecture.drawio: how results reach
health_transformation_lab.gold_perio_bench and who reads them. The frame (lanes, Data Intelligence Platform, groups, key,
storage) follows jcbowyer/DE_Assessment scripts/shared/diagrams/drawio_architecture.py, which copies the Databricks
reference architecture; each pill carries its Databricks product icon (dbx_icons/, see render.md).
Run: python3 gold_architecture.py   (then node drawio_render.js)   Synthetic data only.
"""
import base64
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "gold" / "source"
INK, MUTED, GREEN, GREEN_T, LINE = "#1B3139", "#5B6B73", "#00A972", "#0E7A57", "#44525A"
FONT = "fontFamily=Helvetica;html=1;whiteSpace=wrap;"


class Diagram:
    def __init__(self, name):
        self.name, self.cells, self.n = name, [], 0

    def v(self, value, x, y, w, h, style, parent="1"):
        self.n += 1
        cid = f"c{self.n}"
        self.cells.append(f'<mxCell id="{cid}" value="{escape(value, {chr(34): "&quot;"})}" style="{FONT}{style}" '
                          f'vertex="1" parent="{parent}"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return cid

    def e(self, src, tgt, style="", value="", points=()):
        self.n += 1
        pts = ('<Array as="points">' + "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in points) + "</Array>") if points else ""
        self.cells.append(f'<mxCell id="c{self.n}" value="{escape(value)}" style="{FONT}{style}" edge="1" parent="1" source="{src}" '
                          f'target="{tgt}"><mxGeometry relative="1" as="geometry">{pts}</mxGeometry></mxCell>')

    def write(self, stem):
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{stem}.drawio").write_text(
            f'<mxfile host="drawio"><diagram name="{self.name}" id="{stem}"><mxGraphModel grid="0" page="0" background="#FFFFFF"><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(self.cells) + "</root></mxGraphModel></diagram></mxfile>")
        print("wrote", f"diagrams/gold/source/{stem}.drawio")


LANE = "rounded=0;fillColor=#D9D9D9;strokeColor=none;fontSize=18;fontStyle=1;fontColor=#333333;"
PLAT = f"rounded=1;arcSize=3;fillColor=#EEF3F6;strokeColor={INK};strokeWidth=2;verticalAlign=top;fontSize=20;fontStyle=1;fontColor={INK};spacingTop=6;"
GROUP = f"rounded=1;arcSize=5;fillColor=#FFFFFF;strokeColor=#C9D2D8;verticalAlign=top;fontSize=15;fontColor={MUTED};spacingTop=2;"
PILL = f"rounded=1;arcSize=12;fillColor=#FFFFFF;strokeColor={GREEN};strokeWidth=2;fontColor={GREEN_T};fontSize=12;"
EXT = f"rounded=1;arcSize=5;fillColor=#FFFFFF;strokeColor={INK};strokeWidth=1.5;fontColor={INK};verticalAlign=top;spacingTop=6;fontSize=12;"
NOTE = f"text;strokeColor=none;fillColor=none;fontSize=11;fontColor={MUTED};align=center;verticalAlign=middle;"
ARROW = f"endArrow=block;endFill=1;strokeColor={LINE};strokeWidth=1.6;fontSize=11;fontColor={MUTED};labelBackgroundColor=#FFFFFF;"
ORTHO = "edgeStyle=orthogonalEdgeStyle;rounded=1;"
CYL = "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=7;fontSize=12;fontColor=#1B3139;"
BRONZE, SILVER, GOLD = "fillColor=#E3B48F;strokeColor=#A07A55;", "fillColor=#E4E7EA;strokeColor=#9AA3AB;", "fillColor=#F3DC8A;strokeColor=#B39440;"
XS = [(10, 200), (210, 380), (392, 760), (772, 1060), (1100, 1300)]   # Sources · Ingest · Transform · Query/Process · Analyse


def sub(title, *lines):
    return f"<b>{title}</b>" + "".join(f"<br><font style='font-size:10px' color='{MUTED}'>{l}</font>" for l in lines)


def pill(d, text, x, y, w, h, icon=None):
    """A 'used here' pill; with a Databricks product icon at its left, the text moves right of it."""
    if not icon:
        return d.v(text, x, y, w, h, PILL)
    cid = d.v(text, x, y, w, h, PILL + "align=left;spacingLeft=36;")
    svg = base64.b64encode((HERE / "dbx_icons" / f"{icon}.svg").read_bytes()).decode()
    d.v("", x + 7, y + (h - 24) / 2, 24, 24, f"shape=image;aspect=fixed;imageAspect=0;image=data:image/svg+xml,{svg};")
    return cid


def frame(d):
    for name, (x1, x2) in zip(("Sources", "Ingest", "Transform", "Query / Process", "Analyse"), XS):
        d.v(name, x1, 10, x2 - x1, 34, LANE)
    d.v("Data Intelligence Platform", 210, 58, 860, 520, PLAT)
    d.v("Orchestration, CI/CD", 220, 100, 840, 72, GROUP + "align=left;verticalAlign=middle;spacingLeft=14;spacingTop=0;")
    d.v("Ingest", 220, 184, 160, 150, GROUP)
    d.v("Data Engineering and Processing", 392, 184, 368, 150, GROUP)
    d.v("Data Warehousing and AI", 772, 184, 288, 150, GROUP)
    d.v("Data and AI Governance – Unity Catalog", 220, 346, 840, 88, GROUP)
    d.v("Data Management", 220, 446, 840, 120, GROUP)


def key(d, y=470):
    d.v("<b>Key</b>", 1100, y, 40, 22, NOTE + f"fontColor={INK};fontSize=13;align=left;")
    d.v("3rd party / outside", 1145, y, 140, 22, f"rounded=1;fillColor=#FFFFFF;strokeColor={INK};fontSize=11;fontColor={MUTED};")
    d.v("Databricks platform", 1145, y + 28, 140, 22, f"rounded=1;fillColor=#EEF3F6;strokeColor={INK};fontSize=11;fontColor={INK};")
    d.v("used here", 1145, y + 56, 140, 22, f"rounded=1;fillColor=#FFFFFF;strokeColor={GREEN};strokeWidth=2;fontSize=11;fontStyle=1;fontColor={GREEN_T};")


def storage(d, text):
    anchor = d.v("", 640, 578, 1, 1, "shape=none;")
    label = d.v(text, 300, 614, 680, 22, NOTE + f"fontColor={INK};fontSize=12;")
    d.v("Storage", 570, 640, 140, 28, LANE)
    d.e(label, anchor, ARROW + "startArrow=block;startFill=1;")


def sources(d, physical):
    kaggle = d.v(sub("Kaggle free GPU", "MedGemma · GPU encoders",
                     "kaggle-medgemma.yml opens a results PR" if physical else "collected into a pull request"), 10, 58, 190, 76, EXT)
    git = d.v(sub("GitHub repo (laptop runs)", "data/datasets/ai_predictions_*.csv" if physical else "committed result files",
                  "llm_details_*.csv · results_manifest.csv" if physical else "with their source and run URL"), 10, 146, 190, 76, EXT)
    key_ = d.v(sub("Synthetic study data", "answer_key/review_key.csv" if physical else "240 de-identified review charts",
                   "data/deid/scores.csv" if physical else "de-identification benchmark", "seeded, no PHI"), 10, 234, 190, 90, EXT)
    return kaggle, git, key_


def analyse(d, physical):
    lead = d.v(sub("Study lead, data science", "Scorecard dashboard" if not physical else "databricks/dashboards/scorecard.lvdash.json",
                   "phenotyping · de-identification"), 1100, 184, 200, 76, EXT)
    sql = d.v(sub("Ad hoc SQL, R, notebooks", "select … from gold_perio_bench.*" if physical else "any gold table"), 1100, 280, 200, 60, EXT)
    rd = d.v(sub("README leaderboard", "35_readme_results.py" if physical else "", "reads the committed files, not gold"), 1100, 360, 200, 60, EXT)
    return lead, sql, rd


# ---------- logical ----------
d = Diagram("gold logical architecture")
frame(d)
pill(d, "<b>Lakeflow Jobs</b>", 440, 120, 170, 34, "lakeflow-jobs")
pill(d, "<b>Asset Bundles</b> · GitHub CI/CD", 630, 120, 240, 34, "databricks")
ing = pill(d, sub("Deployed files", "the bundle syncs", "committed results"), 228, 236, 144, 64, "notebooks")
nb = pill(d, sub("Notebook jobs", "load · read · judge · score"), 402, 222, 170, 50, "notebooks")
gpu = pill(d, sub("Serverless GPU", "MedGemma reader"), 402, 280, 170, 44, "databricks")
py = pill(d, sub("health_transformation_lab_nlp", "metrics in code, never by the LLM"), 584, 236, 166, 64)
ms = pill(d, sub("Model Serving", "LLM judge (pay-per-token)"), 782, 216, 268, 44, "model-serving")
wh = pill(d, sub("SQL warehouse", "AI/BI dashboard · ai_query"), 782, 274, 268, 44, "sql-warehouse")
pill(d, "<b>Access control</b>", 300, 380, 190, 40, "unity-catalog")
pill(d, "<b>Catalog and lineage</b>", 510, 380, 210, 40, "unity-catalog")
pill(d, "<b>MLflow</b> runs and traces", 750, 380, 220, 40, "notebooks")
pill(d, "<b>Delta Lake</b>", 236, 488, 150, 44, "delta-lake")
b = d.v("bronze<br><font style='font-size:10px'>empty for now</font>", 430, 480, 110, 60, CYL + BRONZE)
s = d.v("silver<br><font style='font-size:10px'>empty for now</font>", 580, 480, 110, 60, CYL + SILVER)
g = d.v("<b>gold</b><br><font style='font-size:10px'>results · judge scorecard<br>de-identification scores</font>", 730, 474, 180, 72, CYL + GOLD)
d.e(b, s, ARROW); d.e(s, g, ARROW)
d.v("silver and gold layers are this study's; gold is written by notebook jobs, not a pipeline", 920, 470, 130, 84, NOTE)
kaggle, git, key_ = sources(d, False)
d.e(kaggle, git, ARROW, "PR")
d.e(git, ing, ARROW + "entryX=0;entryY=0.4;")
d.e(key_, ing, ARROW + "entryX=0;entryY=0.8;")
d.e(ing, nb, ARROW); d.e(nb, py, ARROW); d.e(gpu, py, ARROW)
d.e(py, ms, ARROW + ORTHO + "exitX=1;exitY=0.3;entryX=0;entryY=0.5;")
d.e(py, wh, ARROW + ORTHO + "exitX=1;exitY=0.7;entryX=0;entryY=0.5;")
d.e(py, g, ARROW + ORTHO + "exitX=0.5;exitY=1;entryX=0.03;entryY=0;", "writes", points=[(667, 340), (735, 340)])
lead, sql, rd = analyse(d, False)
d.e(wh, lead, ARROW + ORTHO + "exitX=1;exitY=0.3;entryX=0;entryY=0.5;")
d.e(wh, sql, ARROW + ORTHO + "exitX=1;exitY=0.7;entryX=0;entryY=0.5;")
key(d)
storage(d, "Unity Catalog managed storage · landing volume landing_perio_bench.data (logs, scratch files)")
d.write("gold_logical_architecture")

# ---------- physical ----------
d = Diagram("gold physical architecture")
frame(d)
pill(d, sub("databricks.yml", "resources/*.yml", "dev · uat · prod"), 440, 110, 190, 52, "databricks")
pill(d, "<b>deploy.yml</b> → bundle deploy → <b>Load results</b><font style='font-size:10px' color='#5B6B73'><br>"
        "jobs: load_results · medgemma_reader · judge_scorecard · llm_judge · encoder_gpu · study_benchmark</font>", 645, 110, 405, 52, "lakeflow-jobs")
ing = pill(d, sub("Git folder", "data/datasets/", "(bundle sync)"), 228, 236, 144, 64, "notebooks")
nb = pill(d, sub("11 migrate → 10 load results", "07_judge_scorecard.py", "02_llm_judge.sql"), 402, 214, 170, 62, "notebooks")
gpu = pill(d, sub("03 MedGemma reader", "serverless GPU", "6 retries, 30 min apart"), 402, 282, 170, 46, "databricks")
py = pill(d, sub("python/health_transformation_lab_nlp/", "results_store.py · delta.py", "judge_scorecard.py"), 584, 232, 166, 72)
ms = pill(d, sub("serving endpoint", "var.judge_endpoint · max_usd 5"), 782, 216, 268, 44, "model-serving")
wh = pill(d, sub("SQL warehouse var.warehouse_id", "dashboard Scorecard · ai_query"), 782, 274, 268, 44, "sql-warehouse")
pill(d, sub("catalog health_transformation_lab", "group health_transformation_lab_nlp_&lt;target&gt;_admin"), 232, 374, 250, 52, "unity-catalog")
pill(d, sub("schemas", "landing_ · bronze_ · silver_ · gold_perio_bench"), 494, 374, 270, 52, "unity-catalog")
pill(d, sub("MLflow experiment + UC model", "perio_note_classifier"), 776, 374, 274, 52, "notebooks")
pill(d, sub("Delta tables", "UC managed"), 232, 482, 130, 52, "delta-lake")
b = d.v("bronze_perio_bench<br><font style='font-size:10px'>no tables yet</font>", 374, 478, 150, 60, CYL + BRONZE)
s = d.v("silver_perio_bench<br><font style='font-size:10px'>no tables yet</font>", 536, 478, 150, 60, CYL + SILVER)
g = d.v("<b>gold_perio_bench</b><font style='font-size:10px'><br>dim_result_file · fact_prediction · fact_llm_call<br>"
        "fact_chart_answer · fact_judge_call · judge_metric<br>judge_agreement · judge_cost · deid_score<br>"
        "judge_queue · fact_corpus_judge_call<br>dim_study_note · benchmark_metric</font>", 700, 462, 260, 104, CYL + GOLD)
d.e(b, s, ARROW); d.e(s, g, ARROW)
d.v("Gold also gets the OMOP tables person · visit_occurrence · measurement · note (study_benchmark), and the "
    "GPU encoders' rows in fact_prediction (encoder_gpu)", 1100, 586, 200, 84, NOTE + "align=left;")
kaggle, git, key_ = sources(d, True)
d.e(kaggle, git, ARROW, "PR")
d.e(git, ing, ARROW + "entryX=0;entryY=0.4;")
d.e(key_, ing, ARROW + "entryX=0;entryY=0.8;")
d.e(ing, nb, ARROW); d.e(nb, py, ARROW); d.e(gpu, py, ARROW)
d.e(py, ms, ARROW + ORTHO + "exitX=1;exitY=0.3;entryX=0;entryY=0.5;")
d.e(py, wh, ARROW + ORTHO + "exitX=1;exitY=0.7;entryX=0;entryY=0.5;")
d.e(py, g, ARROW + ORTHO + "exitX=0.5;exitY=1;entryX=0.27;entryY=0;", "writes", points=[(667, 340), (770, 340)])
lead, sql, rd = analyse(d, True)
d.e(wh, lead, ARROW + ORTHO + "exitX=1;exitY=0.3;entryX=0;entryY=0.5;")
d.e(wh, sql, ARROW + ORTHO + "exitX=1;exitY=0.7;entryX=0;entryY=0.5;")
key(d)
storage(d, "volume health_transformation_lab.landing_perio_bench.data · runlog logs · encoder_gpu/ CSVs")
d.write("gold_physical_architecture")
