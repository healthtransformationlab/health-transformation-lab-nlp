# Synthetic dental periodontal notes and charts

Synthetic dental chart notes, each labelled with the patient's periodontal status under the 2017 AAP/EFP
classification (healthy, gingivitis, periodontitis stage I-IV, with grade and extent), plus the structured
visits they came from and a 223-note review set with its answer key. Built to practise clinical NLP,
phenotyping from dental records and OMOP modelling without touching real patients.

**Everything here is synthetic.** No patient, no PHI, no real clinic. The generator wrote fake identifiers
into the notes and a de-identification step replaced them with placeholders such as `[NAME]` and `[DATE]`.
This is a personal learning project, **not affiliated** with any employer, institution or company, and
**not for clinical use**: nothing here is evidence about real patients, products or populations.

## How it was made

[github.com/healthtransformationlab/health-transformation-lab-nlp](https://github.com/healthtransformationlab/health-transformation-lab-nlp), `python/scripts/10_build_study.py`
(seed 42, 1,200 people, 8 clinics). Each visit gets a true periodontal chart; the status follows the AAP/EFP
staging and grading worksheet (Tonetti, Greenwell & Kornman, J Periodontol 2018). The note is written from
the chart in one of several clinician styles, with realistic noise: the written diagnosis is sometimes a step
off the chart, text is copied forward from earlier visits, and older terms ("moderate chronic periodontitis")
appear. Each review note has a difficulty level (L1-L3).

## Files

- **Train:** `train.csv`. `label` is the chart truth; `stated_status` is what the clinician wrote.
- **Test:** `review_key.csv`. The 223 review notes with `truth_status`, difficulty, and what each other
  evidence source (exam form, procedure and diagnosis codes, probing chart, radiograph AI) said. Score models
  here; don't train on it.
- `visits_structured.csv` and `visits_truth.csv` are every visit's structured record and its truth, for
  phenotyping from structured data. `clinic_profiles.csv` describes the 8 synthetic clinics.
- `review_tasks.json` loads the review set into Label Studio for human chart review.

## Licence and citation

CC BY 4.0. Please cite: Bowyer J., *health-transformation-lab-nlp: synthetic dental notes, OMOP and periodontal status
benchmark*, https://github.com/healthtransformationlab/health-transformation-lab-nlp.
