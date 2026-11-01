# Spec 004 US6 (#132): MedGemma accuracy per field, the R twin of
# python/health_transformation_lab_nlp/reference_answers.py (field_accuracy, wilson_ci). Base R only.
#
# status: the rung's answer (pred, after fallback to note_rules), on every reference visit.
# grade, extent: only where the reference is periodontitis, and only answers that passed the gate
# (note_rules reads neither, so a fallback row has no grade or extent and counts as wrong).
# Synthetic notes and generator truth: not evidence about real records.

FIELDS_004 <- c("status", "grade", "extent")

wilson_ci_004 <- function(k, n, z = 1.959963984540054) {
  if (n == 0) return(c(NA_real_, NA_real_))
  p <- k / n; d <- 1 + z * z / n
  c0 <- (p + z * z / (2 * n)) / d
  h <- z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
  c(max(0, c0 - h), min(1, c0 + h))
}

# details: an llm_details_*.csv; reference: answer_key/reference_answers.csv (read with na.strings = "")
field_accuracy_004 <- function(details, reference) {
  ref <- reference[order(reference$visit_id), ]
  i <- match(ref$visit_id, details$visit_id)
  if (any(is.na(i))) stop(sprintf("%d of %d reference visits have no answer in this run", sum(is.na(i)), nrow(ref)))
  det <- details[i, ]
  gate <- tolower(as.character(det$gate_ok)) == "true"
  perio <- startsWith(as.character(ref$status), "periodontitis")
  do.call(rbind, lapply(FIELDS_004, function(f) {
    if (f == "status") { pred <- as.character(det$pred); mask <- rep(TRUE, nrow(ref)) }
    else { pred <- ifelse(gate, as.character(det[[f]]), NA); mask <- perio }
    ok <- !is.na(pred) & pred == as.character(ref[[f]])
    n <- sum(mask); k <- sum(ok[mask]); ci <- wilson_ci_004(k, n)
    data.frame(field = f, n = n, correct = k, accuracy = if (n) k / n else NA_real_,
               ci_lo = ci[1], ci_hi = ci[2], stringsAsFactors = FALSE)
  }))
}
