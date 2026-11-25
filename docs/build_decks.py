"""Build the slide decks from their slide sources: docs/<deck>/slides/NN-<id>.html, one <section> per slide with
the speaker notes in its <aside>. Writes each deck's deck.html (a reveal.js presentation, one slide at a time: arrow
keys or swipe to page, N for the notes, S for the speaker view, and a top nav back to the site) and
full_text_and_notes.md (every slide's text and notes, for reading or search).

    python docs/build_decks.py           # every deck
    python docs/build_decks.py edr       # one deck
"""

import html
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
PERSONAL = "A personal idea, not affiliated with or endorsed by any organization."
SITE = "https://healthtransformationlab.org"
REPO = "https://github.com/healthtransformationlab/health-transformation-lab-nlp"
# deck folder under docs/ -> its page on the site and its name in the top nav
SITE_PAGES = {"edr": ("perio-bench", "PerioBench"), "pitch": ("oral-health-bench", "OralHealthBench"),
              "access": ("access-bench", "AccessBench")}
# deck folder under docs/ -> (title, the line above the slides)
DECKS = {
    "pitch": ("Health Transformation Lab: Shark Tank pitch",
              f'{PERSONAL} Figures are cited on each slide; nothing marked "to measure" has been measured.'),
    "access": ("Health Transformation Lab: AccessBench, does the answer get you care?",
               (f"{PERSONAL} Exploratory: synthetic questions written from public sources; scores are preliminary (one AI "
                "judge, no independent reviewer yet); anything simulated is labelled simulated.")),
    "edr": ("Health Transformation Lab: PerioBench, the dental record (EDR) study, executive pitch",
            (f"{PERSONAL} Synthetic data only: results are scored against the generator's truth, not clinical "
             "performance, and costs use illustrative prices.")),
}
REVEAL = "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0"
# Subresource integrity for those files (sha384 of the npm package's own files): a changed file is refused
SRI = {"css": "sha384-YgvgKeZJykuztG+iQPoZHNZENTFZvOcOJ/uRzmJTje6GHYN9zAw+y5rx/L8MQKA/",
       "js": "sha384-M/JtqCVlLcK9lwVnBnMXP0V577CBULkjodKsR/PITOe4MSKNbbwqCemEyluOw0+5",
       "notes": "sha384-vGIe90H8q0nlnrw/zr9vn+r39OtjvzBfai9voOybn5Bx+KmKLtSxhM+YIfcrsfI3"}
HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&display=swap"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400..700&display=swap"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Caveat:wght@500..700&display=swap"><link rel="stylesheet" href="{reveal}/dist/reveal.css" integrity="{sri[css]}" crossorigin="anonymous">
<style>html,body{{height:100%}}body{{margin:0;background:#2b2b2b;font-family:Arial,sans-serif}}*{{box-sizing:border-box;margin:0}}
td,th{{padding:12px 16px;border-bottom:1px solid #D9D3C4}}ul{{padding-left:1.2em}}
.topnav{{position:fixed;top:0;left:0;right:0;z-index:50;height:56px;background:#0F2A33;border-bottom:1px solid rgba(213,227,225,.14);font-family:'Public Sans',Arial,sans-serif}}
.topnav .bar{{height:100%;padding:0 16px;display:flex;align-items:center;justify-content:space-between;gap:12px}}
.home{{display:flex;align-items:center;gap:10px;font-family:'Libre Baskerville',Georgia,serif;font-weight:700;font-size:15px;color:#F7F5EF;text-decoration:none;white-space:nowrap}}
.home .mark{{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:#F2A070;color:#0F2A33;font-size:15px}}
.home:hover .name{{text-decoration:underline}}
.topnav .links{{display:flex;flex:1 1 auto;justify-content:flex-end;align-items:center;gap:4px;min-width:0}}
.topnav .links a,.topnav button{{color:#D5E3E1;text-decoration:none;font:600 14px 'Public Sans',Arial,sans-serif;padding:7px 11px;border-radius:8px;background:none;border:0;cursor:pointer;white-space:nowrap}}
.topnav .links a:hover,.topnav button:hover{{color:#F7F5EF;background:rgba(255,255,255,.07)}}.topnav .links a.active,.topnav button[aria-pressed=true]{{color:#F2A070}}
.topnav .links a.cta{{background:#F2A070;color:#0F2A33;margin-left:6px}}.topnav .links a.cta:hover{{background:#F7F5EF}}
.topnav select{{flex:1 1 auto;width:280px;max-width:280px;min-width:72px;font:600 14px 'Public Sans',Arial,sans-serif;color:#F7F5EF;background:#15303A;border:1px solid rgba(213,227,225,.3);border-radius:8px;padding:6px 8px}}
.disclaimer{{position:fixed;top:56px;left:0;right:0;z-index:40;padding:6px 16px;background:#15303A;color:#D5E3E1;font:13px/1.45 'Public Sans',Arial,sans-serif}}
.reveal-viewport,.reveal{{background:#2b2b2b}}.reveal{{position:fixed;top:84px;left:0;right:0;bottom:0;width:auto;height:auto}}
.reveal .slides{{text-align:left}}.reveal .slides>section{{height:1080px}}.reveal .progress{{color:#F2A070}}
.topnav .pager{{display:flex;flex:0 1 auto;align-items:center;gap:4px;min-width:0}}
.topnav .pager button{{color:#0F2A33;background:#F2A070;padding:7px 12px}}.topnav .pager button:hover{{color:#0F2A33;background:#F7F5EF}}
.topnav .pager button:disabled{{opacity:.35;cursor:default;background:#F2A070}}
.topnav button:focus-visible,.topnav select:focus-visible{{outline:2px solid #F7F5EF;outline-offset:2px}}
/* reveal's own arrows: at the slide's left and right edges (controlsLayout 'edges'), larger, on a solid disc */
.reveal .controls{{color:#F2A070;font-size:14px}}
.reveal .controls .navigate-left,.reveal .controls .navigate-right{{background:rgba(15,42,51,.85);border-radius:50%;box-shadow:0 2px 10px rgba(0,0,0,.35)}}
.reveal .slide-number{{font:600 14px 'Public Sans',Arial,sans-serif;background:rgba(15,42,51,.8);color:#F7F5EF}}
.notes-panel{{position:fixed;left:0;right:0;bottom:0;z-index:45;max-height:35vh;overflow:auto;background:#f4f1ea;color:#222;padding:16px 20px 28px;font-size:15px;line-height:1.5;box-shadow:0 -8px 24px rgba(0,0,0,.3)}}
.notes-panel[hidden]{{display:none}}
/* the slide picker shrinks first; then the site name goes, then the deck links; on phones the pager's labels and
   the GitHub link (also on the home page) go, so Previous, the picker, Next and Notes always fit */
@media (max-width:1180px){{.home .name{{display:none}}}}
@media (max-width:820px){{.topnav .links a.deck{{display:none}}}}
@media (max-width:560px){{.topnav .pager .lbl,.topnav .links a.cta{{display:none}}.topnav .pager button{{padding:7px 13px;font-size:16px}}}}</style></head><body>
<nav class="topnav" aria-label="Main"><div class="bar">
<a class="home" href="{site}/" title="Back to the Health Transformation Lab home page"><span class="mark" aria-hidden="true">←</span><span class="name">Health Transformation Lab</span></a>
<div class="links">{decks}<span class="pager"><button id="deck-prev" aria-label="Previous slide" title="Previous slide (←)">‹<span class="lbl"> Previous</span></button>
<select id="deck-jump" aria-label="Go to slide">{options}</select>
<button id="deck-next" aria-label="Next slide" title="Next slide (→)"><span class="lbl">Next </span>›</button></span>
<button id="deck-notes-btn" aria-pressed="false" title="Speaker notes (N)">Notes</button>
<a class="cta" href="{repo}" target="_blank" rel="noopener">GitHub ↗</a></div></div></nav>
<p class="disclaimer" id="deck-disclaimer">{note}</p>
<div class="reveal"><div class="slides">
"""
TAIL = """</div></div>
<div class="notes-panel" id="deck-notes" hidden></div>
<script src="{reveal}/dist/reveal.js" integrity="{sri[js]}" crossorigin="anonymous"></script><script src="{reveal}/plugin/notes/notes.js" integrity="{sri[notes]}" crossorigin="anonymous"></script>
<script>
document.querySelectorAll('.slides a[href^="http"]').forEach(a=>{{a.target='_blank';a.rel='noopener'}})
var jump=document.getElementById('deck-jump'),prev=document.getElementById('deck-prev'),next=document.getElementById('deck-next'),panel=document.getElementById('deck-notes'),btn=document.getElementById('deck-notes-btn'),
  bar=document.getElementById('deck-disclaimer'),deck=document.querySelector('.reveal')
function sync(){{var s=Reveal.getCurrentSlide();if(!s)return;var i=Reveal.getIndices().h;jump.selectedIndex=i;prev.disabled=Reveal.isFirstSlide();next.disabled=Reveal.isLastSlide();var n=s.querySelector('aside.notes');panel.innerHTML='<b>Slide '+(i+1)+' notes:</b> '+(n?n.innerHTML:'');if(!panel.hidden)fit()}}
// the slide area sits between the disclaimer (it wraps on narrow screens) and the notes panel, when open
function fit(){{deck.style.top=(56+bar.offsetHeight)+'px';deck.style.bottom=(panel.hidden?0:panel.offsetHeight)+'px';if(Reveal.isReady())Reveal.layout()}}
function toggleNotes(){{var on=panel.hidden;panel.hidden=!on;btn.setAttribute('aria-pressed',on);fit()}}
jump.addEventListener('change',()=>{{Reveal.slide(jump.selectedIndex);jump.blur()}})
btn.addEventListener('click',toggleNotes)
// after a mouse click, blur so the arrow keys page again (the keyboard is off while focus is in the nav);
// a keyboard press (detail 0) keeps focus on the button, so Enter pages again
prev.addEventListener('click',e=>{{Reveal.prev();if(e.detail)prev.blur()}})
next.addEventListener('click',e=>{{Reveal.next();if(e.detail)next.blur()}})
fit()
Reveal.initialize({{width:1920,height:1080,margin:0.03,center:false,display:'flex',hash:true,history:false,
  // scrollActivationWidth:null: phones page by swipe too, not reveal's scroll view below 435 px
  slideNumber:'c/t',scrollActivationWidth:null,controls:true,controlsLayout:'edges',controlsTutorial:false,progress:true,transition:'fade',transitionSpeed:'fast',
  keyboard:{{78:toggleNotes}},keyboardCondition:e=>!e.target.closest('.topnav'),plugins:[RevealNotes]}}).then(sync)
Reveal.on('slidechanged',sync)
addEventListener('resize',fit)
</script></body></html>
"""


def slides(folder: Path):
    for path in sorted((folder / "slides").glob("[0-9][0-9]-*.html")):
        src = path.read_text(encoding="utf-8")
        notes = re.search(r"<aside>(.*?)</aside>", src, re.DOTALL)
        yield path.stem.split("-", 1)[1], re.sub(r"\s*<aside>.*?</aside>", "", src, flags=re.DOTALL), \
            notes.group(1).strip() if notes else ""


def visible_text(section: str) -> list[str]:
    section = re.sub(r"<svg.*?</svg>", "", section, flags=re.DOTALL)
    parts = (html.unescape(p).strip() for p in re.split(r"<[^>]+>", section))
    return [p for p in parts if p]


def heading(section: str, sid: str) -> str:
    """The slide's first h1 or h2, for the jump menu."""
    found = re.search(r"<h[12][^>]*>(.*?)</h[12]>", section, re.DOTALL)
    return html.unescape(re.sub(r"<[^>]+>", "", found.group(1))).strip() if found else sid


def nav(deck: str) -> dict:
    """The top nav's links to the decks on the site, and one jump-menu entry per slide."""
    decks = "".join(f'<a class="deck{" active" if d == deck else ""}" href="{SITE}/{page}/">{name}</a>'
                    for d, (page, name) in SITE_PAGES.items())
    options = "".join(f'<option value="{sid}">{n}. {html.escape(heading(section, sid))}</option>'
                      for n, (sid, section, _) in enumerate(slides(DOCS / deck), 1))
    return {"site": SITE, "repo": REPO, "reveal": REVEAL, "sri": SRI, "decks": decks, "options": options}


def render(deck: str) -> tuple[str, str]:
    """deck.html and full_text_and_notes.md for docs/<deck>/."""
    title, note = DECKS[deck]
    links = nav(deck)
    out, md = [HEAD.format(title=title, note=html.escape(note), **links)], [
        f"# {title}: full text and notes\n",
        f"{PERSONAL} Built from `slides/` by `docs/build_decks.py`; edit the slides, then rebuild.\n"]
    for n, (sid, section, notes) in enumerate(slides(DOCS / deck), 1):
        out.append(section.replace("</section>", f'<aside class="notes">{notes}</aside>\n</section>', 1) + "\n")
        md.append(f"\n## Slide {n} — {sid}\n\n" + "\n".join(visible_text(section)) + "\n")
        if notes:
            md.append(f"\n**Speaker notes:** {html.unescape(notes)}\n")
    out.append(TAIL.format(**links))
    return "".join(out), "".join(md)


def main(decks):
    for deck in decks:
        out, md = render(deck)
        (DOCS / deck / "deck.html").write_text(out, encoding="utf-8")
        (DOCS / deck / "full_text_and_notes.md").write_text(md, encoding="utf-8")
        print(f"built docs/{deck}: deck.html, full_text_and_notes.md")


if __name__ == "__main__":
    unknown = set(sys.argv[1:]) - set(DECKS)
    if unknown:
        sys.exit(f"unknown deck {', '.join(sorted(unknown))}: choose from {', '.join(sorted(DECKS))}")
    main(sys.argv[1:] or sorted(DECKS))
