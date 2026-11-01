# Parity checks: the R side must agree with the Python side.
#   Rscript r/tests/test_parity.R            (from repo root, after python scripts 01 + 02)
# Base R only.

source("r/R/labels.R")
source("eval/score.R")

# 0. AAP worksheet edge cases: CAL missing, tooth loss, complexity factors.
if (file.exists("data/labels/aap_rule_cases.csv")) {
  g <- read.csv("data/labels/aap_rule_cases.csv", stringsAsFactors = FALSE)
  r <- label_chart(g$pd, rep(30, nrow(g)), g$cal, g$rbl, g$lost, vertical_defect_mm = g$vd,
                   furcation_class = g$fc, mobility_degree = g$mob, remaining_teeth = g$rem)
  cat(sprintf("AAP rules: %d / %d edge cases agree\n", sum(r == g$label), nrow(g)))
  stopifnot(all(r == g$label))
} else cat("AAP rules: skipped (run python/scripts/export_rules_predictions.py first)\n")

if (file.exists("data/labels/labeled_notes.csv")) {
notes <- read.csv("data/labels/labeled_notes.csv", stringsAsFactors = FALSE)
split <- read.csv("data/labels/split.csv")

# 1. Labels: R label_chart on the chart columns == Python's label column.
r_lab <- with(notes, label_chart(max_probing_depth_mm, bop_pct, max_cal_mm, rbl_pct, teeth_lost_perio))
mism <- sum(r_lab != notes$label)
cat(sprintf("labels:  %d / %d agree\n", nrow(notes) - mism, nrow(notes)))
stopifnot(mism == 0)

# 2. Rules baseline: R regex rules == Python regex rules on every note.
py_rules_file <- "data/labels/python_rules_predictions.csv"
if (file.exists(py_rules_file)) {
  py <- read.csv(py_rules_file, stringsAsFactors = FALSE)
  m <- merge(py, data.frame(note_id = notes$note_id, r_pred = rules_predict(notes$note_text)))
  cat(sprintf("rules:   %d / %d agree\n", sum(m$pred == m$r_pred), nrow(m)))
  stopifnot(all(m$pred == m$r_pred))
} else cat("rules:   skipped (run python/scripts/export_rules_predictions.py first)\n")

# 3. Scorer: R score_run == Python score.py on the same predictions.
test <- merge(notes, split)[merge(notes, split)$split == "test", ]
res <- score_run(test$label, rules_predict(test$note_text), NULL, "rules_baseline", run_id = "parity")
py_res_file <- "data/labels/python_rules_score.csv"
if (file.exists(py_res_file)) {
  py <- read.csv(py_res_file, stringsAsFactors = FALSE)
  key <- function(d) paste(d$metric, ifelse(is.na(d$class), "", d$class))
  both <- merge(data.frame(k = key(res), r = res$value), data.frame(k = key(py), p = py$value))
  diff <- abs(both$r - both$p); diff[is.na(diff)] <- 0
  cat(sprintf("scorer:  max |R - Python| = %.2e over %d metrics\n", max(diff), nrow(both)))
  stopifnot(max(diff) < 1e-9)
} else cat("scorer:  skipped (python score file not found)\n")

} else cat("labels/rules/scorer: skipped (run python scripts 01 + 02 + export_rules_predictions first)\n")

