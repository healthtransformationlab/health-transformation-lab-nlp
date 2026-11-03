# Synthetic data card: every generator parameter and where it comes from (spec 033)

> **Every number made with these parameters is SYNTHETIC.** A "source" is a published figure a synthetic value is
> set from or checked against, never real records. Personal learning project; see [DISCLAIMER.md](../DISCLAIMER.md).

The repo has three generators. Each table below lists one generator's parameters: the value in the code today, what
it means, its source or the word **placeholder**, the published figure it should match where one exists, and whether
the repo checks it. A source is an item of [references.md](references.md), checked against its full text (or, where
the item says so, its abstract) before it was cited, or the citation the generator's own code carries. A placeholder
is a value the repo chose: plausible, not an estimate of any population. `tests/test_synthetic_data_card.py` fails
when a parameter declared in `open_dental.Params`, a keyword argument of `synthetic.draw_risk`, or one of the
module constants it names is missing here, has neither a source nor "placeholder", or shows a value the code no
longer holds.

What this card answers (spec 033):

- **Sourced and checked**: the medical-record conditions and their links to periodontitis, the reasons teeth are
  missing at entry, and the effects of smoking and diabetes on tooth loss for other reasons.
- **Placeholders**: the periodontitis mix (shaped on NHANES, not calibrated to it), progression and treatment, and
  every record-mess rate. Calibrating the periodontitis mix is a later spec; the mess rates wait for a real
  extract's `realism_profile` (spec 033, "Out of scope").
- **Set from published US figures in the Open Dental extract since spec 033 US2**: smoking (11.6% of US adults in
  2022, item 72) and diabetes (15.8% of US adults 20 and over, HbA1c >= 6.5, item 73). The study's notes keep the
  older placeholders (18% smoke, 8.5% have diabetes) until they are rebuilt (US3).
