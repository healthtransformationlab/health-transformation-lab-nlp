"""Every column description of a published Kaggle dataset, for pasting into Kaggle's own editor (#694).

    python kaggle/column_descriptions.py --out build/column_descriptions.html [--dataset notes results tasks]

Kaggle's server drops the column descriptions sent through its API (Kaggle/kaggle-cli#1207); what is typed into the
site's editor is kept. So until that issue closes, the descriptions in kaggle/dataset_docs.yaml reach Kaggle by hand:
this writes one page listing each dataset, file (by the name Kaggle shows, publish.kaggle_name) and column, with its
description and a Copy button, and a link to each dataset's page on Kaggle. Nothing is sent anywhere.
"""
import argparse
import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dataset_docs as docs  # noqa: E402  kaggle/dataset_docs.py
import publish  # noqa: E402  kaggle/publish.py: the notes and results datasets

OWNER = "jcblearning"


def _files(name: str) -> tuple[str, dict]:
    """(slug, {path in the dataset: source file}) for a dataset name: notes, results or tasks."""
    if name == "tasks":     # its CSV files only: the rest have no columns, and listing them needs a full build
        import publish_tasks
        from health_transformation_lab_nlp.paths import TASKS_DIR
        csvs = {"tasks_excluded.csv": TASKS_DIR / "tasks_excluded.csv", "task_gates.csv": TASKS_DIR / "task_gates.csv",
                publish_tasks.VERIFICATION: TASKS_DIR / "official_verifier" / publish_tasks.VERIFICATION}
        return publish_tasks.SLUG, csvs
    return publish.DATASETS[name]["slug"], publish.files_of(name)


def column_rows(name: str) -> list[dict]:
    """One row per column of each file with columns: dataset_slug, file_name (Kaggle's form), column_name,
    description_text (from kaggle/dataset_docs.yaml)."""
    slug, files = _files(name)
    rows = []
    for dest, src in files.items():
        for col in docs.columns_of(Path(src)):
            rows.append({"dataset_slug": slug, "file_name": publish.kaggle_name(dest), "column_name": col,
                         "description_text": docs.column_description(slug, dest, col) or ""})
    return rows


def page(rows: list[dict]) -> str:
    """A self-contained HTML page: per dataset and file, each column with its description and a Copy button."""
    e = html.escape
    out, last_slug, last_file = [], None, None
    for r in rows:
        if r["dataset_slug"] != last_slug:
            if last_file is not None:
                out.append("</tbody></table>")
            last_slug, last_file = r["dataset_slug"], None
            n = sum(1 for x in rows if x["dataset_slug"] == last_slug)
            url = f"https://www.kaggle.com/datasets/{OWNER}/{last_slug}/data"
            out.append(f'<h2>{e(last_slug)} <small>({n} columns)</small></h2>'
                       f'<p><a href="{url}" target="_blank" rel="noopener">Open on Kaggle</a>: choose a file, then '
                       "the pencil beside each column.</p>")
        if r["file_name"] != last_file:
            if last_file is not None:
                out.append("</tbody></table>")
            last_file = r["file_name"]
            out.append(f'<h3>{e(last_file)}</h3><table><tbody>')
        out.append(f'<tr><th>{e(r["column_name"])}</th><td><span class="d">{e(r["description_text"])}</span></td>'
                   '<td><button class="copy" type="button">Copy</button></td></tr>')
    if last_file is not None:
        out.append("</tbody></table>")
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Kaggle column descriptions</title>"
            "<style>:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e3e3e3;--accent:#1f5fbf}"
            "@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#eee;--muted:#aaa;--line:#333;--accent:#7aa7ef}}"
            "body{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0 auto;"
            "max-width:900px;padding:16px}table{width:100%;border-collapse:collapse;margin-bottom:12px}"
            "th,td{border-top:1px solid var(--line);padding:6px 4px;text-align:left;vertical-align:top}"
            "th{font-family:ui-monospace,monospace;font-weight:600;width:28%;word-break:break-all}"
            "button{font:inherit;padding:4px 10px;border:1px solid var(--accent);color:var(--accent);"
            "background:transparent;border-radius:6px}button.done{background:var(--accent);color:var(--bg)}"
            "small,p{color:var(--muted)}a{color:var(--accent)}</style></head><body>"
            "<h1>Kaggle column descriptions</h1><p>Kaggle drops column descriptions sent through its API "
            "(Kaggle/kaggle-cli#1207), so they are entered in its editor. Each is copied from "
            "kaggle/dataset_docs.yaml; files are named as Kaggle shows them.</p>"
            + "".join(out) +
            "<script>document.addEventListener('click',function(ev){var b=ev.target;"
            "if(!b.classList||!b.classList.contains('copy'))return;"
            "var t=b.closest('tr').querySelector('.d').textContent;"
            "navigator.clipboard.writeText(t).then(function(){b.textContent='Copied';b.classList.add('done');});});"
            "</script></body></html>")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dataset", nargs="+", default=["tasks", "notes", "results"],
                    choices=["notes", "results", "tasks"])
    a = ap.parse_args()
    rows = [r for name in a.dataset for r in column_rows(name)]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(page(rows))
    print(f"wrote {a.out}: {len(rows)} columns")


if __name__ == "__main__":
    main()