# 4. Reliability: R 04_reliability.R == Python reliability.py (needs a simulated or real review run).
py_rel <- "data/review/simulated_reliability/methods_vs_reviewers.csv"
if (file.exists(py_rel) && file.exists("data/review/simulated_reviewer_labels.csv")) {
  source("r/R/04_reliability.R")
  labels <- read.csv("data/review/simulated_reviewer_labels.csv", stringsAsFactors = FALSE)
  key <- read.csv("data/datasets/answer_key/review_key.csv", stringsAsFactors = FALSE)
  py <- read.csv(py_rel, stringsAsFactors = FALSE)
  compare <- setNames(lapply(setdiff(py$method, "generator_chart_truth"), function(m) {
    if (startsWith(m, "ai:")) { p <- read.csv(sprintf("data/datasets/ai_predictions_%s.csv", sub("^ai:", "", m)))
      setNames(p$pred, p$visit_id) } else setNames(key[[m]], key$visit_id)
  }), setdiff(py$method, "generator_chart_truth"))
  r <- reliability_report(labels, key, compare)$methods
  r <- r[match(py$method, r$method), ]
  num <- c("coverage", "pct_agree_consensus", "kappa_vs_consensus", "weighted_kappa_vs_consensus",
           "mean_kappa_vs_each_reviewer", "unsafe_rate", "s2_rate")
  d <- max(abs(as.matrix(r[num]) - as.matrix(py[num])), na.rm = TRUE)
  cat(sprintf("reliability: max |R - Python| = %.2e over %d methods\n", d, nrow(py)))
  stopifnot(d < 1e-9)
  # spec 002: agreement by difficulty level
  py_lv <- read.csv("data/review/simulated_reliability/by_level.csv", stringsAsFactors = FALSE)
  cons_df <- read.csv("data/review/simulated_reliability/consensus.csv", stringsAsFactors = FALSE)
  r_lv <- by_level(key, cons_df, compare)
  m <- merge(py_lv, r_lv, by = c("method", "level"), suffixes = c("_py", "_r"))
  dl <- max(abs(m$pct_agree_consensus_py - m$pct_agree_consensus_r), na.rm = TRUE)
  cat(sprintf("by level:    max |R - Python| = %.2e over %d rows\n", dl, nrow(m)))
  stopifnot(nrow(m) == nrow(py_lv), dl < 1e-9)
  # 4b. AI vs humans: point estimates exact, bootstrap CI approximate (different RNG)
  py_vh_f <- "data/review/simulated_reliability/agreement_vs_humans.csv"
  if (file.exists(py_vh_f)) {
    py_vh <- read.csv(py_vh_f, stringsAsFactors = FALSE)
    w <- reshape(labels[, c("visit_id", "reviewer", "status")], idvar = "visit_id", timevar = "reviewer", direction = "wide")
    rownames(w) <- w$visit_id; w$visit_id <- NULL; names(w) <- sub("^status\\.", "", names(w))
    w <- w[order(as.numeric(rownames(w))), , drop = FALSE]
    r_vh <- agreement_vs_humans(w, compare, n_boot = 200)
    mm <- merge(py_vh, r_vh, by = "rater", suffixes = c(".py", ".r"))
    d <- max(abs(mm$mean_kappa_vs_humans.py - mm$mean_kappa_vs_humans.r))
    ci_d <- max(abs(c(mm$ci_low.py - mm$ci_low.r, mm$ci_high.py - mm$ci_high.r)), na.rm = TRUE)
    cat(sprintf("vs humans:   max |R - Python| = %.2e over %d raters; CI bounds within %.3f\n", d, nrow(mm), ci_d))
    stopifnot(nrow(mm) == nrow(py_vh), d < 1e-9, ci_d < 0.05)
  }
} else cat("reliability: skipped (run python scripts 12 --simulate and 13 --simulated first)\n")
# 9. De-identification cost-effectiveness: R 08_deid.R == Python deid_eval.cost_table (spec 007).
if (file.exists("data/deid/cost_inputs.csv") && file.exists("data/deid/cost_effectiveness.csv")) {
  source("r/R/08_deid.R")
  ci <- read.csv("data/deid/cost_inputs.csv", stringsAsFactors = FALSE)
  ci$unit[is.na(ci$unit)] <- ""; ci$hardware[is.na(ci$hardware)] <- ""
  r <- deid_cost_table(ci)
  py <- read.csv("data/deid/cost_effectiveness.csv", stringsAsFactors = FALSE)
  m <- merge(r, py, by = c("tier", "method"), suffixes = c(".r", ".p"))
  stopifnot(nrow(m) == nrow(py), nrow(m) == nrow(r))
  num <- c("cost_usd", "leaked_per_1m_notes", "icer_usd_per_leak_avoided")
  d <- max(sapply(num, function(k) { x <- abs(m[[paste0(k, ".r")]] - m[[paste0(k, ".p")]]); max(ifelse(is.na(x), 0, x)) }))
  same_na <- all(is.na(m$icer_usd_per_leak_avoided.r) == is.na(m$icer_usd_per_leak_avoided.p))
  cat(sprintf("de-id CE: %d rows, max |R - Python| = %.2e, dominated agree: %s\n", nrow(m), d,
              all(m$dominated.r == as.logical(m$dominated.p))))
  stopifnot(d < 1e-6, same_na, all(m$dominated.r == as.logical(m$dominated.p)))
} else cat("de-id CE: skipped (run python/scripts/26_deid_benchmark.py first)\n")
# 9e. De-identification review flows (spec 008): agreement, consensus, annotator recall, and the QA
# leak rate, sensitivity, specificity and leak-span recall, R == Python.
for (pfx in c("", "simulated_")) {
  f <- sprintf("data/deid/review/%sgold_spans.csv", pfx)
  if (!file.exists(f)) next
  source("r/R/08_deid.R")
  rd <- function(x) read.csv(sprintf("data/deid/review/%s%s.csv", pfx, x), stringsAsFactors = FALSE)
  gs <- read.csv(f, stringsAsFactors = FALSE)
  ma <- merge(deid_agreement(gs), rd("gold_agreement"), by = c("annotator_a", "annotator_b"), suffixes = c(".r", ".p"))
  da <- max(abs(ma$f1_span.r - ma$f1_span.p), abs(ma$f1_typed.r - ma$f1_typed.p), abs(ma$n_notes.r - ma$n_notes.p))
  rc <- deid_consensus(gs); pc <- rd("gold_consensus")
  mc <- merge(rc, pc, by = c("note_id", "start", "end"), suffixes = c(".r", ".p"))
  ok_c <- nrow(mc) == nrow(pc) && nrow(rc) == nrow(pc) && all(mc$type.r == mc$type.p)
  mr <- merge(deid_annotator_recall(gs, rd("generator_spans")), rd("gold_annotator_recall"),
              by = c("annotator", "aided"), suffixes = c(".r", ".p"))
  dr <- max(abs(mr$entity_recall.r - mr$entity_recall.p), abs(mr$n_phi.r - mr$n_phi.p))
  ql <- rd("qa_labels"); pq <- rd("qa_summary")
  mq <- merge(merge(deid_qa_summary(ql), deid_qa_vs_key(ql, rd("qa_key")), by = "scope"), pq,
              by = "scope", suffixes = c(".r", ".p"))
  cols <- c("n_notes", "leak_notes", "leak_rate", "leak_lo", "leak_hi", "over_redaction_rate",
            "sensitivity", "specificity", "leak_span_recall")
  dq <- max(sapply(cols, function(k) { x <- abs(mq[[paste0(k, ".r")]] - mq[[paste0(k, ".p")]]); max(ifelse(is.na(x), 0, x)) }))
  cat(sprintf("%sdeid review: %d pairs %.2e; consensus %d spans same: %s; recall %.2e; QA %d scopes %.2e\n",
              pfx, nrow(ma), da, nrow(pc), ok_c, dr, nrow(mq), dq))
  stopifnot(nrow(ma) == nrow(rd("gold_agreement")), da < 1e-9, ok_c, nrow(mr) == nrow(rd("gold_annotator_recall")),
            dr < 1e-9, nrow(mq) == nrow(pq), dq < 1e-9)
}

# 9b. Licensed engines (John Snow Labs) never reach cost_inputs.csv without a licence, so check the
# R twin directly against Python's deid_eval.engine_cost on the vendor's example (1M notes x 5,250 chars).
source("r/R/08_deid.R")
lic <- list(chars_per_sec = 6392.7, node_usd_per_hour = 1.2, license_usd_per_month = 7000, hours_per_month = 744)
lic_cost <- function(pr) deid_engine_cost("licensed", "cpu", NA, "", NA, 0, 1e6, 5250, 1, 4,
                                          lic = c(lic, list(prorate_license = pr)))
stopifnot(abs(lic_cost(1) - 2420.085118369502) < 1e-6, abs(lic_cost(0) - 7273.749745803808) < 1e-6,
          abs(lic_cost(NA) - 7273.749745803808) < 1e-6)
cat("de-id licensed cost: R == Python (prorated, whole month, missing)\n")

# 9c. Model ladder vs the synthetic truth (spec 002 T015): R 10_ladder.R == Python ladder_eval point estimates.
if (file.exists("data/datasets/ladder/ladder_vs_truth.csv")) {
  source("r/R/10_ladder.R")
  lp <- read.csv("data/datasets/ladder/ladder_preds.csv", stringsAsFactors = FALSE, check.names = FALSE)
  lq <- read.csv("data/datasets/ladder/ladder_proba.csv", stringsAsFactors = FALSE)
  names(lq) <- sub("^p_", "", names(lq))
  r <- ladder_point(lp, lq)
  py <- read.csv("data/datasets/ladder/ladder_vs_truth.csv", stringsAsFactors = FALSE)
  m <- merge(r, py, by = "method", suffixes = c(".r", ".p"))
  cols <- c("accuracy", "stage4_recall", "unsafe_rate", "s2_rate", "ece")
  d <- max(sapply(cols, function(k) { x <- abs(m[[paste0(k, ".r")]] - m[[paste0(k, ".p")]]); max(ifelse(is.na(x), 0, x)) }))
  same_na <- all(is.na(m$ece.r) == is.na(m$ece.p))
  cat(sprintf("ladder vs truth: %d methods, max |R - Python| = %.2e\n", nrow(m), d))
  stopifnot(nrow(m) == nrow(py), d < 1e-9, same_na)
} else cat("ladder vs truth: skipped (run python/scripts/28_ladder_vs_truth.py first)\n")

