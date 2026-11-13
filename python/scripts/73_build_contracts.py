"""Write or check the gold tables' Open Data Contracts and Data Products (spec 038: US1 #702, US2 #704).

    python scripts/73_build_contracts.py             # rewrite contracts/<schema>/<table>.odcs.yaml and
                                                     # contracts/products/<bench>.odps.yaml from the gold model
    python scripts/73_build_contracts.py --check     # exit 1 and name each stale file; exit 0 when all match
    python scripts/73_build_contracts.py --check --root <dir>   # check another copy of the contracts folder

Every contract and product is validated against the vendored ODCS v3.1.0 or ODPS v1.0.0 JSON Schema
(contracts/schema/) first: one that fails makes the script exit 2 before anything is written. Validation needs
jsonschema (pip install -e ".[dev]").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from health_transformation_lab_nlp import data_contracts as dc
from health_transformation_lab_nlp.paths import CONTRACTS_DIR


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write or check the gold tables' ODCS contracts and ODPS products.")
    ap.add_argument("--check", action="store_true", help="name stale contracts and exit 1 instead of writing")
    ap.add_argument("--root", type=Path, default=CONTRACTS_DIR, help="the contracts folder (default: contracts/)")
    a = ap.parse_args(argv)
    try:
        import jsonschema  # noqa: F401 - checked before any work (AGENTS.md: a required setting fails at once)
    except ImportError:
        print("jsonschema is needed to validate the contracts: pip install -e \".[dev]\"", file=sys.stderr)
        return 2
    docs, products = dc.all_contracts(), dc.all_products()
    odcs, odps = f"ODCS {dc.ODCS_API_VERSION}", f"ODPS {dc.ODPS_API_VERSION}"
    invalid = {f"{key}.odcs.yaml": (odcs, errors) for key, doc in docs.items() if (errors := dc.validate(doc))}
    invalid |= {f"{key}.odps.yaml": (odps, errors) for key, doc in products.items()
                if (errors := dc.validate_product(doc))}
    for rel, (standard, errors) in invalid.items():
        print(f"{rel}: not valid {standard}: {errors[0]}", file=sys.stderr)
    if invalid:
        return 2
    counted = f"{len(docs)} contracts and {len(products)} data products"
    if a.check:
        stale = dc.stale_contracts(a.root) + dc.stale_products(a.root)
        for rel in stale:
            print(f"stale: {rel} (run python scripts/73_build_contracts.py)")
        if not stale:
            print(f"{counted} match the gold model and validate against {odcs} and {odps}")
        return 1 if stale else 0
    dc.write_contracts(a.root)
    dc.write_products(a.root)
    print(f"wrote {counted} under {a.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
