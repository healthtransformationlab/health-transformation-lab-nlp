"""Build a deck's PowerPoint from its slide sources (issue #923): docs/<deck>/slides/NN-<id>.html, the same files
docs/build_decks.py turns into deck.html. One PowerPoint slide per HTML slide, in order: the kicker, the heading,
the cards, bullets and closing band as editable text boxes, the footer, and the speaker notes in the notes pane.

    python docs/build_pptx.py            # every deck in PPTX_NAMES
    python docs/build_pptx.py access     # one deck

Edit the HTML slides, then rebuild both: python docs/build_decks.py access && python docs/build_pptx.py access
"""

import html
import importlib.util
import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

DOCS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("build_decks", DOCS / "build_decks.py")
build_decks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_decks)

# deck folder under docs/ -> the PowerPoint written beside its deck.html
PPTX_NAMES = {"access": "access_bench.pptx"}

PX = 6350                     # EMU per pixel of the 1920 x 1080 HTML slide, so the layout carries over 1:1
INK, MUTED, ACCENT, PAPER, CARD, BAND = "15303A", "5C6F75", "B4501F", "F7F5EF", "FDFCF9", "ECE8DD"
NAVY, CREAM, PEACH, MIST = "0F2A33", "F7F5EF", "F2A070", "D5E3E1"
SERIF, SANS = "Libre Baskerville", "Public Sans"


def plain(fragment: str) -> str:
    """Text of an HTML fragment: tags dropped, entities decoded, spaces collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def _paras(fragment: str) -> list[str]:
    return [plain(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", fragment, re.DOTALL)]


def parts(section: str) -> dict:
    """The pieces of one slide: kicker, headings, cards, bullets, band, paragraphs, footer."""
    found = lambda pattern: re.search(pattern, section, re.DOTALL)
    kicker = found(r'<p style="[^"]*text-transform:uppercase[^"]*">(.*?)</p>')
    band = found(r'<p style="[^"]*background:#ECE8DD[^"]*">(.*?)</p>')
    footer = found(r'<p style="position:absolute[^"]*">(.*?)</p>')
    cards = [_paras(c) for c in re.findall(r'<div style="flex:1;[^"]*">(.*?)</div>', section, re.DOTALL)]
    return {"kicker": plain(kicker.group(1)) if kicker else "",
            "h1": [plain(h) for h in re.findall(r"<h1[^>]*>(.*?)</h1>", section, re.DOTALL)],
            "h2": [plain(h) for h in re.findall(r"<h2[^>]*>(.*?)</h2>", section, re.DOTALL)],
            "cards": cards,
            "bullets": [plain(li) for li in re.findall(r"<li>(.*?)</li>", section, re.DOTALL)],
            "band": plain(band.group(1)) if band else "",
            "footer": plain(footer.group(1)) if footer else "",
            "paras": _paras(re.sub(r"<div style=\"flex:1;.*?</div>", "", section, flags=re.DOTALL))}


def _box(slide, x, y, w, h, fill=None):
    shape = slide.shapes.add_textbox(Emu(x * PX), Emu(y * PX), Emu(w * PX), Emu(h * PX))
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    frame = shape.text_frame
    frame.word_wrap = True
    for side in ("left", "right", "top", "bottom"):
        setattr(frame, f"margin_{side}", Emu((24 if fill else 0) * PX))
    return frame


def _write(frame, lines, size, color, *, font=SANS, bold=False, bullet=False, first_bold=False):
    for i, text in enumerate(lines):
        para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        run = para.add_run()
        run.text = ("• " if bullet else "") + text
        run.font.size, run.font.name = Pt(size * 0.75), font
        run.font.bold = bold or (first_bold and i == 0)
        run.font.color.rgb = RGBColor.from_string(color)
        para.space_after = Pt(8)


def _background(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor.from_string(color)


def add_slide(prs, sid: str, section: str, notes: str):
    slide = prs.slides.add_slide(prs.slide_layouts[6])               # blank
    p = parts(section)
    if p["h1"]:                                                       # a cover
        _background(slide, NAVY)
        _write(_box(slide, 128, 110, 1664, 50), [p["kicker"]], 24, PEACH, bold=True)
        _write(_box(slide, 128, 240, 1664, 120), p["h1"][:1], 80, CREAM, font=SERIF, bold=True)
        _write(_box(slide, 128, 350, 1664, 120), p["h1"][1:], 80, PEACH, font=SERIF, bold=True)
        rest = [t for t in p["paras"] if t != p["kicker"]]
        _write(_box(slide, 128, 520, 1600, 420), rest[:-1], 36, MIST)
        _write(_box(slide, 128, 960, 1664, 50), rest[-1:], 24, "A9C2BF")
    else:
        _background(slide, PAPER)
        _write(_box(slide, 128, 100, 1664, 40), [p["kicker"]], 24, ACCENT, bold=True)
        _write(_box(slide, 128, 150, 1664, 120), p["h2"], 46, INK, font=SERIF, bold=True)
        y = 300
        if p["cards"]:
            n, gap = len(p["cards"]), 16
            w = (1664 - gap * (n - 1)) // n
            for i, card in enumerate(p["cards"]):
                frame = _box(slide, 128 + i * (w + gap), y, w, 420, fill=CARD)
                _write(frame, card[:1], 28, ACCENT, bold=True)
                _write_more(frame, card[1:2], 26, INK, bold=True)
                _write_more(frame, card[2:], 22, MUTED)
            y += 460
        if p["bullets"]:
            _write(_box(slide, 128, y, 1664, 470), p["bullets"], 24, INK, bullet=True)
            y += 500
        if p["band"]:
            _write(_box(slide, 128, max(y, 790), 1664, 150, fill=BAND), [p["band"]], 26, INK)
        _write(_box(slide, 128, 1000, 1664, 40), [p["footer"]], 22, MUTED)
    slide.notes_slide.notes_text_frame.text = plain(notes)
    return slide


def _write_more(frame, lines, size, color, **kw):
    for text in lines:
        para = frame.add_paragraph()
        run = para.add_run()
        run.text = text
        run.font.size, run.font.name = Pt(size * 0.75), SANS
        run.font.bold = kw.get("bold", False)
        run.font.color.rgb = RGBColor.from_string(color)
        para.space_after = Pt(8)


def build(deck: str) -> Presentation:
    """The PowerPoint for docs/<deck>/, one slide per HTML slide."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(1920 * PX), Emu(1080 * PX)
    prs.core_properties.title = build_decks.DECKS[deck][0]
    prs.core_properties.author = "Health Transformation Lab"
    for sid, section, notes in build_decks.slides(DOCS / deck):
        add_slide(prs, sid, section, notes)
    return prs


def main(decks):
    for deck in decks:
        out = DOCS / deck / PPTX_NAMES[deck]
        build(deck).save(out)
        print(f"built docs/{deck}/{out.name}")


if __name__ == "__main__":
    unknown = set(sys.argv[1:]) - set(PPTX_NAMES)
    if unknown:
        sys.exit(f"unknown deck {', '.join(sorted(unknown))}: choose from {', '.join(sorted(PPTX_NAMES))}")
    main(sys.argv[1:] or sorted(PPTX_NAMES))
