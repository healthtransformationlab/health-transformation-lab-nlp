# PerioDx: the method of Patel et al. 2022 (spec 024)

Patel JS, Brandon R, Tellez M, Albandar JM, Rao R, Krois J, Wu H. *Developing automated computer algorithms to
phenotype periodontal disease diagnoses in electronic dental records.* Methods Inf Med 2022;61(S2):e125–e133,
doi:[10.1055/s-0042-1757880](https://doi.org/10.1055/s-0042-1757880), CC BY-NC-ND 4.0
([references](references.md), item 4).

> Personal learning project; synthetic data only (`DISCLAIMER.md`). The paper's data is real dental records from
> one dental school, used under its IRB; it is not public and never comes into this repo. Everything below runs on
> this repo's synthetic charts. Nothing here is a replication of the paper.

The paper finds gum disease in dental records (phenotyping) from three sections, in order: the structured
diagnosis a dentist recorded (M1), its keyword program on the clinical notes (the **PerioDx Extractor**, M2), and
its rule tree on the periodontal chart (the **PerioDx Diagnoser**, M3). Those two names are the paper's own; here
both only identify a status in a synthetic record. Code: `python/health_transformation_lab_nlp/periodx.py`; base-R
twin: `r/R/14_spec024.R`, checked by `r/tests/test_parity.R`.

## The PerioDx Diagnoser: the chart (Fig. 2), `periodx.chart_status`

Fig. 2 as drawn, top to bottom. Every threshold is a named constant citing "Patel et al. 2022, Fig. 2".

1. **Entry.** Detectable marginal bone loss? Interproximal CAL > 2 mm at 2+ non-adjacent teeth? Buccal or lingual
   recession with CAL > 2 mm and PD > 3 mm at 2+ teeth?
   - No to all three: BOP < 10% periodontal health, 10–30% localized gingivitis, > 30% generalized gingivitis.
   - Yes to any, and no PD ≥ 4 mm: BOP < 10% reduced but healthy periodontium, ≥ 10% gingival inflammation /
     past periodontitis.
   - Yes to any, and a PD ≥ 4 mm: periodontitis.
2. **Stage.** Stage III/IV criteria in the figure's order: bone loss > 33%; CAL ≥ 5 mm at 2+ adjacent teeth;
   furcation class II/III or vertical bone loss ≥ 3 mm; PD > 5 mm at 2+ adjacent teeth. With one, fewer than 10
   occluding pairs, mobility degree ≥ 2 at 5+ teeth, or drifting, bite collapse, flaring or a severe ridge defect
   gives stage IV. Every other path goes through tooth loss: 1–4 teeth lost to periodontitis stage III, 5 or more
   stage IV, none the bone-loss box (BL < 15%, PD 4 mm, CAL 1–2 mm stage I; BL 15–33%, PD 5 mm, CAL 3–4 mm stage II).
3. **Extent.** The share of teeth lost to periodontitis or involved at the case's stage (III/IV: CAL ≥ 5 and PD ≥ 4,
   or CAL 3–4 and PD ≥ 6; II: CAL 3–4 and PD 4–5, or CAL 1–2 and PD ≥ 5; I: CAL 1–2 and PD 4): under 30%
   localized, 30% or more generalized, or a molar/incisor pattern.
4. **Grade.** % bone loss / age: under 0.25, a current smoker goes to "≥ 10 a day" (yes C, no HbA1c), a non-smoker
   with diabetes to "HbA1c ≥ 7.0" (yes C, no B), anyone else A; 0.25 to 1.0 enters at "≥ 10 a day", so C or B,
   never A; over 1.0, C.

### Where the figure leaves a step open (spec 024's readings)

| Parameter | Reading | Why |
|---|---|---|
| `III_IV_NO_TOOTH_LOSS` | stage III | A III/IV case with no complexity factor and no tooth lost reaches the bone-loss box, which has no branch for BL > 33%. The criteria placed it at III or IV and nothing pointed to IV. |
| `STAGE_I_II_HIGHER` | the higher stage | A chart meeting stage I and stage II measures at once goes to stage II; so does a measure beyond the stage II band that wasn't at 2+ adjacent teeth (a single 6 mm pocket). |
| `GRADE_MID_ENTRY` | "≥ 10 a day" | The arrow from 0.25–1.0 enters there, so that band gives C or B, never A. |
| bands | contiguous | "CAL 1–2 mm" is 1 ≤ CAL < 3, "3–4 mm" is 3 ≤ CAL < 5, "PD 4 mm" is 4 ≤ PD < 5. |
| `DETECTABLE_BL_PCT` | any loss > 0% | The figure asks only whether bone loss is detectable. |
| bone-loss categories | accepted | The paper's form records < 15%, 15–33%, > 33%. A category grades only when its whole range falls in one ratio band; otherwise the grade is not assessable. |
| grade without age or bone loss | not assessable | Not a default B, unlike `labels.grade_of`: the figure has no default. |

