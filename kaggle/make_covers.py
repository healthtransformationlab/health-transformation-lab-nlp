"""Draw the Kaggle cover images, kaggle/covers/<slug>.png (spec 034 US1, #533). Seeded, so a rerun gives the same
files; 1120 x 560 (2:1), no text, since Kaggle crops covers and shows the title beside them.

    python kaggle/make_covers.py

    perio-bench-notes        a probing chart: two arches of teeth, each site shaded from healthy to deep pocket
    perio-bench-results      a leaderboard: methods as bars with 95% interval whiskers
    health-transformation-lab-coding-agent-tasks   a code graph: nodes and call edges
"""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "covers"
W, H = 1120, 560
INK = (24, 31, 56)
PAPER = (246, 244, 238)
GOOD, MID, BAD = (64, 160, 120), (240, 180, 60), (205, 70, 70)


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _pocket(depth):   # 1-8 mm: green, amber, red
    t = min(max((depth - 1) / 7, 0), 1)
    return _mix(GOOD, MID, t * 2) if t < 0.5 else _mix(MID, BAD, (t - 0.5) * 2)


def notes(rng):
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    for row, y0 in enumerate((95, 315)):
        for k in range(16):
            x0 = 52 + k * 64
            d.rounded_rectangle([x0, y0, x0 + 52, y0 + 150], radius=18, fill=PAPER)
            sick = rng.random() < 0.35
            for s in range(3):   # three sites a side, two sides
                for side, yy in enumerate((y0 + 14, y0 + 112)):
                    depth = rng.uniform(4, 8) if sick and rng.random() < 0.7 else rng.uniform(1, 3.5)
                    d.ellipse([x0 + 6 + s * 15, yy, x0 + 18 + s * 15, yy + 12], fill=_pocket(depth))
    return im


def results(rng):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    accs = sorted((rng.uniform(0.45, 0.96) for _ in range(9)), reverse=True)
    for i, a in enumerate(accs):
        y = 60 + i * 50
        x1 = 90 + a * 900
        d.rounded_rectangle([90, y, x1, y + 30], radius=8, fill=_mix(BAD, GOOD, (a - 0.45) / 0.51))
        half = rng.uniform(25, 60)
        d.line([x1 - half, y + 15, x1 + half, y + 15], fill=INK, width=4)
        for x in (x1 - half, x1 + half):
            d.line([x, y + 5, x, y + 25], fill=INK, width=4)
    d.line([90, 40, 90, 520], fill=INK, width=5)
    return im


def tasks(rng):
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)
    nodes = []
    for _ in range(46):
        nodes.append((rng.uniform(60, W - 60), rng.uniform(50, H - 50), rng.choice((7, 9, 12, 16))))
    for i, (x, y, _) in enumerate(nodes):   # each node calls its nearest few
        near = sorted(range(len(nodes)), key=lambda j: math.dist((x, y), nodes[j][:2]))[1:4]
        for j in near[: rng.randint(1, 3)]:
            d.line([x, y, nodes[j][0], nodes[j][1]], fill=(92, 108, 160), width=3)
    for x, y, r in nodes:
        colour = rng.choice((GOOD, MID, PAPER, (120, 170, 235)))
        d.ellipse([x - r, y - r, x + r, y + r], fill=colour, outline=INK, width=2)
    return im


COVERS = {"perio-bench-notes": (notes, 101), "perio-bench-results": (results, 202),
          "health-transformation-lab-coding-agent-tasks": (tasks, 303)}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for slug, (draw, seed) in COVERS.items():
        draw(random.Random(seed)).save(OUT / f"{slug}.png", optimize=True)
        print(f"wrote {OUT.name}/{slug}.png")


if __name__ == "__main__":
    main()
