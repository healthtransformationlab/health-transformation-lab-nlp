"""Copy each published snapshot and add one file at its root: conftest.py (the adapter). Nothing else changes."""
import io
import sys
import tarfile
from pathlib import Path

src, dst, conf = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]).read_bytes()
dst.mkdir(parents=True, exist_ok=True); n = 0; had = []
for tgz in sorted(src.glob("*.tgz")):
    out = dst / tgz.name
    with tarfile.open(tgz, "r:gz") as tin, tarfile.open(out, "w:gz", compresslevel=1) as tout:
        names = set()
        for m in tin:
            names.add(m.name.lstrip("./"))
            tout.addfile(m, tin.extractfile(m) if m.isfile() else None)
        if "conftest.py" in names:
            had.append(tgz.name)
        else:
            ti = tarfile.TarInfo("conftest.py"); ti.size = len(conf); ti.mode = 0o644
            tout.addfile(ti, io.BytesIO(conf))
    n += 1
print(n, "snapshots adapted;", "already had a root conftest.py:", had)
