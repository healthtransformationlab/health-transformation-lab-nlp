# How each evidence type is turned into a status

Every method in the results answers one question per chart: **healthy, gingivitis, or periodontitis
stage 1–4?** The truth comes from the gum measurements, scored with the AAP 2017 worksheet
([staging_grading.md](staging_grading.md)). Each other part of the record is read by its own rule,
written down here. A rule that can't tell gives **no answer**, never a guess.

The worked examples are checked against the code by `python/tests/test_evidence_rules_doc.py`, so
this page and the code can't drift apart. All examples are synthetic.

Where each rule comes from (published or designed here) and how each scores: [algorithms.md](algorithms.md).
The definitions (2017 AAP/EFP, 2012 CDC/AAP, ACES), sources and orders side by side, and where they disagree:
[standards.md](standards.md).

| Evidence type (README name) | What it is | Best it can do | Code |
|---|---|---|---|
| Gum measurements (probing chart) | Pocket depths, attachment loss, bleeding, teeth lost | All six statuses: it *defines* them | `labels.label_chart` |
| Chart note | The clinician's free text | All six, if a diagnosis or findings are written | `note_reader.read_note` |
| Exam form | PSR screening score and a perio-status checkbox | Healthy, gingivitis, stage 2, stage 3 (stage 1 and 4 only from the checkbox) | `sources.read_exam_form` |
| Diagnosis codes (planned or done treatment) | ICD-10-CM code on the procedure | Healthy, gingivitis, stage 1–3 (never 4) | `sources.read_proc_dx` |
| Procedure codes (planned or done) | CDT treatment codes | A rough guess: healthy, gingivitis, stage 1–3 | `sources.read_proc_codes` |
| X-ray AI reading | Bone loss measured on the radiograph | Stage 2 or 3 only (a lower bound) | `radiograph.read_radiograph` |

## Gum measurements (probing chart)

The measured evidence the 2017 definitions are written against, so it is the reference for the
synthetic truth. Full rules: [staging_grading.md](staging_grading.md). In short:

1. **No attachment loss** (worst interdental CAL under 1 mm) and no tooth lost to gum disease:
   **gingivitis** if bleeding on probing is at 10% of sites or more, else **healthy**.
