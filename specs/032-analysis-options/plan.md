# Plan: analysis options (spec 032)

One pull request per user story, each from its issue's branch, defaults unchanged so they can merge in any order;
US7 after them, since it calls the others; US8 last, flipping the defaults and rerunning every result.

| Story | Where | R twin |
|---|---|---|
| US1 grouping | `labels.py` (`GROUPINGS`, `group_status`), `eval/score.py`, prevalence | `eval/score.R`, labels in R |
| US2 visit filters | study-set builder, `tooth_loss_model.ModelParams.start_date` | none (filters) |
| US3 absent code | `phenotype.py` code source | phenotype R twin |
| US4 stage IV rules | `labels.STAGE4_COUNT_RULES`, `tooth_loss_model` recount | `r/R/16_spec029.R` |
| US5 validation | `tooth_loss_model`, `classify_status` | none (model fitting) |
| US6 insurance | `open_dental.py`, `tooth_loss_dq.py`, `opendental_silver_model.py`, ERDs | none |
| US7 preset | `analysis_presets.yaml`, `scripts/56_exploratory_preset.py` | none |
| US8 new defaults | every default above; `repo_v1` preset; all result scripts rerun | parity rerun |

Every new public function gets `@traced`. Settings are arguments with fixed defaults (AGENTS.md: seeds and
defaults fixed); no environment variable is added.
