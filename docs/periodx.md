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
