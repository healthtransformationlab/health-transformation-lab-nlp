"""Write docs/standards.md: the case definitions, sources and reading orders side by side, and where they disagree
(#391). Read from committed files; nothing is re-run. Synthetic data.

    python scripts/48_standards_doc.py           # rewrite docs/standards.md
    python scripts/48_standards_doc.py --check   # exit 1 if it is stale
"""

import sys

from health_transformation_lab_nlp import standards_doc

text = standards_doc.markdown()
if "--check" in sys.argv:
    stale = standards_doc.DOC.read_text() != text
    print("docs/standards.md is stale: run python scripts/48_standards_doc.py" if stale else "up to date")
    sys.exit(1 if stale else 0)
standards_doc.DOC.write_text(text)
print("wrote docs/standards.md")
