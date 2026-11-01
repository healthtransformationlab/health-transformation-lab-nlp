"""Issue #221: Health Transformation Lab is the name, not a "working name" or a name "for now". Past PR reviews in
pull_requests/ are records and stay as written."""
import re
import subprocess

from health_transformation_lab_nlp.paths import REPO_ROOT

PHRASE = re.compile(r"working name|Health Transformation Lab for now", re.IGNORECASE)
ALLOWED = {"python/tests/test_no_working_name.py"}


def test_no_file_calls_the_lab_a_working_name():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
    hits = []
    for rel in (f for f in out.decode().split("\0") if f):
        path = REPO_ROOT / rel
        if rel in ALLOWED or rel.startswith("pull_requests/") or rel == "data/tasks/task_manifest.csv" \
                or not path.is_file():   # the manifest is a verbatim record of past titles (spec 028)
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:            # binary: images, archives
            continue
        hits += [f"{rel}:{n}" for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1)
                 if PHRASE.search(line)]
    assert not hits, "Drop \"working name\" (issue #221):\n" + "\n".join(hits)