# 9c'. Spec 030: the same accuracy on charts that can and can't be staged (R by_difficulty == Python).
sf <- "data/datasets/ladder/ladder_by_stageable.csv"
if (file.exists(sf)) {
  source("r/R/10_ladder.R")
  lp <- read.csv("data/datasets/ladder/ladder_preds.csv", stringsAsFactors = FALSE, check.names = FALSE)
  rk <- read.csv("data/datasets/answer_key/review_key.csv", stringsAsFactors = FALSE)
  rad <- suppressWarnings(as.numeric(rk$rad_present))
  ok <- (!is.na(rk$probing_chart) & rk$probing_chart != "unknown") | (!is.na(rad) & rad == 1)
  lv <- ifelse(ok, "stageable", "not_stageable")[match(lp$visit_id, rk$visit_id)]
  rs <- by_difficulty(lp, lv)
  ps <- read.csv(sf, stringsAsFactors = FALSE)
  m <- merge(rs, ps, by.x = c("method", "difficulty"), by.y = c("method", "stageable_code"), suffixes = c(".r", ".p"))
  d <- max(abs(m$accuracy.r - m$accuracy.p), na.rm = TRUE)
  cat(sprintf("ladder by stageable: %d rows, n equal %s, max |R - Python| = %.2e\n", nrow(m),
              all(m$n.r == m$n.p), d))
  stopifnot(nrow(m) == nrow(ps), all(m$n.r == m$n.p), d < 1e-9)
} else cat("ladder by stageable: skipped (run python/scripts/28_ladder_vs_truth.py first)\n")

# 9e. Spec 030 US2: the same accuracy by age band and by clinic (R by_difficulty == Python):
#     ladder_by_age.csv, ladder_by_clinic.csv.
for (grp in c("age", "clinic")) {
  gf <- sprintf("data/datasets/ladder/ladder_by_%s.csv", grp)
  if (!file.exists(gf)) { cat(sprintf("ladder by %s: skipped (run 28_ladder_vs_truth.py)\n", grp)); next }
  source("r/R/10_ladder.R")
  lp <- read.csv("data/datasets/ladder/ladder_preds.csv", stringsAsFactors = FALSE, check.names = FALSE)
  rk <- read.csv("data/datasets/answer_key/review_key.csv", stringsAsFactors = FALSE)
  k <- rk[match(lp$visit_id, rk$visit_id), ]
  lv <- if (grp == "age") ifelse(k$age < 35, "under_35", ifelse(k$age < 65, "35_64", "65_plus")) else as.character(k$clinic_id)
  rs <- by_difficulty(lp, lv)
  ps <- read.csv(gf, stringsAsFactors = FALSE, colClasses = setNames("character", paste0(grp, "_code")))
  m <- merge(rs, ps, by.x = c("method", "difficulty"), by.y = c("method", paste0(grp, "_code")), suffixes = c(".r", ".p"))
  d <- max(abs(m$accuracy.r - m$accuracy.p), na.rm = TRUE)
  cat(sprintf("ladder by %s: %d rows, n equal %s, max |R - Python| = %.2e\n", grp, nrow(m), all(m$n.r == m$n.p), d))
  stopifnot(nrow(m) == nrow(ps), all(m$n.r == m$n.p), d < 1e-9)
}

# 9f. Spec 030 US2: each method's spread over seeds (R summary of seed_stability.csv == Python).
sf2 <- "data/datasets/ladder/seed_stability_summary.csv"
if (file.exists(sf2)) {
  st <- read.csv("data/datasets/ladder/seed_stability.csv", stringsAsFactors = FALSE)
  rs <- do.call(rbind, lapply(split(st, st$method), function(x) data.frame(method = x$method[1],
    seed_count = nrow(x), mean_accuracy = mean(x$accuracy), sd_accuracy = if (nrow(x) > 1) sd(x$accuracy) else NA,
    min_accuracy = min(x$accuracy), max_accuracy = max(x$accuracy))))
  ps <- read.csv(sf2, stringsAsFactors = FALSE)
  m <- merge(rs, ps, by = "method", suffixes = c(".r", ".p"))
  cols <- c("mean_accuracy", "sd_accuracy", "min_accuracy", "max_accuracy")
  d <- max(sapply(cols, function(k) max(abs(m[[paste0(k, ".r")]] - m[[paste0(k, ".p")]]), na.rm = TRUE)))
  cat(sprintf("seed stability: %d methods, max |R - Python| = %.2e\n", nrow(m), d))
  stopifnot(nrow(m) == nrow(ps), all(m$seed_count.r == m$seed_count.p), d < 1e-9)
  cat("parity OK (spec 030 US2)\n")
} else cat("seed stability: skipped (run python/scripts/49_seed_stability.py)\n")

# 9d. MedGemma vs BERT (spec 004 T018): same point estimates and per-difficulty accuracy.
# Uses the real runs if present, else the simulated dry run (placeholder reader, not a result).
for (pfx in c("", "simulated_")) {
  f <- sprintf("data/datasets/ladder/%smedgemma_vs_bert_preds.csv", pfx)
  if (!file.exists(f)) next
  source("r/R/10_ladder.R")
  gp <- read.csv(f, stringsAsFactors = FALSE, check.names = FALSE)
  r <- ladder_point(gp, data.frame(method = character(), visit_id = integer()))
  py <- read.csv(sprintf("data/datasets/ladder/%smedgemma_vs_bert.csv", pfx), stringsAsFactors = FALSE, check.names = FALSE)
  m <- merge(r, py, by = "method", suffixes = c(".r", ".p"))
  cols <- c("accuracy", "stage4_recall", "unsafe_rate", "s2_rate")
  d <- max(sapply(cols, function(k) max(abs(m[[paste0(k, ".r")]] - m[[paste0(k, ".p")]]))))
  rl <- by_difficulty(gp, gp$difficulty)
  pl <- read.csv(sprintf("data/datasets/ladder/%smedgemma_vs_bert_by_difficulty.csv", pfx), stringsAsFactors = FALSE)
  ml <- merge(rl, pl, by = c("method", "difficulty"), suffixes = c(".r", ".p"))
  dl <- max(abs(ml$accuracy.r - ml$accuracy.p), abs(ml$n.r - ml$n.p))
  cat(sprintf("%smedgemma vs bert: %d methods, max |R - Python| = %.2e; by difficulty %.2e\n",
              pfx, nrow(m), d, dl))
  stopifnot(nrow(m) == nrow(py), d < 1e-9, nrow(ml) == nrow(pl), dl < 1e-9)
}

