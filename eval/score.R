# Shared scorer (R). Twin of eval/score.py: same metrics, same output schema.
# Base R only so it runs anywhere, including Posit and Databricks R notebooks.

PERIO_LABELS <- c("healthy", "gingivitis", "periodontitis_stage_1",
                  "periodontitis_stage_2", "periodontitis_stage_3", "periodontitis_stage_4")

# Spec 032 US1: status groupings, the same as r/R/labels.R and labels.GROUPINGS (copied so this file stays
# standalone; the parity test checks five and three against eval/score.py).
SCORE_GROUPINGS <- list(
  six = PERIO_LABELS,
  five = c("healthy_or_gingivitis", PERIO_LABELS[3:6]),
  three = c("healthy_or_gingivitis", "mild", "severe"))
.score_group_of <- list(
  six = character(0),
  five = c(healthy = "healthy_or_gingivitis", gingivitis = "healthy_or_gingivitis",
           healthy_gingivitis = "healthy_or_gingivitis"),
  three = c(healthy = "healthy_or_gingivitis", gingivitis = "healthy_or_gingivitis",
            healthy_gingivitis = "healthy_or_gingivitis", periodontitis_stage_1 = "mild",
            periodontitis_stage_2 = "mild", periodontitis_stage_3 = "severe", periodontitis_stage_4 = "severe"))
.score_group <- function(x, grouping) {
  m <- .score_group_of[[grouping]]
  hit <- !is.na(x) & x %in% names(m)
  x[hit] <- unname(m[x[hit]])
  x
}

.f1 <- function(y_true, y_pred, lab) {
  tp <- sum(y_true == lab & y_pred == lab)
  fp <- sum(y_true != lab & y_pred == lab)
  fn <- sum(y_true == lab & y_pred != lab)
  if (tp == 0) return(0)
  p <- tp / (tp + fp); r <- tp / (tp + fn)
  2 * p * r / (p + r)
}

.auroc <- function(truth, score) {
  # Mann-Whitney U formulation; ties count half. Matches sklearn roc_auc_score.
  pos <- score[truth]; neg <- score[!truth]
  if (!length(pos) || !length(neg)) return(NA_real_)
  r <- rank(c(pos, neg))
  (sum(r[seq_along(pos)]) - length(pos) * (length(pos) + 1) / 2) / (length(pos) * length(neg))
}

score_run <- function(y_true, y_pred, proba = NULL, model_id, language = "r", run_id = NULL, grouping = "six") {
  # proba: n x 6 matrix in PERIO_LABELS column order, or NULL.
  # grouping (spec 032 US1): six (default), five or three; F1 per group, periodontitis yes/no unchanged.
  if (!grouping %in% names(SCORE_GROUPINGS))
    stop("unknown status grouping '", grouping, "'; one of ", paste(names(SCORE_GROUPINGS), collapse = ", "))
  y_true <- .score_group(as.character(y_true), grouping); y_pred <- .score_group(as.character(y_pred), grouping)
  labels <- SCORE_GROUPINGS[[grouping]]; perio <- unique(.score_group(PERIO_LABELS[3:6], grouping))
  if (is.null(run_id)) run_id <- paste0(model_id, "-", paste(sample(c(0:9, letters[1:6]), 8, TRUE), collapse = ""))
  ts <- format(Sys.time(), "%Y-%m-%dT%H:%M:%S+00:00", tz = "UTC")
  rows <- list()
  add <- function(metric, value, cls = "") {
    rows[[length(rows) + 1]] <<- data.frame(run_id = run_id, model_id = model_id, language = language,
      metric = metric, class = cls, value = value, n_test = length(y_true), timestamp = ts)
  }
  f1s <- vapply(labels, function(l) .f1(y_true, y_pred, l), numeric(1))
  add("macro_f1", mean(f1s))
  for (l in labels) add("f1", f1s[[l]], l)

  t <- y_true %in% perio; p <- y_pred %in% perio
  tp <- sum(t & p); fn <- sum(t & !p); tn <- sum(!t & !p); fp <- sum(!t & p)
  add("sensitivity", if (tp + fn) tp / (tp + fn) else NA_real_)
  add("specificity", if (tn + fp) tn / (tn + fp) else NA_real_)
  add("ppv", if (tp + fp) tp / (tp + fp) else NA_real_)   # of the "periodontitis" calls, the share right
  add("npv", if (tn + fn) tn / (tn + fn) else NA_real_)   # of the "no periodontitis" calls, the share right
  add("auroc", if (is.null(proba)) NA_real_ else .auroc(t, rowSums(proba[, 3:6, drop = FALSE])))
  do.call(rbind, rows)
}

write_run <- function(results, results_dir) {
  dir.create(results_dir, recursive = TRUE, showWarnings = FALSE)
  out <- file.path(results_dir, paste0(results$run_id[1], ".csv"))
  write.csv(results, out, row.names = FALSE, na = "")
  out
}
