"""Build the website's copies of the decks and their covers (issue #374).

The website repository (healthtransformationlab/healthtransformationlab.github.io) serves docs/edr/deck.html as
perio-bench/index.html and docs/pitch/deck.html as oral-health-bench/index.html, with the two covers in img/. Its
only change to a deck is the icon links after <title>. .github/workflows/copy-decks-to-site.yml runs this on every
push to main that touches a deck or a cover, then commits to the site only when something changed.

    python .github/scripts/copy_decks_to_site.py check-auth         # SITE_DEPLOY_KEY, else SITE_PUSH_TOKEN (#464)
    python .github/scripts/copy_decks_to_site.py check-token        # SITE_PUSH_TOKEN present and fine-grained
    python .github/scripts/copy_decks_to_site.py build --site DIR   # write the copies into a site checkout

Standard library only, so the workflow needs no install.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

TOKEN_NAME = "SITE_PUSH_TOKEN"
KEY_NAME = "SITE_DEPLOY_KEY"   # an SSH deploy key with write access to the site; never expires (#464)
SITE_REPO = "healthtransformationlab/healthtransformationlab.github.io"

# source in this repo -> path in the site repo
DECKS = {"docs/edr/deck.html": "perio-bench/index.html",
         "docs/pitch/deck.html": "oral-health-bench/index.html"}
COVERS = {"docs/img/edr_deck_cover.png": "img/edr_deck_cover.png",
          "docs/img/pitch_deck_cover.png": "img/pitch_deck_cover.png"}

# What the site adds right after </title> (copied from the live site pages, 2026-11-01)
ICON_LINKS = ('<link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" href="/favicon.svg" '
              'type="image/svg+xml"><link rel="apple-touch-icon" href="/apple-touch-icon.png">'
              '<link rel="manifest" href="/site.webmanifest"><meta name="theme-color" content="#0F2A33">')

# A fine-grained personal access token: github_pat_ then letters, digits and underscores (82 of them today)
_FINE_GRAINED = re.compile(r"github_pat_[A-Za-z0-9_]{50,}")


def site_copy(html: str) -> str:
    """The deck as the site serves it: the deck with the icon links inserted once, right after </title>."""
    if "</title>" not in html:
        raise ValueError("the deck has no </title>, so there is nowhere to put the icon links")
    if ICON_LINKS in html:
        raise ValueError("the deck already carries the site's icon links; they belong only in the site copy")
    head, tail = html.split("</title>", 1)
    return head + "</title>" + ICON_LINKS + tail


def build(repo_root: Path, site_dir: Path) -> list[str]:
    """Write each deck's site copy and each cover into site_dir. Returns the site paths whose bytes changed;
    other files in the site are left alone."""
    wanted = {dst: site_copy((repo_root / src).read_text(encoding="utf-8")).encode("utf-8")
              for src, dst in DECKS.items()}
    wanted |= {dst: (repo_root / src).read_bytes() for src, dst in COVERS.items()}
    changed = []
    for dst, data in wanted.items():
        target = site_dir / dst
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        changed.append(dst)
    return changed


def check_token_shape(token: str) -> None:
    """Fail at once, naming the token, when it is missing or isn't a fine-grained token. Never echoes it."""
    if not token.strip():
        raise ValueError(f"{TOKEN_NAME} is missing. Make a fine-grained token for {SITE_REPO} only, "
                         "Contents read and write, 90 days at most, and save it as the repository secret "
                         f"{TOKEN_NAME} (ops/secrets_register.yaml).")
    if not _FINE_GRAINED.fullmatch(token):
        raise ValueError(f"{TOKEN_NAME} is not a fine-grained token (github_pat_...). Make one for {SITE_REPO} "
                         "only, Contents read and write, 90 days at most (ops/secrets_register.yaml).")


def check_key_shape(key: str) -> None:
    """Fail at once, naming the secret, when it isn't an OpenSSH private key. Never echoes it."""
    k = key.strip()
    if not (k.startswith("-----BEGIN OPENSSH PRIVATE KEY-----") and k.endswith("-----END OPENSSH PRIVATE KEY-----")):
        raise ValueError(f"{KEY_NAME} is not an OpenSSH private key (-----BEGIN OPENSSH PRIVATE KEY----- ... END). "
                         "Save the private half of the key pair, not the .pub file (ops/secrets_register.yaml).")


def auth_method(env) -> str:
    """"key" when SITE_DEPLOY_KEY is set (checked), else "token" when SITE_PUSH_TOKEN is (checked). With neither,
    fail naming both, the deploy key first: it never expires (#464)."""
    if (env.get(KEY_NAME) or "").strip():
        check_key_shape(env[KEY_NAME])
        return "key"
    if (env.get(TOKEN_NAME) or "").strip():
        check_token_shape(env[TOKEN_NAME])
        return "token"
    raise ValueError(f"Neither {KEY_NAME} nor {TOKEN_NAME} is set. Preferred: a deploy key, which never expires. Run "
                     f"ssh-keygen -t ed25519 -N '' -f site_deploy_key, add site_deploy_key.pub to {SITE_REPO} -> "
                     f"Settings -> Deploy keys with Allow write access, and save site_deploy_key as the repository "
                     f"secret {KEY_NAME} (ops/secrets_register.yaml).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-auth", help=f"check {KEY_NAME}, else {TOKEN_NAME}; write method=key|token to GITHUB_OUTPUT")
    sub.add_parser("check-token", help=f"check {TOKEN_NAME} is present and fine-grained")
    b = sub.add_parser("build", help="write the site copies into a checkout of the site")
    b.add_argument("--site", required=True, type=Path, help="the site checkout")
    b.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2], help="this repository")
    args = parser.parse_args(argv)

    if args.command == "check-auth":
        try:
            method = auth_method(os.environ)
        except ValueError as e:
            print(f"::error::{e}")
            return 1
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
                f.write(f"method={method}\n")
        print(f"Pushing to the site with {KEY_NAME if method == 'key' else TOKEN_NAME}.")
        return 0

    if args.command == "check-token":
        try:
            check_token_shape(os.environ.get(TOKEN_NAME, ""))
        except ValueError as e:
            print(f"::error::{e}")
            return 1
        print(f"{TOKEN_NAME} is present and fine-grained.")
        return 0

    changed = build(args.repo, args.site)
    print("\n".join(f"changed: {p}" for p in changed) or "The site's copies are already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