# 10. Spec 005 twins: evidence-order search, data quality, progression (R 09_spec005.R).
sp <- "data/review/simulated_reliability_5cat/phenotype_orders_split.csv"
if (file.exists(sp) && file.exists("data/review/simulated_reviewer_labels.csv") &&
    file.exists("data/datasets/prediction/pairs_algorithm_design.csv")) {
  source("r/R/09_spec005.R")
  # order search: every point estimate for all 24 orders, and the same order selected
  labels <- read.csv("data/review/simulated_reviewer_labels.csv", stringsAsFactors = FALSE)
  key <- read.csv("data/datasets/answer_key/review_key.csv", stringsAsFactors = FALSE)
  w <- reshape(labels[, c("visit_id", "reviewer", "status")], idvar = "visit_id", timevar = "reviewer", direction = "wide")
  rownames(w) <- w$visit_id; w$visit_id <- NULL; names(w) <- sub("^status\\.", "", names(w))
  r_o <- score_orders_r(key, w, read.csv(sp))
  py_o <- read.csv("data/review/simulated_reliability_5cat/phenotype_orders.csv", stringsAsFactors = FALSE)
  m <- merge(r_o, py_o, by = "order", suffixes = c(".r", ".p"))
  num <- c("select_n", "select_coverage", "select_pct_agree", "select_kappa", "holdout_n", "holdout_coverage",
           "holdout_pct_agree", "holdout_kappa", "holdout_diff_vs_human_bar")
  d <- max(sapply(num, function(k) max(abs(m[[paste0(k, ".r")]] - m[[paste0(k, ".p")]]), na.rm = TRUE)))
  same_pick <- r_o$order[r_o$selected] == py_o$order[as.logical(py_o$selected)]
  cat(sprintf("orders:       %d orders, max |R - Python| = %.2e; same order selected: %s\n", nrow(m), d, same_pick))
  stopifnot(nrow(m) == 24, d < 1e-9, same_pick)
  # data quality: every check, overall
  v <- read.csv("data/datasets/visits_structured.csv", stringsAsFactors = FALSE)
  r_dq <- run_checks_r(v, "2026-10-25")
  py_dq <- read.csv("data/datasets/data_quality/dq_overall.csv", stringsAsFactors = FALSE)
  m <- merge(r_dq, py_dq, by = "check", suffixes = c(".r", ".p"))
  ok <- all(m$n_checked.r == m$n_checked.p, m$n_fail.r == m$n_fail.p, m$status.r == m$status.p)
  cat(sprintf("data quality: %d / %d checks identical\n", sum(m$n_fail.r == m$n_fail.p), nrow(py_dq)))
  stopifnot(nrow(m) == nrow(py_dq), ok)
  # progression: same pairs, same model (glm = unpenalized logistic), same test predictions and AUROC
  for (outcome in c("algorithm_design", "truth_status")) {
    vv <- v
    if (outcome == "truth_status") vv <- merge(v, read.csv("data/datasets/answer_key/visits_truth.csv",
                                                           stringsAsFactors = FALSE)[, c("visit_id", "truth_status")])
    pr <- make_pairs_r(vv, outcome)
    pp <- read.csv(sprintf("data/datasets/prediction/pairs_%s.csv", outcome))
    pr <- pr[order(pr$visit_id), ]; pp <- pp[order(pp$visit_id), ]
    dp <- max(abs(as.matrix(pr[PRED_FEATURES]) - as.matrix(pp[PRED_FEATURES])))
    tp <- read.csv(sprintf("data/datasets/prediction/test_predictions_%s.csv", outcome))
    fr <- fit_progression_r(pp, tp$visit_id)
    mm <- merge(fr$test, tp, by = "visit_id")
    py_auc <- read.csv(sprintf("data/datasets/prediction/summary_%s.csv", outcome))$auroc
    cat(sprintf("progression (%s): %d pairs (features max diff %.1e); test p max diff %.1e; AUROC R %.6f vs Python %.6f\n",
                outcome, nrow(pr), dp, max(abs(mm$p.x - mm$p.y)), fr$auroc, py_auc))
    stopifnot(nrow(pr) == nrow(pp), all(pr$visit_id == pp$visit_id), dp < 1e-9,
              max(abs(mm$p.x - mm$p.y)) < 1e-4, abs(fr$auroc - py_auc) < 1e-4)
  }
} else cat("spec 005 twins: skipped (run python scripts 18 --simulated and 21 first)\n")

# 11. Component verdicts (spec 002 T011): R calibrate_judge per component == Python calibrate_components.
if (file.exists("data/corpus/simulated_component_gold.csv")) {
  source("r/R/05_cost_effectiveness.R")
  g <- read.csv("data/corpus/simulated_component_gold.csv", stringsAsFactors = FALSE)
  g <- g[g$verdict != "not_applicable", ]
  py <- read.csv("data/corpus/simulated_component_calibration.csv", stringsAsFactors = FALSE)
  r <- do.call(rbind, lapply(py$component, function(cp) {
    c0 <- calibrate_judge(g[g$component == cp, ])
    data.frame(component = cp, sensitivity = c0$sensitivity, specificity = c0$specificity)
  }))
  m <- merge(r, py, by = "component")
  d <- max(abs(c(m$sensitivity.x - m$sensitivity.y, m$specificity.x - m$specificity.y)))
  cat(sprintf("components:   %d components, max |R - Python| = %.2e\n", nrow(m), d))
  stopifnot(nrow(m) == 3, d < 1e-12)
} else cat("components: skipped (run python/scripts/27_component_judge.py --simulated first)\n")

cat("parity OK (all sections)\n")

# 5. Cost-effectiveness: point estimates, costs, dominance and ICER match Python.
py_ce <- "data/corpus/simulated_cost_effectiveness.csv"
if (file.exists(py_ce)) {
  source("r/R/05_cost_effectiveness.R")
  gold <- read.csv("data/corpus/simulated_judgments_gold.csv", stringsAsFactors = FALSE)
  corp <- read.csv("data/corpus/simulated_judgments_corpus.csv", stringsAsFactors = FALSE)
  bench <- read.csv("data/corpus/cost_benchmark.csv", stringsAsFactors = FALSE)
  py <- read.csv(py_ce, stringsAsFactors = FALSE)
  r <- cost_effectiveness(gold, corp, bench, 1e6)
  r <- r[match(py$method, r$method), ]
  num <- c("accuracy_est", "cost_usd", "usd_per_1k_correct", "icer_usd_per_extra_correct_note")
  d <- max(abs(as.matrix(r[num]) - as.matrix(py[num])), na.rm = TRUE)
  stopifnot(all(r$dominated == as.logical(py$dominated)))
  cat(sprintf("cost-effectiveness: max |R - Python| = %.2e over %d methods; frontier identical\n", d, nrow(py)))
  stopifnot(d < 1e-9)
} else cat("cost-effectiveness: skipped (run python scripts 14-16 first)\n")

