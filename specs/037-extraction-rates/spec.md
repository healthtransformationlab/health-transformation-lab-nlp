# Feature Specification: extraction rates in the synthetic Open Dental extract

**Feature Branch**: `spec/610-037-extraction-rates`

**Created**: 2026-11-06

**Status**: specified

**Input**: the owner asked why the tooth-loss model (spec 029) is tested on only 14 periodontal teeth, when the
synthetic tooth loss was meant to match the general population. Answer: the extract matches published figures for
teeth already *missing* (edentulism and missing teeth at the first exam, by age; specs 029 US7 and 033 US4), but
nothing calibrated the *new* extractions recorded while a patient is in the record. Those are the model's only
labels. Measured at 6,000 patients, seed 42:

| Age | Extractions per patient-year | Share periodontal | Published share periodontal (Suzuki 2022) |
|---|---|---|---|
| 25-34 | 0.063 | 8% | 6% |
| 35-44 | 0.070 | 8% | 21% |
| 45-54 | 0.069 | 10% | 33% |
| 55-64 | 0.060 | 12% | 48% |
| 65-74 | 0.068 | 11% | 50% |
| 75+ | 0.064 | 9% | 47% |

Patients have 2.5 years of record on average. The published rate is about 0.17 extractions per adult patient per
year (Vehkalahti et al. 2023). So the extract has too few extractions, too few of them periodontal past 35, and too
little history.

> Personal learning project; synthetic data only. Every number is SYNTHETIC; a "source" is a published figure the
> synthetic value is set from or checked against, never real records. Figures from any employer's or
> organization's data are never used as targets.

## User stories

### US1 - The extraction rate follows a published rate per patient-year (P1) #610

- Completed extractions per patient-year in the record (all reasons, third molars included, patients with natural
  teeth) are 0.15-0.20 pooled over generator seeds, against about 0.17 for adults seen by a dentist (Vehkalahti,
  Ventä, Valaste, Acta Odontol Scand 2023;81(4):259-266, doi:10.1080/00016357.2022.2130977: 0.17 in 2012 and 0.18
  in 2017 per patient, Finland's national register of adults seen by private dentists).
- The rate is the same in every age band (the source's per-band figures weren't checked in full text; its abstract
  gives a U shape, lowest at 35-49, which is noted as not modelled).
- A patient-year is the span from the first to the last visit plus half a year (each recall covers six months).

### US2 - Extractions in the record are periodontal at the published share for each age (P1) #611

- In each age band, the share of completed extractions whose true reason is periodontal is within 0.07 of
  `ENTRY_PERIO_SHARE_BY_AGE` (Suzuki et al., Int Dent J 2022, Table 2; already the target for teeth missing at entry),
  pooled over generator seeds.
- Periodontal extractions fall on the teeth with the worst attachment loss of a patient with attachment loss, as the
  chart-driven ones already do, so the model still has something to learn from.
- The recorded diagnosis keeps its error rates (`dx_correct`, `dx_mismatch`, `dx_none`).

### US3 - Patients have up to ten years of record, none after 2025 (P2) #612

- 2 to 20 recall visits six months apart (up to ten years), every visit on or before 2025-12-31: a patient whose
  visits would run later has fewer.
- No published figure for how long patients stay in a practice's records was found (a survey of NHS patients in
  England and Wales, Burke and Lucarotti 2015, gives no usable figure in what could be read), so this is a stated
  choice, labelled "placeholder" in the data card (`docs/synthetic_data.md`).
- The mean years of record is reported beside the rate.

## Out of scope

- The study visits and benchmark notes (`synthetic.py`, `notes.py`): unchanged.
- The tooth-loss model and its analysis plan: unchanged, except that every synthetic result is rerun on the new
  extract and the change is recorded in the analysis plan's change log.
- Teeth missing at entry and edentulism: their targets are unchanged and their tests must still pass.

## Success criteria

- `python/tests/test_open_dental.py` checks US1-US3 on generated extracts and passes.
- At the default 60,000 patients (#609), the held-out set has several hundred periodontal extractions.
- `docs/synthetic_data.md`, `docs/references.md`, `docs/tooth_loss.md` and the study page give the new figures,
  labelled SYNTHETIC.
