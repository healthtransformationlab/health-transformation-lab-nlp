"""Write the grader dashboards and Genie spaces (spec 019) from health_transformation_lab_nlp/dashboards.py.

    python scripts/42_build_dashboards.py           # databricks/dashboards/<name>.lvdash.json, databricks/genie/<name>.geniespace.json
    python scripts/42_build_dashboards.py --check   # exit 1 if a committed file is stale
"""

import argparse
import sys

from health_transformation_lab_nlp import dashboards
from health_transformation_lab_nlp.paths import REPO_ROOT
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("42_build_dashboards", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
a = ap.parse_args()

files = {REPO_ROOT / "databricks" / "dashboards" / f"{n}.lvdash.json": dashboards.render(n)
         for n in dashboards.DASHBOARDS}
files |= {REPO_ROOT / "databricks" / "genie" / f"{n}.geniespace.json": dashboards.render_genie(n)
          for n in dashboards.GENIE_SPACES}
stale = [p for p, text in files.items() if not p.exists() or p.read_text() != text]
if a.check:
    sys.exit(f"stale: {', '.join(p.name for p in stale)}; run python scripts/42_build_dashboards.py" if stale else 0)
for p in stale:
    p.parent.mkdir(exist_ok=True)
    p.write_text(files[p])
print("updated:", ", ".join(p.name for p in stale) or "nothing")