# 6. Judge bake-off kappa (spec 002).
py_bo <- "data/corpus/simulated_judge_bakeoff.csv"
if (file.exists(py_bo) && file.exists("data/corpus/simulated_judgments_gold_all_candidates.csv")) {
  if (!exists("judge_kappa")) source("r/R/05_cost_effectiveness.R")
  bo <- read.csv(py_bo, stringsAsFactors = FALSE)
  all <- read.csv("data/corpus/simulated_judgments_gold_all_candidates.csv", stringsAsFactors = FALSE)
  rk <- sapply(bo$judge_model, function(j) judge_kappa(all[all$judge_model == j, ]))
  d <- max(abs(rk - bo$kappa))
  cat(sprintf("judge bake-off: max |R - Python| kappa = %.2e over %d judges\n", d, nrow(bo)))
  stopifnot(d < 1e-9)
}
cat("parity OK (incl. cost-effectiveness and judge bake-off)\n")

# 6. Spec 005: five categories, temporal plausibility, clinic prevalence.
source("r/R/06_validation.R")
py5 <- "data/review/simulated_reliability_5cat/methods_vs_reviewers.csv"
if (file.exists(py5) && file.exists("data/review/simulated_reviewer_labels.csv")) {
  source("r/R/04_reliability.R")
  labels <- read.csv("data/review/simulated_reviewer_labels.csv", stringsAsFactors = FALSE)
  key <- read.csv("data/datasets/answer_key/review_key.csv", stringsAsFactors = FALSE)
  py <- read.csv(py5, stringsAsFactors = FALSE)
  ms <- setdiff(py$method, "generator_chart_truth")
  compare <- setNames(lapply(ms, function(m) {
    if (startsWith(m, "ai:")) { p <- read.csv(sprintf("data/datasets/ai_predictions_%s.csv", sub("^ai:", "", m)))
      setNames(collapse5(p$pred), p$visit_id) } else setNames(collapse5(key[[m]]), key$visit_id)
  }), ms)
  labels$status <- collapse5(labels$status); key$truth_status <- collapse5(key$truth_status)
  r <- reliability_report(labels, key, compare)$methods
  r <- r[match(py$method, r$method), ]
  num <- c("coverage", "pct_agree_consensus", "kappa_vs_consensus", "weighted_kappa_vs_consensus",
           "mean_kappa_vs_each_reviewer", "unsafe_rate", "s2_rate")
  d <- max(abs(as.matrix(r[num]) - as.matrix(py[num])), na.rm = TRUE)
  cat(sprintf("five categories: max |R - Python| = %.2e over %d methods\n", d, nrow(py)))
  stopifnot(d < 1e-9)
} else cat("five categories: skipped (run 13_reliability.py --simulated)\n")

vs <- "data/datasets/visits_structured.csv"
pf <- "data/datasets/data_quality/flags_probing_chart.csv"
if (file.exists(vs) && file.exists(pf)) {
  v <- read.csv(vs, stringsAsFactors = FALSE)
  h <- data.frame(visit_id = v$visit_id, person_id = v$person_id, visit_date = v$visit_date,
                  charted = v$charted == "True" | v$charted == TRUE, max_cal_mm = v$rec_max_cal_mm,
                  rbl_pct = v$rec_rbl_pct, teeth_lost_perio = v$rec_teeth_lost_perio, status = v$probing_chart)
  r <- check_history(h, "status")
  py <- read.csv(pf, stringsAsFactors = FALSE)
  m <- merge(py, r, by = "visit_id", suffixes = c(".py", ".r"))
  bad <- sum(sapply(c(PLAUS_FLAGS, "any_flag"), function(f) sum(as.logical(m[[paste0(f, ".py")]]) != m[[paste0(f, ".r")]])))
  cat(sprintf("plausibility: %d visits, %d flag mismatches\n", nrow(m), bad))
  stopifnot(nrow(m) == nrow(py), bad == 0)
} else cat("plausibility: skipped (run 20_data_quality.py)\n")

tp <- "data/datasets/data_quality/transition_pairs_algorithm_design.csv"
if (file.exists(vs) && file.exists(tp)) {
  v <- read.csv(vs, stringsAsFactors = FALSE)
  r <- transition_pairs(v, "algorithm_design")
  py <- read.csv(tp, stringsAsFactors = FALSE)
  m <- merge(py, r, by = "visit_id", suffixes = c(".py", ".r"))
  bad <- sum(m$next_visit_id.py != m$next_visit_id.r | m$change.py != m$change.r | m$to_status.py != m$to_status.r)
  cat(sprintf("transitions:  %d pairs, %d mismatches\n", nrow(m), bad))
  stopifnot(nrow(m) == nrow(py), nrow(r) == nrow(py), bad == 0)
} else cat("transitions: skipped (run 20_data_quality.py)\n")

ps <- "data/datasets/data_quality/prevalence_by_scale.csv"
if (file.exists(vs) && file.exists(ps)) {
  v <- read.csv(vs, stringsAsFactors = FALSE)
  py <- read.csv(ps, stringsAsFactors = FALSE)
  r <- do.call(rbind, lapply(unique(py$status_col), function(m) prevalence_by_scale(v, m)))
  num <- c("n_visits", "n_known", "periodontitis", "stage3_4")
  d <- max(abs(as.matrix(r[num]) - as.matrix(py[num])), na.rm = TRUE)
  cat(sprintf("scales:       max |R - Python| = %.2e over %d rows\n", d, nrow(py)))
  stopifnot(nrow(r) == nrow(py), all(r$scale == py$scale), d < 1e-9)
} else cat("scales: skipped (run 20_data_quality.py)\n")

