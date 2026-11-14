"""Regenerate the results leaderboards from committed results (no re-runs): the summary block in
the EDR study page (docs/edr/README.md) and the full tables in docs/results.md.

    python scripts/35_readme_results.py           # rewrite both
    python scripts/35_readme_results.py --check   # exit 1 if either is stale

Note readers (data/datasets/ladder/), the rule phenotypes (answer key) and de-identification
(data/deid/). Method and ranking: health_transformation_lab_nlp/readme_results.py.
"""

import argparse
import sys

from health_transformation_lab_nlp import readme_results as rr
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("35_readme_results", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
a = ap.parse_args()

inp = rr.load_inputs()
readme = rr.SUMMARY_DOC
text = readme.read_text()
new = {readme: rr.update_readme(text, rr.results_markdown(inp)), rr.RESULTS_DOC: rr.details_markdown(inp)}
stale = [p for p, t in new.items() if not p.exists() or p.read_text() != t]
if a.check:
    sys.exit(f"stale: {', '.join(p.name for p in stale)}; run python scripts/35_readme_results.py" if stale else 0)
for p in stale:
    p.write_text(new[p])
print("updated:", ", ".join(p.name for p in stale) or "nothing")
