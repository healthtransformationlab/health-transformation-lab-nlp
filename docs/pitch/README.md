# Health Transformation Lab: a Shark Tank pitch

> **A personal idea**, written on my own time like the rest of this repo. Not affiliated with or endorsed by any
> employer, institution or company, and not any organization's plan ([DISCLAIMER.md](../../DISCLAIMER.md)). No
> partner named here has been contacted or has agreed to anything.
> Figures come from the public sources cited on each slide; nothing marked "to measure" has been measured.

**The pitch in one line:** AI passes the dental exam and fails the real patient: most benchmarks test exam knowledge,
and published studies have found AI falling short on real patient cases such as drug interactions. An open lab writes
the missing real-world test questions, publishes an open agent built on public evidence, and measures the gain in
public, for better oral health for millions of Americans and better overall health through medical-dental care.

| File | What it is |
|---|---|
| [deck.html](deck.html) | The 24 slides with speaker notes (open in a browser) |
| [full_text_and_notes.md](full_text_and_notes.md) | Every slide's text and notes, for reading or search |
| [slides/](slides/) | The source: one `<section>` per slide, notes in its `<aside>` |
| [../build_decks.py](../build_decks.py) | Rebuilds the two files above from `slides/`: `python docs/build_decks.py pitch` |

Slides 1–6 are the pitch; 7–24 are backup for questions.

## How this repo tests the idea

The pitch asks for a fair test, and this repo is where one gets built on synthetic data:

- **The medical-dental seam, from the record:** the periodontal phenotyping study ([the dental record path](../edr/README.md)) reads a dental chart the
  way a doctor or an AI would have to, with harm grades borrowed from GlobalDentBench
  ([dentbench_methods.md](../dentbench_methods.md)) and the record in OMOP, the format medicine already uses.
- **Large LLMs, from narrow to broad:** the same models, harm grades and leaderboards score LLMs first on
  periodontal charts, then on case questions written from synthetic patients whose right answers are known, then on
  broader dental and medical-dental questions.

## Sources cited in the deck

- GlobalDentBench: Zhao, Liang, Cai et al., [arXiv 2605.24636](https://arxiv.org/abs/2605.24636), 2026
- First, Do NOHARM (ARISE network), 2026 preprint
- Hager et al., *Evaluation and mitigation of the limitations of large language models in clinical decision-making*,
  Nat Med 2024, [doi:10.1038/s41591-024-03097-1](https://doi.org/10.1038/s41591-024-03097-1)
- Bean et al., *Reliability of LLMs as medical assistants for the general public*, Nat Med 2026,
  [doi:10.1038/s41591-025-04074-y](https://doi.org/10.1038/s41591-025-04074-y)
- Al-Ashwal et al., ChatGPT, Bing AI and Bard against drug-drug interaction tools, Drug Healthc Patient Saf 2023,
  [doi:10.2147/DHPS.S425858](https://doi.org/10.2147/DHPS.S425858)
- Kaplan and Akyol, systematic review of AI evaluation in dentistry, Japanese Dental Science Review 2026,
  [doi:10.1016/j.jdsr.2026.01.002](https://doi.org/10.1016/j.jdsr.2026.01.002)
- CDC, NCHS Data Brief 531, *Emergency Department Visits for Tooth Disorders: United States, 2020–2022* (June 2025),
  [cdc.gov](https://www.cdc.gov/nchs/products/databriefs/db531.htm)
- Sanz et al., *Scientific evidence on the links between periodontal diseases and diabetes*, EFP and IDF consensus
  report, J Clin Periodontol 2018, [doi:10.1111/jcpe.12808](https://doi.org/10.1111/jcpe.12808)
- OpenAI (January 2026) and Google (July 2026) on health questions and assistant users; HealthBench leaderboard on
  benchmarklist.com (September 29, 2026); Google Health AI Developer Foundations, MedGemma (January 13, 2026)
- Public benchmarks on the "tests" slide: arXiv 2603.08281, 2505.06046, 2511.04705, 2406.06056, 2403.12025
- REDCap (Vanderbilt CTTC), OHDSI, healthtalk.org