pp <- "data/datasets/prevalence/prevalence_by_clinic.csv"
if (file.exists(vs) && file.exists(pp)) {
  v <- read.csv(vs, stringsAsFactors = FALSE)
  py <- read.csv(pp, stringsAsFactors = FALSE)
  py <- py[py$method == "algorithm_design", ]
  r <- prevalence_by(v, "algorithm_design", by = "clinic_id")
  m <- merge(py, r, by = "clinic_id", suffixes = c(".py", ".r"))
  num <- c("n_people", "n_unknown", "periodontitis", "periodontitis_ci_low", "periodontitis_ci_high",
           "stage3_4", "stage3_4_ci_low", "stage3_4_ci_high")
  d <- max(abs(as.matrix(m[paste0(num, ".py")]) - as.matrix(m[paste0(num, ".r")])), na.rm = TRUE)
  cat(sprintf("prevalence:   max |R - Python| = %.2e over %d clinics\n", d, nrow(m)))
  stopifnot(nrow(m) == nrow(py), d < 1e-9)
} else cat("prevalence: skipped (run 19_prevalence.py)\n")
cat("parity OK (spec 005)\n")

# 7. Spec 006: derived measures and CDC/AAP from site-level charts.
if (file.exists("data/sites/parity_sites.csv") && file.exists("data/sites/derived.csv")) {
  source("r/R/07_sites.R")
  s <- read.csv("data/sites/parity_sites.csv", stringsAsFactors = FALSE)
  t <- read.csv("data/sites/parity_teeth.csv", stringsAsFactors = FALSE)
  t$missing_reason[is.na(t$missing_reason)] <- ""
  r <- derive_sites(s, t)
  py <- read.csv("data/sites/derived.csv", stringsAsFactors = FALSE)
  m <- merge(py, r, by = "visit_id", suffixes = c(".py", ".r"))
  num <- c("n_teeth_present", "teeth_lost_perio", "max_probing_depth_mm", "max_cal_mm", "bop_pct",
           "pct_teeth_ip_cal1", "n_teeth_ip_cal3", "n_teeth_ip_cal4", "n_teeth_ip_cal6", "n_teeth_ip_pd4",
           "n_teeth_ip_pd5", "n_sites_ip_pd5", "max_furcation_class", "max_mobility_degree")
  d <- max(abs(as.matrix(m[paste0(num, ".py")]) - as.matrix(m[paste0(num, ".r")])))
  cdc_bad <- sum(cdc_aap(r[match(m$visit_id, r$visit_id), ]) != m$cdc_aap_2012)
  cat(sprintf("sites:        max |R - Python| = %.2e over %d exams; CDC/AAP mismatches %d\n", d, nrow(m), cdc_bad))
  stopifnot(nrow(m) == length(unique(s$visit_id)), d < 1e-9, cdc_bad == 0)
} else cat("sites: skipped (run 22_build_sites.py)\n")
cat("parity OK (spec 006)\n")

# 12. Spec 012 judge scorecard: R 11_judge_scorecard.R == Python judge_scorecard point estimates
# (metrics vs truth and vs the judge's status, judge agreement). Real judge if run, and the simulated dry run.
for (pfx in c("", "simulated_")) {
  if (!file.exists(sprintf("data/datasets/judge/%sjudge_metrics.csv", pfx))) next
  source("r/R/11_judge_scorecard.R")
  inp <- read_judge_inputs(pfx)
  r <- judge_metrics_point(inp$answers, inp$judgments, inp$truth)
  py <- read.csv(sprintf("data/datasets/judge/%sjudge_metrics.csv", pfx), stringsAsFactors = FALSE)
  m <- merge(r, py, by = c("system", "metric"), suffixes = c(".r", ".p"))
  cols <- c("vs_truth", "vs_truth_judged", "vs_judge", "difference", "n_judged", "judged_correct",
            "verdict_sensitivity", "verdict_specificity")
  gap <- function(df, k) { x <- abs(df[[paste0(k, ".r")]] - df[[paste0(k, ".p")]]); max(ifelse(is.na(x), 0, x)) }
  same_na <- function(df, ks) all(sapply(ks, function(k) all(is.na(df[[paste0(k, ".r")]]) == is.na(df[[paste0(k, ".p")]]))))
  d <- max(sapply(cols, function(k) gap(m, k)))
  ra <- judge_agreement_point(inp$judgments, inp$truth, inp$level)
  pa <- read.csv(sprintf("data/datasets/judge/%sjudge_agreement.csv", pfx), stringsAsFactors = FALSE)
  ma <- merge(ra, pa, by = c("group", "value"), suffixes = c(".r", ".p"))
  acols <- c("n", "coverage", "agreement", "kappa")
  da <- max(sapply(acols, function(k) gap(ma, k)))
  cat(sprintf("%sjudge scorecard: %d system x metric rows, max |R - Python| = %.2e; agreement %d rows, %.2e\n",
              pfx, nrow(m), d, nrow(ma), da))
  stopifnot(nrow(m) == nrow(py), d < 1e-9, same_na(m, cols), nrow(ma) == nrow(pa), da < 1e-9, same_na(ma, acols))
  rf <- sprintf("data/datasets/judge/%sjudge_run.csv", pfx)
  if (file.exists(rf)) {   # priced at the list price the script used (judge_scorecard.LIST_USD_PER_1M_*)
    pr <- read.csv(rf, stringsAsFactors = FALSE)
    rr <- judge_run_summary(inp$judgments, 0.50, 1.50)
    mr <- merge(rr, pr, by = "kind", suffixes = c(".r", ".p"))
    rcols <- c("calls", "charts", "endpoint_errors", "gate_failures", "usd", "usd_per_chart", "latency_mean_s",
               "latency_p50_s", "latency_p95_s")
    dr <- max(sapply(rcols, function(k) gap(mr, k)))
    cat(sprintf("%sjudge run cost and speed: max |R - Python| = %.2e\n", pfx, dr))
    stopifnot(nrow(mr) == nrow(pr), dr < 1e-9)
  }
}
cat("parity OK (spec 012)\n")

