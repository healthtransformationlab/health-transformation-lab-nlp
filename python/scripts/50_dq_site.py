"""Write docs/site/data-quality.json, the data-quality results for the website's static page (#399).
Read from committed results; nothing is re-run. Synthetic data.

    python scripts/50_dq_site.py           # write it
    python scripts/50_dq_site.py --check   # exit 1 if it is stale
"""

import json
import sys

from health_transformation_lab_nlp import dq_site

data = dq_site.build()
if "--check" in sys.argv:
    stale = not dq_site.OUT.exists() or json.loads(dq_site.OUT.read_text()) != data
    print("docs/site/data-quality.json is stale: run python scripts/50_dq_site.py" if stale else "up to date")
    sys.exit(1 if stale else 0)
dq_site.OUT.parent.mkdir(parents=True, exist_ok=True)
dq_site.OUT.write_text(json.dumps(data, indent=1) + "\n")
print(f"wrote {dq_site.OUT.relative_to(dq_site.REPO_ROOT)}")
