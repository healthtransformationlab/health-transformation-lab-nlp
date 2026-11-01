# Spec 023 twin: per-class metrics of the status classifier (python/health_transformation_lab_nlp/classify_status.py,
# class_metrics). Base R. Synthetic data only.
#
# y: class index per visit, 0..K-1. proba: matrix, one column per class, rows summing to 1.
# Per class, one-vs-rest: sensitivity and specificity of the arg-max class (first column wins a tie, as numpy's
# argmax), AUC by ranks with ties averaged (missing when the class or its rest is absent), Brier score (mean squared
# error of that class's probability against 0/1). Then a "mean" row over the classes present in y.

auc_rank_023 <- function(pos, score) {
  n1 <- sum(pos); n0 <- sum(!pos)
  if (n1 == 0 || n0 == 0) return(NA_real_)
  r <- rank(score)                       # ties get their average rank
  (sum(r[pos]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}

class_metrics_023 <- function(y, proba, names) {
  pred <- max.col(proba, ties.method = "first") - 1
  rows <- lapply(seq_along(names), function(k) {
    pos <- y == (k - 1); hit <- pred == (k - 1)
    data.frame(class = names[k], n_test = sum(pos),
               sensitivity = if (any(pos)) sum(hit & pos) / sum(pos) else NA_real_,
               specificity = if (any(!pos)) sum(!hit & !pos) / sum(!pos) else NA_real_,
               auc = auc_rank_023(pos, proba[, k]),
               brier = mean((proba[, k] - pos)^2),
               classes_averaged = NA_real_, stringsAsFactors = FALSE)
  })
  m <- do.call(rbind, rows)
  present <- m$n_test > 0
  avg <- function(x) { x <- x[present]; x <- x[!is.na(x)]; if (length(x)) mean(x) else NA_real_ }
  rbind(m, data.frame(class = "mean", n_test = length(y), sensitivity = avg(m$sensitivity),
                      specificity = avg(m$specificity), auc = avg(m$auc), brier = avg(m$brier),
                      classes_averaged = sum(present), stringsAsFactors = FALSE))
}