# 7b. Spec 013: CAL reliability (nested ANOVA, ICCs, stage-band flips).
cg <- "data/datasets/reliability_cal/simulated_cal_charts.csv.gz"
cr <- "data/datasets/reliability_cal/simulated_cal_reliability.csv"
if (file.exists(cg) && file.exists(cr)) {
  source("r/R/12_spec013.R")
  d <- read.csv(gzfile(cg), stringsAsFactors = FALSE)
  py <- read.csv(cr); py <- py[py$sd_error_true == 0.8, ]
  r <- c(cal_nested_components(d), cal_icc(cal_nested_components(d)), stage_band_flips(d))
  num <- c("slope_mm_per_year", "var_patient", "var_tooth", "var_site", "var_error",
           "icc_patient", "icc_tooth", "icc_site", "sem_mm", "flip_rate", "down_rate")
  dd <- max(abs(unlist(r[num]) - unlist(py[num])))
  cat(sprintf("CAL reliability: max |R - Python| = %.2e\n", dd))
  stopifnot(dd < 1e-9)
} else cat("CAL reliability: skipped (run 37_cal_reliability.py)\n")
if (file.exists("data/sites/parity_sites.csv") && file.exists("data/sites/derived.csv")) {
  source("r/R/12_spec013.R")
  s <- read.csv("data/sites/parity_sites.csv", stringsAsFactors = FALSE)
  t <- read.csv("data/sites/parity_teeth.csv", stringsAsFactors = FALSE)
  t$missing_reason[is.na(t$missing_reason)] <- ""
  py <- read.csv("data/sites/derived.csv", stringsAsFactors = FALSE)
  ids <- sort(unique(t$visit_id)); S <- split(s, s$visit_id); Tt <- split(t, t$visit_id)
  variants <- list(aces = list(), aces_teeth20 = list(stage4_rule = "teeth20"),
                   aces_no_complexity = list(complexity = FALSE), aces_case_cal3 = list(case_cal = 3))
  bad <- 0
  for (v in names(variants)) {
    r <- sapply(ids, function(k) do.call(aces_exam, c(list(S[[as.character(k)]], Tt[[as.character(k)]]), variants[[v]])))
    bad <- bad + sum(r != py[[v]][match(ids, py$visit_id)])
  }
  cat(sprintf("ACES:         %d exams x %d variants, %d mismatches\n", length(ids), length(variants), bad))
  stopifnot(bad == 0)
} else cat("ACES: skipped (run 22_build_sites.py)\n")
cat("parity OK (spec 013)\n")

# Spec 026: record-mismatch rules and their scores (R 15_spec026.R vs scripts/45_case_profiles.py).
cm <- "data/datasets/case_profiles/record_mismatch.csv"
cs <- "data/datasets/case_profiles/mismatch_rule_score.csv"
if (file.exists(cm) && file.exists(cs)) {
  source("r/R/15_spec026.R")
  v <- read.csv("data/datasets/visits_structured.csv", stringsAsFactors = FALSE)
  truth <- read.csv("data/datasets/answer_key/visits_truth.csv", stringsAsFactors = FALSE)
  checks <- check_rules_026(v)
  key <- function(d) sort(paste(d$visit_id, d$rule, ifelse(is.na(d$related_visit_id), "", d$related_visit_id)))
  r_fail <- key(checks[checks$outcome == "fail", ])
  py_fail <- key(read.csv(cm, stringsAsFactors = FALSE))
  same_flags <- identical(r_fail, py_fail)
  r_s <- score_rules_026(checks, v, truth)
  py_s <- read.csv(cs, stringsAsFactors = FALSE)
  m <- merge(r_s, py_s, by = c("rule", "clinic"), suffixes = c(".r", ".p"))
  num <- c("checkable_count", "not_checkable_count", "flagged_count", "code_truth_mismatch_count",
           "true_flag_count", "precision", "recall", "only_rule_count", "injected_checkable_count",
           "injected_caught_count")
  diff_of <- function(k) {
    a <- m[[paste0(k, ".r")]]; b <- m[[paste0(k, ".p")]]
    if (any(is.na(a) != is.na(b))) return(Inf)
    if (all(is.na(a))) 0 else max(abs(a - b), na.rm = TRUE)
  }
  d <- max(sapply(num, diff_of))
  cat(sprintf("record mismatches: %d flags (same as Python: %s); %d rule x clinic scores, max |R - Python| = %.2e\n",
              length(r_fail), same_flags, nrow(m), d))
  stopifnot(same_flags, nrow(m) == nrow(py_s), nrow(r_s) == nrow(py_s), d < 1e-9)
  cat("parity OK (spec 026)\n")
} else cat("record mismatches: skipped (run 45_case_profiles.py)\n")

# Spec 029: tooth statuses and plan-copy counts (R 16_spec029.R vs scripts/47_tooth_table.py).
td <- "data/datasets/tooth_loss"
if (file.exists(file.path(td, "patient_tooth.csv"))) {
  source("r/R/16_spec029.R")
  rd <- function(n) read.csv(file.path(td, paste0(n, ".csv")), stringsAsFactors = FALSE)
  pl <- rd("procedurelog"); pc <- rd("procedurecode"); defs <- rd("definition"); ti <- rd("toothinitial")
  r_t <- tooth_status_029(pl, pc, defs, ti, rd("patient")$patnum)
  py_t <- rd("patient_tooth")
  m <- merge(r_t, py_t, by = c("patient_id", "tooth_num"), suffixes = c(".r", ".p"))
  bad_t <- sum(m$tooth_status_code.r != m$tooth_status_code.p | m$label_source_code.r != m$label_source_code.p)
  r_p <- planned_extraction_029(pl, pc, defs, rd("proctp"))
  py_p <- rd("planned_extraction")
  mp <- merge(r_p, py_p, by = "procedure_id", suffixes = c(".r", ".p"))
  bad_p <- sum(mp$plan_copy_count.r != mp$plan_copy_count.p |
               mp$is_completed.r != as.logical(mp$is_completed.p))
  cat(sprintf("tooth statuses: %d teeth, %d differ; planned extractions: %d, %d differ\n",
              nrow(m), bad_t, nrow(mp), bad_p))
  stopifnot(nrow(m) == nrow(py_t), nrow(r_t) == nrow(py_t), bad_t == 0,
            nrow(mp) == nrow(py_p), nrow(r_p) == nrow(py_p), bad_p == 0)
  cat("parity OK (spec 029)\n")
} else cat("tooth statuses: skipped (run 47_tooth_table.py)\n")