2. Otherwise **periodontitis**. Stage from the worst CAL: 1–2 mm **stage 1**, 3–4 mm **stage 2**,
   5 mm or more **stage 3**. (Bone loss on the X-ray is used only when CAL isn't charted.)
3. Teeth lost to gum disease raise it: 1–4 teeth at least **stage 3**, 5 or more **stage 4**.
4. Complications raise it, never lower it: pocket deeper than 4 mm at least **stage 2**; 6 mm or
   more, a vertical bone defect of 3 mm or more, or furcation class II/III at least **stage 3**;
   at stage 3, loose teeth (mobility 2+), fewer than 20 teeth or a bite needing rebuilding make it
   **stage 4**.

**No answer** when the chart wasn't taken at that visit.

| Evidence | Input | Status |
|---|---|---|
| Gum measurements | `CAL 0 mm, BOP 5%` | `healthy` |
| Gum measurements | `CAL 0 mm, BOP 20%` | `gingivitis` |
| Gum measurements | `CAL 2 mm, PD 4 mm, BOP 30%` | `periodontitis_stage_1` |
| Gum measurements | `CAL 4 mm, PD 5 mm, BOP 30%` | `periodontitis_stage_2` |
| Gum measurements | `CAL 6 mm, PD 7 mm, BOP 40%` | `periodontitis_stage_3` |
| Gum measurements | `CAL 6 mm, PD 7 mm, BOP 40%, teeth lost 5` | `periodontitis_stage_4` |

## Chart note (keyword rules)

Text copied forward from an earlier visit is ignored. Then, in order:

1. **A written diagnosis**, in any scheme clinicians use:
   - "periodontal health", "periodontium WNL" and similar: **healthy**.
   - "gingivitis" with no mention of periodontitis: **gingivitis**.
   - A 2017 stage ("stage III", "st. 2", "perio IV") next to "perio"/"periodontitis" or a grade:
     that **stage**, as written.
   - Pre-2017 severity: slight or mild **stage 1**, moderate **stage 2**, severe or advanced
     **stage 3**, raised to **stage 4** if the note records 5 or more teeth lost.
   - AAP case type: I **gingivitis**, II **stage 1**, III **stage 2**, IV **stage 3** (stage 4 on
     5+ teeth lost).
2. **No diagnosis written: the findings** in the note go through the gum-measurement rules above:
   bleeding ("BOP 30%", or "heavy"/"generalized"/"localized" BOP as 45/25/12%), attachment loss
   ("CAL up to 5", or severe/moderate/slight as 6/3.5/1.5 mm), bone loss ("~30%", or by third of
   the root) and teeth lost. Pocket depths aren't read: notes list sites, not the worst one.
3. **Nothing measurable written**: read as no loss, so **healthy** or **gingivitis** by bleeding.

| Evidence | Input | Status |
|---|---|---|
| Chart note | `Periodontium WNL. Recall 6 months.` | `healthy` |
| Chart note | `Plaque-induced gingivitis, BOP 30%.` | `gingivitis` |
| Chart note | `Dx: generalized periodontitis stage III grade B` | `periodontitis_stage_3` |
| Chart note | `Moderate chronic periodontitis, SRP planned.` | `periodontitis_stage_2` |
| Chart note | `BOP 20%, CAL up to 4 mm.` | `periodontitis_stage_2` |

## Exam form

Two fields: the **perio-status checkbox** (used first, if ticked) and the **PSR screening score**
(the worst of six sextants, 0–4).

- Checkbox: "WNL" **healthy**; otherwise the status ticked.
- PSR when the checkbox is empty: 0 **healthy**; 1–2 **gingivitis** (bleeding or calculus, no
  pocket over 3.5 mm); 3 **stage 2** (pockets 3.5–5.5 mm); 4 **stage 3** (pockets over 5.5 mm).
  PSR can't show stage 1 or stage 4.
- **No answer** when no form was filled in.

| Evidence | Input | Status |
|---|---|---|
| Exam form | `PSR max 1; perio status: WNL` | `healthy` |
| Exam form | `PSR max 2` | `gingivitis` |
| Exam form | `PSR max 3; perio status: periodontitis stage 2` | `periodontitis_stage_2` |
| Exam form | `PSR max 4` | `periodontitis_stage_3` |

## Diagnosis codes, planned treatment / Diagnosis codes, done treatment

The ICD-10-CM code attached to the planned or the completed procedure. Same rule for both; they
differ because patients decline treatment (a declined SRP leaves a gingivitis code on the done
side).

- Z01.20 (exam, no abnormal findings): **healthy**.
- K05.0x, K05.1x (gingivitis): **gingivitis**.
- K05.3*xy* (chronic periodontitis; *x* is localized/generalized, *y* severity): slight
  **stage 1**, moderate **stage 2**, severe **stage 3**. The codes have no stage 4.
- **No answer** when the practice doesn't attach diagnosis codes, or for any other code.

| Evidence | Input | Status |
|---|---|---|
| Diagnosis codes | `Z01.20` | `healthy` |
| Diagnosis codes | `K05.10` | `gingivitis` |
| Diagnosis codes | `K05.311` | `periodontitis_stage_1` |
| Diagnosis codes | `K05.322` | `periodontitis_stage_2` |
| Diagnosis codes | `K05.323` | `periodontitis_stage_3` |

## Procedure codes, planned / Procedure codes, done

CDT treatment codes say what was done, not what the patient has, so this is a rough guess. Same
rule for planned and done; done lags planned when patients decline.

- Bone surgery (D4260/D4261), or an extraction (D7140) with scaling and root planing:
  **stage 3** (at least).
- Scaling and root planing, 4+ teeth (D4341): **stage 2** (it covers stage 2–4; 2 is the most
  common).
- Scaling and root planing, 1–3 teeth (D4342): **stage 1**.
- Scaling for gum inflammation (D4346): **gingivitis**.
- A routine cleaning (D1110) with no full perio exam: **healthy** (it can't separate healthy
  from gingivitis; healthy is more common).
- A full perio exam (D0180) and only a routine cleaning: **no answer** (evaluated, treatment not
  done yet).

| Evidence | Input | Status |
|---|---|---|
| Procedure codes | `D0120 D1110` | `healthy` |
| Procedure codes | `D0120 D4346` | `gingivitis` |
| Procedure codes | `D0180 D4342` | `periodontitis_stage_1` |
| Procedure codes | `D0180 D4341` | `periodontitis_stage_2` |
| Procedure codes | `D0180 D4341 D4260` | `periodontitis_stage_3` |
| Procedure codes | `D0180 D1110` | `unknown` |

## X-ray AI reading

Bone loss as a share of root length (RBL), measured on the radiograph. Bone loss alone sets a
minimum stage, not the stage, so:

- Needs 15% bone loss or more on **at least two teeth** (one noisy tooth can't call disease).
- Worst bone loss up to 33%: **stage 2**; over 33%: **stage 3**.
- Never stage 1 (under 15% is within measurement error) or stage 4 (the image doesn't show why
  teeth are missing).
- **No answer** when there's no usable image, or no bone loss: healthy and gingivitis look the
  same on an X-ray.

| Evidence | Input | Status |
|---|---|---|
| X-ray AI | `max bone loss 25%, 3 teeth at 15% or more` | `periodontitis_stage_2` |
| X-ray AI | `max bone loss 40%, 2 teeth at 15% or more` | `periodontitis_stage_3` |
| X-ray AI | `max bone loss 20%, 1 tooth at 15% or more` | `unknown` |

## Combined rules on the whole record

Each takes the first part of the record, in a fixed order, that gives an answer
(`phenotype.phenotype_v0`).

### Rules, gum measurements first (`algorithm_v0`)

Order: gum measurements → chart note → diagnosis codes (done, then planned) → exam form →
procedure codes (done, then planned). When the gum measurements didn't decide, the X-ray AI is a
floor: if it shows a higher stage than the deciding part, its stage is used. This order is this repo's own
placeholder (spec 003), not taken from a published algorithm.

### Rules, exam form first (`algorithm_design`)

The study design's starting order (spec 005): exam form → diagnosis codes (done, then planned) → chart note →
gum measurements. This order is this repo's own. It is not the order in Patel et al., *Methods Inf Med* 2022
([references](references.md), item 4), checked against the full text
([action item A2](action_items.md); #389, #204): the paper uses three sources, the structured diagnosis section (the clinician's recorded
diagnosis), then clinical notes, then periodontal charting, each only filling gaps. It has no exam-form or
PSR step, no diagnosis codes attached to done or planned procedures, and it never validated the order against
expert review. The paper's own order is `algorithm_patel2022` (spec 024, below). No X-ray floor. It scores lower
(72 vs 98 correct per 100 charts): about 85% of visits have an exam form, so the form decides most charts,
and its checkbox is often stale.

### Rules, Patel et al. 2022 order (`algorithm_patel2022`)

The paper's own order, run with the paper's own readers (spec 024; details and every reading in
[periodx.md](periodx.md)):

1. Diagnosis codes, done then planned. These stand in for the paper's structured diagnosis section, which is
   this repo's choice.
2. The PerioDx Extractor's keyword reading of the chart note.
3. The PerioDx Diagnoser's Fig. 2 rules on the gum measurements.

The first that gives one of the six statuses decides. There is no exam form and no X-ray floor. The note and chart
readers are the paper's, not this repo's `notes` and `probing_chart` readers, so the outcome can differ from
`algorithm_design` even where the order agrees. The per-visit readings are in `data/datasets/periodx_visits.csv`.

## Stage 4 rule (`+rules4`)

Trained models saw few stage 4 notes, so they rarely say it. In the "+ stage 4 rule" methods, when
the chart-note keyword rules say **stage 4**, that replaces the model's answer; every other answer
is the model's (`ladder_eval.rules_override`).

## Where the noise comes from in the synthetic data

`sources.generate_sources` makes each part of the record from the true status with the kinds of
error real dental records have: forms copied forward (the checkbox is one step off, toward
"moderate", a quarter of the time; the PSR score one point off 15% of the time), diagnosis codes
one step off toward moderate 20% of the time, treatment declined (a fifth of periodontitis
patients, so done codes differ from planned), and parts of the record missing (no exam form on
about 15% of visits, no diagnosis codes on about 30%). That is why the rules above, applied faithfully,
still disagree with the truth.
