# The model ladder against the synthetic truth (spec 002 T015): R twin of
# python/health_transformation_lab_nlp/ladder_eval.py, point estimates only (bootstrap CIs differ by RNG).
# Reads data/datasets/ladder/ladder_preds.csv and ladder_proba.csv written by
# python/scripts/28_ladder_vs_truth.py; r/tests/test_parity.R checks R == Python. Base R only.

source("r/R/04_reliability.R")   # severity(), unsafe_rates()

STAGE4 <- "periodontitis_stage_4"

rules_override <- function(pred, rules_pred, labels = STAGE4) ifelse(rules_pred %in% labels, rules_pred, pred)

expected_calibration_error <- function(truth, proba, n_bins = 10) {
  conf <- apply(proba, 1, max)
  top <- colnames(proba)[max.col(proba, ties.method = "first")]
  correct <- top == truth
  bins <- pmin(as.integer(conf * n_bins), n_bins - 1)
  sum(vapply(unique(bins), function(b) {
    k <- bins == b
    abs(mean(conf[k]) - mean(correct[k])) * mean(k)
  }, numeric(1)))
}

ladder_point <- function(preds, proba_long) {
  truth <- preds$truth
  methods <- setdiff(names(preds), c("visit_id", "truth", "difficulty"))
  s4 <- truth == STAGE4
  do.call(rbind, lapply(methods, function(m) {
    p <- preds[[m]]; ok <- p == truth
    u <- unsafe_rates(truth, p)
    pr <- proba_long[proba_long$method == m, ]
    ece <- if (nrow(pr)) {
      pr <- pr[match(preds$visit_id, pr$visit_id), ]
      # five status groups since spec 032 US8 (healthy and gingivitis added up), else the six statuses
      cols <- if ("healthy_or_gingivitis" %in% names(pr)) c("healthy_or_gingivitis", STATUS_ORDER[3:6]) else STATUS_ORDER
      expected_calibration_error(truth, as.matrix(pr[, cols]))
    } else NA_real_
    data.frame(method = m, accuracy = mean(ok), stage4_recall = mean(ok[s4]),
               unsafe_rate = u[["unsafe_rate"]], s2_rate = u[["s2_rate"]], ece = ece, stringsAsFactors = FALSE)
  }))
}

# Accuracy per method and difficulty level (python ladder_eval.by_difficulty; 29_medgemma_vs_bert.py).
by_difficulty <- function(preds, level) {
  methods <- setdiff(names(preds), c("visit_id", "truth", "difficulty"))
  do.call(rbind, lapply(methods, function(m) do.call(rbind, lapply(sort(unique(level)), function(lv) {
    k <- level == lv
    data.frame(method = m, difficulty = lv, n = sum(k), accuracy = mean(preds[[m]][k] == preds$truth[k]),
               stringsAsFactors = FALSE)
  }))))
}