# Spec 024 US1: the PerioDx Diagnoser (Patel et al. 2022, Fig. 2), R 14_spec024.R vs periodx.chart_status on seeded
# chart inputs with gaps, and on the repo's summary chart read as the figure's inputs. Labels compared exactly.
pc <- "data/labels/periodx_chart_cases.csv"
ps <- "data/labels/periodx_summary_cases.csv"
if (file.exists(pc) && file.exists(ps)) {
  source("r/R/14_spec024.R")
  same_024 <- function(r, py, cols) {
    py[is.na(py)] <- ""; r[is.na(r)] <- ""
    sum(sapply(cols, function(k) sum(as.character(r[[k]]) != as.character(py[[k]]))))
  }
  cols_024 <- c("status", "stage", "extent", "grade", "label", "partial")
  g <- read.csv(pc, stringsAsFactors = FALSE, na.strings = "")
  r_g <- chart_status_024(g)
  bad_g <- same_024(r_g, g[cols_024], cols_024)
  s <- read.csv(ps, stringsAsFactors = FALSE, na.strings = "")
  sc <- summary_chart_024(s$max_pd_mm, s$bop_pct, s$max_cal_mm, s$rbl_pct, s$teeth_lost_perio, s$pct_teeth_involved)
  d_pct <- max(abs(sc$pct_teeth_involved - s$chart_pct_teeth_involved), na.rm = TRUE)
  same_na <- all(is.na(sc$pct_teeth_involved) == is.na(s$chart_pct_teeth_involved))
  bad_counts <- same_024(sc, s, c("interproximal_cal_teeth", "cal5_adjacent_teeth", "pd5_adjacent_teeth"))
  sc$age <- 55; sc$cigarettes_per_day <- 0; sc$diabetes <- FALSE; sc$hba1c <- NA
  bad_s <- same_024(chart_status_024(sc), s[cols_024], cols_024)
  cat(sprintf("PerioDx Diagnoser: %d chart cases, %d values differ; %d summary charts, %d inputs and %d values differ, extent share max |R - Python| = %.2e\n",
              nrow(g), bad_g, nrow(s), bad_counts, bad_s, d_pct))
  stopifnot(bad_g == 0, bad_counts == 0, bad_s == 0, same_na, d_pct < 1e-9)
  cat("parity OK (spec 024 US1)\n")
} else cat("PerioDx Diagnoser: skipped (run python/scripts/export_rules_predictions.py)\n")
# Spec 029 US3: the tooth-loss model's metrics and the stage IV counting rules (R 16_spec029.R vs
# tooth_loss_model.py / labels.py, from scripts/51_tooth_loss_model.py's outputs). Model fitting is Python only.
rt <- "data/results"
if (file.exists(file.path(rt, "synthetic_tooth_loss_eval_rows.csv"))) {
  source("r/R/16_spec029.R")
  rr <- function(n) read.csv(file.path(rt, paste0("synthetic_tooth_loss_", n, ".csv")), stringsAsFactors = FALSE)
  ev <- rr("eval_rows"); sc <- rr("scores"); cb <- rr("calibration")
  seed0 <- min(ev$generator_seed)
  sc <- sc[sc$generator_seed == seed0, ]; cb <- cb[cb$generator_seed == seed0, ]
  key <- function(d) paste(d$label_set, d$feature_set, d$model, d$eval_set, sep = "|")
  ev$k <- key(ev); sc$k <- key(sc); cb$k <- key(cb)
  near <- function(a, b) (is.na(a) & is.na(b)) | (!is.na(a) & !is.na(b) & abs(a - b) < 1e-9)
  bad <- character(0); n_checked <- 0
  for (k in unique(ev$k[ev$eval_set != "train"])) {
    g <- ev[ev$k == k, ]; s <- sc[sc$k == k, ]
    get <- function(metric, tname = "") {
      v <- s$value[s$metric == metric & (if (tname == "") is.na(s$threshold_name) | s$threshold_name == ""
                                         else s$threshold_name == tname)]
      if (length(v) == 1) v else NA_real_
    }
    sl <- calibration_slope_029(g$y, g$p)
    r <- c(auc = auc_029(g$y, g$p), brier = brier_029(g$y, g$p),
           calibration_intercept = calibration_intercept_029(g$y, g$p), calibration_slope = sl[2])
    py <- c(auc = get("auc"), brier = get("brier"), calibration_intercept = get("calibration_intercept"),
            calibration_slope = get("calibration_slope"))
    for (tn in unique(s$threshold_name[!is.na(s$threshold_name) & s$threshold_name != ""])) {
      th <- s$threshold[s$threshold_name == tn][1]
      cl <- classification_029(g$y, g$p, th)
      for (m in c("sensitivity", "specificity", "ppv", "npv")) {
        r[paste(m, tn)] <- cl[[m]]; py[paste(m, tn)] <- get(m, tn)
      }
      if (tn == "youden_train") {                       # the threshold itself, chosen on the training teeth
        tr <- ev[ev$k == paste(g$label_set[1], g$feature_set[1], g$model[1], "train", sep = "|"), ]
        r["youden"] <- youden_threshold_029(tr$y, tr$p); py["youden"] <- th
      }
    }
    ct <- calibration_table_029(g$y, g$p); pc <- cb[cb$k == k, ]
    pc <- pc[order(pc$bin_num), ]
    ok <- near(r, py[names(r)])
    ok_cal <- all(ct$tooth_count == pc$tooth_count) && all(near(ct$mean_predicted_ratio, pc$mean_predicted_ratio)) &&
      all(near(ct$observed_ratio, pc$observed_ratio))
    n_checked <- n_checked + length(r) + 1
    if (!all(ok) || !ok_cal) bad <- c(bad, paste(k, paste(names(r)[!ok], collapse = ",")))
  }
  # the stage rule: expected count and stage IV under each rule, per patient
  ps <- rr("patient_stage"); pr <- rr("predictions")
  ps <- ps[ps$generator_seed == seed0, ]
  pr <- pr[pr$feature_set == "shared" & pr$tooth_status_code %in% c("missing_at_entry", "extracted_no_dx"), ]
  bad_stage <- 0
  for (grp in split(ps, paste(ps$label_set, ps$model))) {
    p <- pr[pr$label_set == grp$label_set[1] & pr$model == grp$model[1], ]
    sums <- tapply(p$probability, p$patient_id, function(v) v, simplify = FALSE)
    for (i in seq_len(nrow(grp))) {
      probs <- sums[[as.character(grp$patient_id[i])]]
      if (is.null(probs)) probs <- numeric(0)
      e <- expected_perio_loss_029(grp$recorded_perio_count[i], probs)
      iv <- sapply(STAGE4_COUNT_RULES_029, function(rule) stage4_rule_029(rule, grp$recorded_perio_count[i],
                   grp$missing_count[i], probs, grp$true_perio_count[i]))
      py_iv <- as.logical(unlist(grp[i, paste0("is_stage4_", STAGE4_COUNT_RULES_029)]))
      at_edge <- abs(e - 5) < 1e-9                       # summation order may differ at exactly five teeth
      if (abs(e - grp$expected_perio_loss[i]) >= 1e-9 || (!at_edge && any(iv != py_iv))) bad_stage <- bad_stage + 1
    }
  }
  cat(sprintf("tooth-loss metrics: %d sets of teeth, %d values checked, %d sets differ; stage rule: %d patient rows, %d differ\n",
              length(unique(ev$k[ev$eval_set != "train"])), n_checked, length(bad), nrow(ps), bad_stage))
  if (length(bad)) print(bad)
  stopifnot(length(bad) == 0, bad_stage == 0, nrow(ps) > 0)
  cat("parity OK (spec 029 US3)\n")
} else cat("tooth-loss model: skipped (run 51_tooth_loss_model.py)\n")
