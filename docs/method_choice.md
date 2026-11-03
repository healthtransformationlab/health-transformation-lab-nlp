# How each method was chosen, and why

The [study design](process.md) shows the steps. This page explains the choice behind each one: what kind of data
each question produces, the textbook rule for matching a method to that data, and the method this repo uses. Every
number the methods produce here is on SYNTHETIC data; the page is about the choice, not the results.

## 1. Start from the question and the outcome's type

The first question is always: what is being measured, and what kind of value is it?

| Outcome type | Example in this repo | What it allows |
|---|---|---|
| **Binary** (yes/no) | periodontitis yes/no; was a missing tooth lost to periodontitis | proportions, odds ratios, logistic regression, AUC |
| **Ordinal** (ordered categories) | healthy, gingivitis, stage I to IV | weighted kappa, ordinal or multiclass models; distances between levels are not equal |
| **Nominal** (unordered categories) | which evidence source gave the answer | chi-square, multinomial models |
| **Count** | teeth lost to periodontitis per patient | Poisson or negative binomial models; a threshold (5 or more) turns it into binary |
| **Continuous** | attachment loss in mm, pocket depth in mm | means, t-tests or rank tests, linear and multilevel models |
| **Agreement between raters** | two reviewers staging the same chart | kappa, not correlation or percent agreement |

## 2. The textbook rules for picking a test

These are the standard rules from introductory biostatistics. They decide which test is valid before any question of
which is best.

