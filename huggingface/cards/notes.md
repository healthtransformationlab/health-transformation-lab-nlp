# PerioBench notes: synthetic dental notes labelled with periodontal status

3,016 synthetic dental chart notes to train on and 223 to test on, each labelled with the patient's periodontal
status under the 2017 AAP/EFP classification: healthy, gingivitis, or periodontitis stage I to IV, with grade
and extent. Built to practise clinical NLP and phenotyping from dental records without touching real patients.
Part of [PerioBench](https://healthtransformationlab.org) from the Health Transformation Lab.

## Quick start

```python
from datasets import load_dataset

notes = load_dataset("healthtransformationlab/perio-bench-notes")   # train: 3,016 notes, test: 223
print(notes["train"][0]["note_text"], "->", notes["train"][0]["label"])
```

Or with pandas only:

```python
import pandas as pd

train = pd.read_csv("hf://datasets/healthtransformationlab/perio-bench-notes/data/train.csv")
test = pd.read_csv("hf://datasets/healthtransformationlab/perio-bench-notes/data/test.csv")
```

**Try it in your browser:** [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/healthtransformationlab/health-transformation-lab-nlp/blob/main/notebooks/perio_bench_quickstart.ipynb)
The quickstart notebook (also in this repository) trains a simple baseline in about a minute and scores it on
the test notes beside the published leaderboard. The same data and notebook are on Kaggle:
[kaggle.com/datasets/jcblearning/perio-bench-notes](https://www.kaggle.com/datasets/jcblearning/perio-bench-notes).

## What's inside

| Config | What it is |
|---|---|
| `notes` (default) | `train` and `test` splits: the note, its `label` (healthy, gingivitis, periodontitis_stage_1 to 4), `grade`, `extent`, what the clinician wrote (`stated_status`), and the X-ray bone-loss reading |
| `review_key` | The 223 test notes with every other part of the record: exam form, procedure and diagnosis codes, probing chart, what each says, and a difficulty level (L1 to L3) |
| `visits`, `visits_truth` | Every visit's structured record and its true status, for phenotyping from structured data |
| `clinics` | The 8 synthetic clinics |

Score on `test`; don't train on it. The `raw/` folder holds the original files, as on Kaggle.

**Everything here is synthetic.** No patient, no PHI, no real clinic. The generator wrote fake identifiers into
the notes and a de-identification step replaced them with placeholders such as `[NAME]` and `[DATE]`. This is a
personal learning project, **not affiliated** with any employer, institution or company, and
**not for clinical use**: nothing here is evidence about real patients, products or populations.

## How it was made

[github.com/healthtransformationlab/health-transformation-lab-nlp](https://github.com/healthtransformationlab/health-transformation-lab-nlp),
`python/scripts/10_build_study.py` (seed 42, 1,200 people, 8 clinics). Each visit gets a true periodontal chart;
the status follows the AAP/EFP staging and grading worksheet (Tonetti, Greenwell & Kornman, *J Periodontol* 2018).
The note is written from the chart in one of several clinician styles, with realistic noise: the written
diagnosis is sometimes a step off the chart, text is copied forward from earlier visits, and older terms
("moderate chronic periodontitis") appear.

## Licence and citation

CC BY 4.0. Please cite: Bowyer J., *health-transformation-lab-nlp: synthetic dental notes, OMOP and periodontal
status benchmark*, https://github.com/healthtransformationlab/health-transformation-lab-nlp.