- **Set from published US figures in the Open Dental extract since spec 033 US4**: complete tooth loss by age band
  (items 79 and 80, and this repo's NHANES 2009-2014 run), and, as an option off by default, state rates (item 81).
- **Still a placeholder**: insurance (the dental-coverage source could not be checked from this environment).

## Study visits (`synthetic.py`, `study.py`)

The benchmark notes, the chart-review set and the answer key (`scripts/10_build_study.py`, seed 42, 1,200 people).
External model runs were scored on these exact notes, so their values stay until the notes are rebuilt (spec 033
US3, #486, with #467).

| Parameter | Value | What it means | Source | Published figure | Checked by |
|---|---|---|---|---|---|
| `synthetic._SEVERITY_WEIGHTS` | healthy 0.3, gingivitis 0.28, mild 0.18, moderate 0.15, severe 0.07, advanced 0.02 | the latent severity mix a chart is drawn from (before the age shift and the clinic's case mix) | placeholder, shaped on NHANES 2009-2014 (item 35) | 42.2% of US adults 30+ with periodontitis, 7.8% severe, CDC/AAP definitions (item 35); under the 2017 classification (ACES), stage I 17.9%, II 46.2%, III 16.7%, IV 12.4% of dentate adults 30+ (Tay et al. 2025, cited in `data/datasets/nhanes/nhanes_published.csv`) | `scripts/19_prevalence.py` writes `data/datasets/prevalence/vs_published.csv`: truth 53.2% with periodontitis and 13.0% stage III-IV against 42.2% and 7.8%. Off, and not comparable one to one ('severe' is not stage III-IV) |
| (age shift in `draw_chart`) | at 50 and over: healthy -0.10, moderate +0.06, severe +0.04 | older people draw more disease | placeholder | prevalence rises with age (item 35) | no |
| `synthetic.BASE_CAL_MM_PER_YEAR` | 0.05 to 0.25 mm a year, uniform | how fast a periodontitis patient's worst attachment loss grows, before risk factors | placeholder | 0.05 mm a year mean whole-mouth loss in a well-maintained cohort, 0.08-0.1 before 35 (item 74); 0.05-0.5 mm a year with moderate and 0.1-1.0 with rapid progression, no care (item 75). The range sits inside the moderate one | no |
| `synthetic.SMOKER_EXTRA` | light 0.1, heavy 0.3 mm a year | added to the rate for under 10 / 10 or more cigarettes a day | placeholder | none checked | no |
| `synthetic.DIABETES_EXTRA` | controlled 0.1, uncontrolled 0.3 mm a year | added to the rate at HbA1c 6.5-6.9 / 7.0 or more | placeholder | none checked | no |
| `synthetic.ONSET_PER_VISIT` | 0.03 | a healthy or gingivitis patient develops early periodontitis at a visit | placeholder | none checked | no |
| (gingivitis flips in `draw_history`) | healthy to gingivitis 0.15, back 0.30 a visit | bleeding comes and goes | placeholder | none | no |
| (teeth lost in `draw_history`) | 0.05 a visit once CAL >= 6 mm | a tooth lost to periodontitis | placeholder | none | no |
| `synthetic.TREAT_PROB` | 0.6 | a periodontitis visit leads to scaling and root planing | placeholder | about half (927 of 1,866, 49.7%) of dental-school patients with generalized moderate periodontitis had scaling and root planing billed within two years (item 78, Table 3) | no |
| `synthetic.TREATED_RATE_FACTOR` | 0.4 | progression after therapy, as a share of the untreated rate | placeholder | none checked | no |
| `draw_risk(light_smoker_share)` | 0.1 | smokes 1-9 cigarettes a day (the study's default) | placeholder | 11.6% (95% CI 11.1-12.1) of US adults smoked cigarettes in 2022, NHIS (item 72); the study's 18% (light and heavy) is above it | `tests/test_risk_shares.py` recovers the shares on a large seeded draw |
| `draw_risk(heavy_smoker_share)` | 0.08 | smokes 10-30 a day (the study's default) | placeholder | as above | the same test |
| `draw_risk(hba1c_share)` | 0.12 | has an HbA1c on record, half drawn from 5.8-6.9 and half from 7.0-10.5 (the study's default), so 8.5% have diabetes and 5.9% HbA1c >= 7.0 | placeholder | 15.8% of US adults 20 and over had diabetes (diagnosed, or HbA1c >= 6.5 or fasting glucose >= 126 mg/dL), NHANES August 2021-August 2023 (item 73); the study's 8.5% is below it | the same test |
| `synthetic.DIABETES_HBA1C` | 6.5 | the HbA1c (%) at or above which a synthetic person has diabetes | item 73 (the NHANES laboratory definition) | HbA1c >= 6.5% (item 73) | no |
| `synthetic.DIABETES_OF_HBA1C` | 0.704545 | the share of drawn HbA1c values at or above 6.5, which `risk_kwargs` divides a diabetes share by | placeholder (follows from the HbA1c draw) | none | `tests/test_risk_shares.py` |
| `study.CHARTED_SHARE` | 0.8 | the share of visits with a full probing chart the evidence reader assumes | item 3 (about 80% of patients charted) | perio chart present for 32.7-69.6% of patients at three dental schools and 99.3-99.7% at a large dental group, 2015-2018 (item 76, Table 2) | no |
| (clinic charting in `clinic_profiles`) | 0.6 to 0.95 per clinic, uniform | the share of a clinic's visits with a probing chart | placeholder | item 76, as above | no |
| (clinic case mix in `clinic_profiles`) | -0.08 to 0.1 per clinic | moves weight from healthy toward moderate and severe disease | placeholder | none | no |
| (clinic size in `clinic_profiles`) | weight 0.5 to 1.5 | how many patients a clinic gets | placeholder | none | no |
| `study.N_CLINICS` | 8 | synthetic clinics | placeholder (design choice) | none | no |
| `study.CLINICIAN_DISAGREES` | 0.25 | the written status is one step off the chart | placeholder | 47% agreement between charting-derived and clinician-recorded diagnoses at one dental school (item 3); the synthetic agreement is higher | no |
| `study.RECORD_ERROR_RATE` | 0.02 | a charted follow-up visit holds another patient's chart or a decimal slip (half each) | placeholder | none | no |
| (people and visits in `_study_visits`) | born 1940-2002; first visit in the first half of 2021; 1-6 visits about 182 days apart | who is in the study | placeholder (design choice) | none | no |
| `study.REVIEW_STRATA` | healthy 0.15, gingivitis 0.2, stage I 0.17, stage II 0.18, stage III 0.18, stage IV 0.12 | target shares of the chart-review set, rare statuses oversampled | placeholder (design choice) | none: a sampling design, not a prevalence | no |
| `study.ANALYSIS_MIN_AGE` | 18 | the youngest age scored (spec 032 US8) | placeholder (design choice) | none | no |
| `study.ANALYSIS_START_DATE` | 2021-04-01 | the first visit date scored, a synthetic stand-in for an adoption date | placeholder (design choice) | none | no |

## The Open Dental extract (`open_dental.py`)

A seeded practice-management extract in Open Dental's table format (spec 029; 2,000 patients by default, 6,000 in
`scripts/51_tooth_loss_model.py` and the presets). It draws smoking, HbA1c and histories with the same
`synthetic.draw_risk` and `draw_history` as the study, so the rows above apply to it too, except that since spec 033
US2 its smoking and diabetes shares are its own settings (`Params.smoking_share`, `heavy_smoking_fraction`,
`diabetes_share`). The record-mess rates are
invented defaults until a real extract's `realism_profile` sets them (#385); `NO_MESS` turns them off.

| Parameter | Value | What it means | Source | Published figure | Checked by |
|---|---|---|---|---|---|
| `Params.n_patients` | 2000 | patients in the extract | placeholder (design choice) | none | no |
| `Params.visits` | 2 to 8 | recall visits per patient | placeholder (design choice) | none | no |
| `Params.first_years` | 2012 to 2022 | the year of the first visit | placeholder (design choice) | none | no |
| `Params.entry_as_existing` | 0.3 | a tooth missing at entry recorded as an extraction done elsewhere | placeholder | none | no |
| `Params.other_extraction_per_visit` | 0.04 | an extraction for another reason between visits | placeholder | none | no |
| `Params.planned_not_done_per_visit` | 0.1 | a periodontal extraction planned and never completed in the record | placeholder | none | no |
| `Params.dx_correct` | 0.8 | the extraction's recorded diagnosis names the true reason | placeholder | 76.7% of diagnoses entered against treatment procedures were valid at one dental school, 2007-2008 (item 77); the synthetic 94% of entered diagnoses (0.8 of 0.85) is higher | no |
| `Params.dx_mismatch` | 0.05 | it names the other kind of reason (a recording mismatch) | placeholder | 23.3% of entered diagnoses not valid (item 77) | no |
| `Params.dx_none` | 0.15 | no diagnosis recorded | placeholder | periodontal diagnosis documented for 3.3-48.6% of patients at three dental schools and 99.9% at a large dental group (item 76) | no |
| `Params.icd_share` | 0.03 | an ICD code, as on a medical claim | placeholder | none | no |
| `Params.list_switch_date` | 2018-01-01 | the practice adopts the 2017 diagnosis list | placeholder (design choice) | none | no |
| `Params.list_adoption_years` | 2 | years over which the older list goes out of use | placeholder | none | no |
| `Params.plans_per_exam` | 1 to 3 | treatment plans saved at an exam that plans something | placeholder | none | no |
| `Params.replan` | 0.7 | a still-planned procedure is copied into the next exam's plans | placeholder | none | no |
| `Params.edited_copy` | 0.03 | a plan copy edited by hand | placeholder | none | no |
| `Params.n_clinics` | 4 | offices | placeholder (design choice) | none | no |
| `Params.n_dentists` | 8 | dentists | placeholder (design choice) | none | no |
| `Params.n_hygienists` | 6 | hygienists | placeholder (design choice) | none | no |
| `Params.sites` | two nursing homes (place of service 4), a school (8), a mobile unit (7) | invented sites of care; 8% of patients are seen at one | placeholder (design choice) | none | no |
| `Params.chart_office` | 0.75 | a visit at an office gets a perio chart | placeholder | perio chart for 32.7-69.6% of patients at three dental schools, 99.3-99.7% at a large dental group (item 76); overall completeness 97.2% in one dental group's extract of children's records (item 57) | `realism_profile` measures it from any extract |
| `Params.chart_site` | 0.3 | a visit at a mobile or nursing-home site does | placeholder | none | `realism_profile` |
| `Params.partial_chart` | 0.2 | a chart covers 40-80% of the teeth present | placeholder | none | `realism_profile` |
| `Params.buccal_only` | 0.1 | a chart records buccal sites only | placeholder | none | `realism_profile` |
| `Params.no_margin` | 0.25 | a chart has no gingival margins, so no CAL | placeholder | none | `realism_profile` |
| `Params.no_bleeding` | 0.15 | a chart has no bleeding | placeholder | none | `realism_profile` |
| `Params.copied_chart` | 0.08 | a chart is the last one copied forward | placeholder | none | `realism_profile` |
| `Params.uniform_chart` | 0.05 | every site the same depth | placeholder | none | `realism_profile` |
| `Params.out_of_range_site` | 0.002 | a site entered as 16-19 mm | placeholder | none | `realism_profile` |
| `Params.charted_after_loss` | 0.03 | a chart includes a tooth already extracted | placeholder | none | `realism_profile` |
| `Params.fmx_first` | 0.6 | a full-mouth series at the first visit | placeholder | none | no |
| `Params.bitewing_per_visit` | 0.35 | bitewings at a later visit | placeholder | none | no |
| `Params.pano_per_visit` | 0.03 | a panoramic image at a later visit | placeholder | none | no |
| `Params.reading_missing` | 0.15 | a tooth the SIMULATED radiograph reading leaves unread | placeholder | none | no |
| `open_dental.ENTRY_PERIO_SHARE_BY_AGE` | 25+: 0.064, 35+: 0.209, 45+: 0.329, 55+: 0.48, 65+: 0.5, 75+: 0.47 | the periodontal share among teeth missing at entry, by age band | item 63, Table 2 (`specs/029-tooth-loss/research.md`) | the same figures | `tests/test_open_dental.py` (`test_the_periodontal_share_at_entry_follows_the_published_mix_by_age`) |
| `Params.entry_other_teeth_by_age` | 25+: 3.61, 35+: 0.96, 45+: 0.54, 55+: 0.33, 65+: 0.28, 75+: 0.35 | mean teeth missing at entry for another reason, by age band, set so the share above holds | item 63, solved for in `specs/029-tooth-loss/research.md` | item 63 | the same test |
| `Params.entry_other_tooth_weights` | molar 3, premolar 2, canine 1, incisor 1 | which teeth those are | placeholder (research.md: the repo's choice) | none | no |
| `Params.entry_other_smoking_ratios` | 1+ a day: 1.05, 20+ a day: 1.38 | how much more often a smoker has them | item 68, Table 3 | the same figures | `tests/test_open_dental.py` (`test_the_rate_ratio_multiplies_the_cited_smoking_and_diabetes_ratios`) |
| `Params.entry_other_diabetes_ratio` | 1.2 | how much more often a patient with diabetes has them (an upper bound) | item 70 (item 69 on why it is an upper bound) | the same figure | the same test |
| `Params.entry_other_norm_draws` | 20000 | patients drawn to keep each band's mean | placeholder (design choice) | none | no |
| `Params.smoking_share` | 0.116 | patients who smoke cigarettes (`synthetic.draw_risk` through `open_dental.risk_kwargs`) | item 72 | 11.6% (95% CI 11.1-12.1) of US adults, 2022 (item 72) | `tests/test_risk_shares.py` recovers it in a built extract |
| `Params.heavy_smoking_fraction` | 0.44 | of the smokers, the share at 10 or more a day (the study's 0.08 of 0.18) | placeholder | none checked | the same test |
| `Params.diabetes_share` | 0.158 | patients with HbA1c >= 6.5, so with type 2 diabetes listed | item 73 | 15.8% of US adults 20 and over (item 73) | the same test |
| `open_dental.DIABETES_HBA1C` | 6.5 | the HbA1c (%) at which a patient has type 2 diabetes listed | item 73 (the NHANES laboratory definition) | HbA1c >= 6.5% (item 73) | no |
| `Params.insurance_shares` | private 0.55, public 0.3, none 0.15 | each patient's insurance type | placeholder | dental coverage of US adults is reported as about 62% private, 16% public and 22% none for 2022, from the ADA Health Policy Institute; that report could not be opened from this environment, so it is not checked and not cited (spec 033 US2) | `tests/test_open_dental.py` recovers the declared shares |
| `Params.secondary_plan` | 0.05 | a privately insured patient also has a second private plan | placeholder | none | no |
| `Params.spouse_subscriber` | 0.25 | a private plan held by a spouse | placeholder | none | no |
| `Params.edentulous_share_by_age` | 25+: 0.008, 35+: 0.013, 45+: 0.037, 55+: 0.079, 65+: 0.089, 70+: 0.106, 75+: 0.178 | patients with no natural teeth, by age band (spec 033 US4): every tooth missing at entry, no perio chart | item 79 at 65 and over; below 65 this repo's NHANES 2009-2014 run (`data/datasets/nhanes/nhanes_edentulous_by_age.csv`, real public data), its 30-34 rate standing in for 25-34 | 8.9% at 65-69, 10.6% at 70-74, 17.8% at 75+, NHANES 2015-2018 (item 79); 0.8% at 30-34, 1.3% at 35-44, 3.7% at 45-54, 7.9% at 55-64, NHANES 2009-2014 (this repo's run, `scripts/38_nhanes_perio.py`) | `tests/test_open_dental.py` (`test_the_edentulous_share_follows_the_published_rates_by_age`); the table below |
| `Params.clinic_states` | none (empty) | optional: one US state per clinic, which scales its patients' edentulous share by the state's rate over the US rate; empty keeps the national shares and `clinic.state` `ZZ` | placeholder (design choice; the rates are item 81) | none | `tests/test_open_dental.py` (`test_a_state_extract_has_more_edentulous_patients_where_the_state_rate_is_higher`) |
| `open_dental.STATE_EDENTULOUS_65_PCT` | AL 16.6, AK 11.8, AZ 10.2, AR 22.1, CA 6.9, CO 7.5, CT 10.0, DE 11.0, DC 11.6, FL 12.2, GA 15.8, HI 5.4, ID 13.3, IL 8.8, IN 18.6, IA 10.6, KS 11.2, KY 22.5, LA 17.0, ME 15.3, MD 8.7, MA 10.7, MI 10.0, MN 8.1, MS 19.0, MO 15.3, MT 12.0, NE 9.5, NV 12.1, NH 10.7, NJ 10.1, NM 11.8, NY 11.9, NC 16.5, ND 11.8, OH 15.6, OK 16.9, OR 10.1, PA 13.1, RI 11.4, SC 12.9, SD 10.3, TN 18.2, TX 13.0, UT 8.6, VT 13.3, VA 10.8, WA 8.5, WV 25.1, WI 9.0, WY 13.5, US 12.1 | adults 65 and over with all teeth lost, % by state, used only as a ratio to the US figure | item 81 (CDC U.S. Chronic Disease Indicators, BRFSS 2022, crude prevalence) | the same figures | no |
| (patient table, inline in `build_with_readings`) | age 25-85; ex-smoker 0.2 of non-smokers; inactive 0.12, deceased 0.03; Spanish 0.1; premedication 0.05; hypertension 0.35 over 50; asthma 0.07; other medicine 0.3; allergy 0.12 | patient rows | placeholder | hypertension 33.2% at 40-59 and 63.1% at 60+ (NCHS Data Brief 289, cited in `medical_record.py`) | no |
| (visits, inline in `build_with_readings`) | scaling and root planing at an untreated periodontitis visit 0.5; surgical extraction 0.2; signed plan 0.5; extraction note 0.7; vital signs 0.6; plaque 0.4, calculus 0.3 | visit rows | placeholder | scaling and root planing: 49.7% (item 78) | no |

## The medical record (`medical_record.py`, spec 023)

One synthetic medical record per study person, on its own random stream. Each rate's citation is in the code
(`Condition.rate_source`, `odds_ratio_source`, `MEASURES`, `HYPERTENSION_CONTROL`, `ASA_SOURCE`), and
`tests/test_medical_record.py` checks that every one names a source.

| Parameter | Value | What it means | Source | Published figure | Checked by |
|---|---|---|---|---|---|
| `medical_record.CONDITIONS[is_hypertension]` | 18-39: 0.075, 40-59: 0.332, 60+: 0.631; OR 1.22 in stages II-IV | hypertension by age band, and its odds ratio with periodontitis | cited in `medical_record.py` (NCHS Data Brief 289; Muñoz Aguilera et al. 2020) | the same figures | `tests/test_medical_record.py`: the age-adjusted odds ratio is recovered (`test_age_adjusted_odds_ratios_are_the_cited_ones`) and the base rates hold (`test_base_rates_hold_in_the_unexposed`) |
| `medical_record.CONDITIONS[is_ckd]` | 18-44: 0.06, 45-64: 0.13, 65+: 0.34; OR 1.6 in periodontitis | chronic kidney disease | cited in `medical_record.py` (CDC CKD in the US 2026; Kapellas et al. 2019) | the same figures | the same tests |
| `medical_record.CONDITIONS[is_cvd]` | 18-44: 0.009, 45-64: 0.059, 65+: 0.182; OR 1.19 in periodontitis | cardiovascular disease | cited in `medical_record.py` (NCHS QuickStats 2022; Janket et al. 2003, a relative risk used as an odds ratio) | the same figures | the same tests |
| `medical_record.CONDITIONS[is_copd]` | 18-24: 0.004, 25-44: 0.014, 45-54: 0.029, 55-64: 0.074, 65-74: 0.089, 75+: 0.105; OR 2.08 in periodontitis | COPD | cited in `medical_record.py` (NCHS Data Brief 529; Zeng et al. 2012) | the same figures | the same tests |
| `medical_record.HYPERTENSION_CONTROL` | 18-39: 0.325, 40-59: 0.508, 60+: 0.494 | blood pressure controlled among people with hypertension | cited in `medical_record.py` (NCHS Data Brief 289) | the same figures | no |
| `medical_record.MEASURES` | normal 100-139 / 60-89; controlled 110-139 / 65-89; raised 140-179 / 80-109 mmHg | blood-pressure bands | cited in `medical_record.py` (NCHS Data Brief 289 sets the 140/90 cut; the outer ends are a placeholder) | 140/90 (Data Brief 289) | no |
| `medical_record.DIABETES_HBA1C` | 6.5 | diabetes is the generator's HbA1c >= 6.5, never redrawn | item 73 | HbA1c >= 6.5% (item 73) | `tests/test_medical_record.py` (`test_diabetes_always_agrees_with_hba1c`) |
| `medical_record.UNCONTROLLED_HBA1C` | 7 | poorly controlled diabetes, for the ASA class | cited in `medical_record.py` (`ASA_SOURCE`, a repo choice there) | none | no |
| `medical_record.OR_TOLERANCE_LOG` | 0.25 | how close a recovered odds ratio must be, on the log scale | placeholder (test tolerance) | none | `tests/test_medical_record.py` |

## Complete tooth loss: synthetic against published (spec 033 US4, #500)

Before US4 no patient of the extract had lost every tooth. Since US4 `Params.edentulous_share_by_age` sets the share,
drawn on a random stream of its own: an edentulous patient's mouth and visits are still drawn and thrown away, so every
patient with teeth keeps their rows. An edentulous patient has all 32 teeth in `toothinitial` and no perio chart,
radiograph, hygiene visit or extraction, and no answer-key rows (why they lost their teeth isn't modelled). The
tooth-loss model and the stage recount leave them out, since the 2018 classification can't stage a mouth with no
teeth (`tooth_loss_model.edentulous`); `realism_profile` leaves their visits out of the charting rates and reports
their share; `tooth_loss_dq` flags a perio chart recorded for one (`chart_without_teeth`).

The 6,000-patient extract, seed 42 (SYNTHETIC), against the published figures:

| Age band | Patients | Edentulous, before US4 | Edentulous, after US4 | Published | Source |
|---|---|---|---|---|---|
| 25-34 | 1,017 | 0 | 7 (0.7%) | 0.8% at 30-34 (95% CI 0.1-1.4) | this repo's NHANES 2009-2014 run |
| 35-44 | 972 | 0 | 13 (1.3%) | 1.3% (0.7-1.9) | the same |
| 45-54 | 959 | 0 | 42 (4.4%) | 3.7% (2.4-5.0) | the same |
| 55-64 | 989 | 0 | 83 (8.4%) | 7.9% (5.9-9.8) | the same |
| 65-69 | 454 | 0 | 36 (7.9%) | 8.9% | item 79 (NHANES 2015-2018) |
| 70-74 | 485 | 0 | 50 (10.3%) | 10.6% | item 79 |
| 75-85 | 1,124 | 0 | 198 (17.6%) | 17.8% at 75 and over | item 79 |
| 65 and over | 2,063 | 0 | 284 (13.8%) | 12.9% | item 79 |
| all, 25-85 | 6,000 | 0 | 429 (7.2%; 7.7% of those 30 and over) | 6.9% of adults 30+ in 2009-2014 (this repo's run; Tay et al. 2025: 6.7%) | `data/datasets/nhanes/nhanes_prevalence.csv` |

The extract's ages are uniform from 25 to 85, older than US adults, so its overall share sits a little above the
national one. The rates under 65 come from 2009-2014 and complete tooth loss is falling (item 80: age-adjusted 29.3%
at 65 and over in 1999-2000, 12.6% in 2017-2018), so they may run a little high.

**Geography (optional).** `Params.clinic_states` gives each clinic a US state; its patients' share is then the age
band's share times the state's rate over the US rate (`STATE_EDENTULOUS_65_PCT`, adults 65 and over with all teeth
lost, BRFSS 2022: 12.1% in the US, 5.4% in Hawaii to 25.1% in West Virginia; item 81). The state figures are for 65 and
over only, so the same ratio is applied at every age, a placeholder assumption. Off by default: the default extract's
clinics keep the state `ZZ` and every committed result uses the national shares.

## Sources checked for this card

Items 72 to 81 of [references.md](references.md) were added for this card, each checked against its full text or,
where the item says so, its abstract (item 81, the state rates, against the CDC dataset itself). Three candidate
sources were not used:

- **Dental coverage, ADA Health Policy Institute (2022)**: the HPI pages and the news report of them could not be
  opened from this environment, so the figures were not checked. `Params.insurance_shares` stays a placeholder.
- **America's Health Rankings (BRFSS teeth extractions by state)**: the page could not be opened from this
  environment (tried again for spec 033 US4), so its figures were not checked or cited. The same BRFSS measure is
  published by CDC's U.S. Chronic Disease Indicators, which could be read, and is item 81.
- **Open Dentistry Journal 2019;13:520** (an EDR audit at one dental school): the article could not be opened, so its
  charting figures were not checked or cited.