A missing input uses a documented fallback (not charted means absent; occluding pairs not counted means 10 or more;
no HbA1c in the HbA1c box means no), and the finding lists every fallback it used (`partial`), so a visit decided on
partial data can be counted.

### The repo's summary chart as the figure's inputs (`periodx.chart_from_summary`)

The synthetic chart is a summary: worst-site PD, CAL and bone loss, BOP, teeth lost to periodontitis, and the share
of teeth with attachment loss. Fig. 2 asks about teeth. This repo's reading, not the paper's:

- the teeth with attachment loss are round(share × teeth present), with 28 teeth (third molars left out) less those
  lost;
- a worst-site measure past a threshold is taken to hold at all of those teeth, adjacent or not as the test needs;
- recession, furcation, vertical defects, occluding pairs, mobility and complexity factors aren't in the summary, so
  their fallback applies and the finding says so;
- the extent share is (teeth with attachment loss + teeth lost) / 28.

### In the six labels the benchmark scores

| Fig. 2 box | Label |
|---|---|
| periodontal health; reduced but healthy periodontium | healthy |
| localized or generalized gingivitis; gingival inflammation / past periodontitis | gingivitis |
| periodontitis, stage I–IV | periodontitis stage 1–4 |

A reduced periodontium, healthy or inflamed, is periodontal health or gingivitis on a reduced periodontium in the
2017 classification (Chapple et al. 2018).

## The PerioDx Extractor: the note, `periodx.note_status`

The paper describes a two-step keyword program, and this follows it:

1. **Normalize and filter.** Lowercase the note, keep abbreviation dots with their word ("st. 2"), split it into
   clauses, turn special characters into spaces and drop stop words. A note counts only if it mentions a
   periodontal diagnosis term from the word list.
2. **Read extent, stage and grade.** Stemming (a small suffix stripper) and string similarity (difflib ratio
   ≥ 0.85 for words of 5+ letters, exact for shorter ones) match words against the same list, so typos like
   "generalzied" still count. A stage needs a stage word ("stage", "st", "perio") followed by a numeral (I–IV or
   1–4, with an optional grade letter: "Perio IIIB"). A grade needs a grade word ("grade", "gr") followed by A–C
   or i–iii. A pre-2017 severity word counts only when "periodontitis" follows within three words
   ("moderate chronic periodontitis": slight or mild = I, moderate = II, severe or advanced = III).

The result is the most specific status the words support, or **no diagnosis** (never "healthy" by default). A
stage, grade or severity term implies periodontitis. When a note holds several, the most severe wins: status
first, then stage, grade and extent each at their worst. Copied-forward text ("-- copied from visit") is left out
by default (`multiple="most_severe_current"`, the spec's edge case). `multiple="most_severe"` reads it too.

**The word list** (`PERIODX_TERMS`, FR-003) names a source for every term:

- the 2017 classification (periodontitis, gingivitis, periodontal or gingival health, generalized, localized,
  molar/incisor, stage, grade);
- the 1999 classification (the severity words);
- the paper's own error analysis ("bone loss", which its missed-negation example shows the program reading);
- the repo's synthetic note templates ("ging", "perio health", "perio WNL", "gen", "loc", "st", "gr", "perio" as
  a stage word).