| Question | Data | Test | Main assumption |
|---|---|---|---|
| Two groups differ? | continuous, roughly normal | t-test (Welch's if spreads differ) | independent observations; normal-ish means (holds for large samples by the central limit theorem) |
| Two groups differ? | continuous, skewed or small sample | Mann-Whitney U (Wilcoxon rank-sum) | independent observations; compares ranks, not means |
| Same people measured twice? | paired continuous | paired t-test, or Wilcoxon signed-rank if skewed | pairs are independent of each other |
| Three or more groups? | continuous | ANOVA, or Kruskal-Wallis if skewed | as above |
| Two categorical variables related? | counts in a table | chi-square; Fisher's exact when an expected cell is under 5 | independent observations |
| A proportion and its interval? | binary | Wilson interval (better than the Wald interval near 0% or 100% or in small samples) | independent observations |
| Two raters agree? | categories | Cohen's kappa (2 raters), Fleiss' kappa (many), weighted kappa (ordered) | the same items rated by each |
| An interval for anything else? | any statistic | bootstrap: resample the units, recompute, take the 2.5th and 97.5th percentiles | resample the independent unit (the person, not the visit) |
| Repeated measures nested in people? | continuous, clustered | multilevel (mixed) model; intra-class correlation (ICC) | the nesting is modelled |
| Survey data with weights? | any | survey-weighted estimates with design-based (Taylor-linearized) standard errors | the survey's strata and clusters are used |

**The independence rule matters most here.** A patient has many visits, a mouth has many teeth, a tooth has six
sites. Treating these as independent makes intervals too narrow and scores too good. Every method below therefore
resamples, splits or models at the patient level.

## 3. The methods this repo uses, and why

### Finding gum disease in the record (phenotyping): rules first

- **What:** fixed rules that read each evidence source (exam form, diagnosis code, note, chart) and combine them in
  a set order (`phenotype.py`, `labels.py`, [evidence_rules.md](evidence_rules.md)).
- **Why:** the 2018 AAP/EFP classification is itself a rule set, so rules can apply it exactly and explain every
  answer. They need no training data, which matters when real labelled records are scarce.
- **When to move past rules:** when evidence is free text (notes), or when the rules miss a pattern the data shows.

### Reading notes: text models

- **What:** keyword rules, TF-IDF with logistic regression, BERT-family encoders and LLM readers such as MedGemma
  ([model_inventory.md](model_inventory.md)).
- **Why a ladder:** each step up costs more compute and is harder to explain, so each must beat the cheaper one on
  the same held-out notes before it earns its place ([scoring.md](scoring.md)).

### Agreement: kappa, not percent agreement

- **What:** Cohen's, Fleiss' and weighted kappa ([statistics.md](statistics.md)).
- **Why:** when one answer is common, two raters agree often by chance; kappa removes that. Stages are ordered, so
  weighted kappa counts calling stage III "stage II" as a smaller miss than calling it "healthy".

### Intervals: Wilson and the bootstrap

- **What:** Wilson intervals for prevalence (`prevalence.wilson_ci`); bootstrap intervals over patients for model
  scores and paired differences ([statistics.md](statistics.md)).
- **Why:** Wilson stays sensible near 0% and 100%; the bootstrap works for any score (AUC, kappa, a difference)
  without a formula, as long as the patient, not the visit, is resampled.

### National comparison: survey-weighted prevalence

- **What:** NHANES prevalence with survey weights and Taylor-linearized standard errors (`nhanes.py`).
- **Why:** NHANES over-samples some groups on purpose; unweighted shares would not describe the US population.

### Reliability of attachment loss: the multilevel ICC

- **What:** a model of attachment loss with sites nested in teeth nested in patients, time as a fixed effect, and
  the intra-class correlation at each level (`reliability_cal.py`).
- **Why:** repeated readings of the same site are not independent; the ICC says how much of the variation is real
  difference between patients, teeth and sites rather than measurement error (de Vet et al. 2006).

### Prediction: logistic regression and XGBoost, side by side

Both are used for a binary outcome: was a missing tooth lost to periodontitis ([tooth_loss.md](tooth_loss.md)), and
does the next visit show a higher stage (`prediction.py`). The visit-level status classifier
(`classify_status.py`) uses XGBoost for five- and three-level outcomes.

| | Logistic regression | XGBoost (gradient-boosted trees) |
|---|---|---|
| **What it assumes** | each predictor shifts the log-odds by a fixed amount (a straight line on the log-odds scale), unless interactions or splines are added by hand | nothing about shape: it finds thresholds, curves and interactions itself |
| **Variable types** | numeric predictors; categories as indicator columns; missing values need imputing (here: median plus a missing-value indicator) | numeric and indicator columns; missing values handled natively |
| **Data needed** | works with few events (a common rule of thumb is 10 or more events per predictor) | needs more data to beat logistic regression; overfits small sets without tuning |
| **What it explains** | its coefficients are the explanation: each is an odds ratio, with a confidence interval | not readable directly; needs SHAP or permutation importance |
| **Probabilities** | usually well calibrated | can be over- or under-confident; check calibration |
| **When to choose it** | small data, a need for odds ratios, a reporting standard that expects them, or a baseline | larger data, non-linear effects or interactions you can't specify in advance |

**The repo reports both** because neither is known to win in advance. If XGBoost does not beat logistic regression
on held-out patients, the simpler, explainable model is preferred. Both are judged the same way: AUC (ranking),
Brier score and calibration slope (whether probabilities are honest), and sensitivity and specificity at a threshold
chosen on training data only (TRIPOD+AI, [probast_tripod_ai.md](probast_tripod_ai.md)).

### Explaining a model: SHAP and permutation importance

**SHAP is not an alternative to logistic regression.** It is a way of explaining a model that has already been
fitted, most often a tree model like XGBoost.

- **SHAP** splits each single prediction into a contribution from each feature, which add up to the model's output
  (here exact TreeSHAP, computed by XGBoost itself). Use it to see which features drove one patient's prediction
  and which matter most overall.
- **Permutation importance** shuffles one feature on held-out data and measures how much the score drops. It is
  simpler and works for any model (`prediction.py`).
- **Logistic regression needs neither**: its odds ratios already say how much each feature moves the odds.

Three cautions apply to SHAP and permutation importance alike:
1. **They describe the model, not the patient's biology.** A large SHAP value means the model leans on that feature,
   not that the feature causes the outcome.
2. **Correlated features share credit.** Pocket depth and attachment loss move together, so the credit can split
   between them unpredictably.
3. **On this repo's synthetic data**, labels come from the same AAP rules the features feed, so the ranking checks the
   pipeline and finds nothing about real patients.

## 4. Choosing in practice

1. **What is the outcome type?** (section 1)
2. **What is the independent unit?** Usually the patient: split, resample and cluster by it.
3. **Is the question to describe, compare, agree or predict?**
   - Describe: proportions with Wilson intervals, survey weights for national samples.
   - Compare groups: the tests in section 2.
   - Agree: kappa or ICC.
   - Predict: logistic regression as the baseline, a flexible model beside it, and judge both on held-out patients.
4. **Does the answer need to be explained?** Prefer the model whose explanation is built in (rules, logistic
   regression) unless a flexible model is clearly better; then explain it with SHAP or permutation importance, with
   the cautions above.

Related: [statistics.md](statistics.md) (kappa, intervals, the acceptance test), [scoring.md](scoring.md) (how
scores are computed), [tooth_loss.md](tooth_loss.md) (the tooth-loss models), [presets.md](presets.md) (the
validation settings and why the split is by patient).