It is built from those sources and the templates, never from real notes. "Perio" on its own ("perio charting
done") is not a diagnosis. AAP case types are not in the list, since the paper's bag has none.

**Negation** is off by default, as published: "no evidence of bone loss, gingivitis localized" reads as
periodontitis with no stage. With `negation=True`, a minimal NegEx-style cue list (no, not, without, denies,
negative, absent, absence, free) negates the next five words of its clause, and the same note reads as localized
gingivitis. Both versions can be scored.

**What differs from the paper:** it used gensim word vectors for similarity. The difflib ratio stands in, so the
method needs no new dependency.

**In the six labels:** health is healthy; gingivitis of any extent is gingivitis; periodontitis with a stage is
that stage. Periodontitis with no stage, and no diagnosis, give no status.

## The stepwise phenotype: `algorithm_patel2022`

`phenotype.phenotype_patel2022` gives each visit the first available of three sections:

- **M1:** the diagnosis codes, done then planned. These stand in for the paper's structured diagnosis section;
  planned after done is this repo's choice, as in `algorithm_design`.
- **M2:** the Extractor on the chart note.
- **M3:** the Diagnoser on the gum measurements.

A section is "available" when it gives one of the six statuses. There is no exam form, since the paper has none.
The paper's order is its own constant (`PATEL2022_ORDER`), not one of the four design groups:
`scripts/18_phenotype_order.py` keeps its 24 orderings and scores this one as an extra row that is never
selected.

**Outputs:**
- `data/datasets/periodx_visits.csv`: every visit's Extractor and Diagnoser readings, the phenotype and its
  deciding section. Statuses only, no note text. It is written by `10_build_study.py` next to the study data, so
  every existing dataset stays byte-identical (FR-010).
- `scripts/52_patel2022.py` writes completeness per section (`data_quality/completeness_patel2022.csv`) and the
  confusion scores (`periodx/confusion_scores.csv`).
- The method also appears in the leaderboard ([results.md](results.md)), the reliability scripts, the DQ
  grader's `fact_visit_evidence` (`rules_patel2022_status_code`) and its dashboard.

## Results beside the paper's own figures

The left column is this repo's code on **synthetic** charts, scored against the generator's truth: an exercise,
not clinical performance. The right column is the paper's own published figures, on **real records, one dental
school**, cited by figure or table. They come from a different population, with different definitions, and are
never computed here. Nothing on this page is a replication.

| Measure | This repo: synthetic, 240 review charts | Patel et al. 2022: real records, one dental school |
|---|---|---|
| Section has a status (M1 / M2 / M3) | 69.6% / 75.4% / 81.2% | 36% / 18% / 80% as the text gives them (Fig. 1 swaps the first two) |
| Merged phenotype has a status | 98.8% | 100% (Fig. 1) |
| Visits decided by M1 / M2 / M3 | 69.6% / 23.3% / 5.8% | not reported in this form |
| Diagnoser F1 | 0.56 pooled over six statuses, against the generator's truth | 97% against two experts on 200 charts (text) |
| Extractor F1 | 0.66 pooled over six statuses | 95% as stated; its own 91% precision and 87% recall give 0.89 (text; Table 1) |
| Phenotype, correct status | 67.5 per 100 charts (95% CI 61.3–73.3) | not validated against experts in the paper |

On all 4,343 synthetic visits, the sections have a status on 70.5% / 73.6% / 79.1% of visits, and the merged
phenotype on 98.2%.

**What the synthetic numbers show (and don't):**
- The Diagnoser finds almost no stage I (recall 0.02). The generator's stage I charts have pockets under 4 mm,
  and Fig. 2 calls a chart periodontitis only with a PD ≥ 4 mm, so those charts land in "reduced periodontium"
  (healthy or gingivitis). That is the figure working as drawn on charts drawn from the AAP worksheet, not a bug.
- Of the 59 review notes with no status from the Extractor, 53 read as periodontitis with no stage. All of them
  mention "bone loss" and name no stage the word list can read. Periodontitis with no stage has no status, so
  the phenotype goes on to the chart. Turning negation on
  makes no difference on these notes.
- The diagnosis codes decide 70% of visits and are right on 65% of those. The note decides 23% (79% right) and the
  chart 6% (71% right). So the codes, more than either PerioDx reader, set the phenotype's score.

**The paper's own inconsistencies,** recorded and not resolved by guessing ([references](references.md), item 4):
- Fig. 1 attaches the text's 36% and 18% to the other section.
- The Extractor's stated F1 (95%) doesn't follow from its precision and recall.
- Table 1 gives 112 actual positives but 224 true positives with 0 false negatives, and a prevalence of 0.59
  where 224/400 = 0.56.
- The HbA1c bands on Fig. 2 leave 5.0–5.7 unassigned.
