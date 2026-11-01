# Quantitative validation in R: reviewer reliability, and every method /
# the rule-based algorithm / each AI model against the reviewers.
# Twin of python/health_transformation_lab_nlp/reliability.py; r/tests/test_parity.R checks they agree.
# Base R only. The `irr` package (kappam.fleiss, kappa2) gives the same
# Fleiss and Cohen numbers if you prefer it; see the cross-check at the bottom.
#
#   Rscript r/R/04_reliability.R             # real reviewers: data/review/reviewer_labels.csv
#   Rscript r/R/04_reliability.R simulated   # dry run: simulated_reviewer_labels.csv

STATUS_ORDER <- c("healthy", "gingivitis", "periodontitis_stage_1",
                  "periodontitis_stage_2", "periodontitis_stage_3", "periodontitis_stage_4")
# Five-category reports (spec 005): healthy + gingivitis collapsed into one label.
FIVE_ORDER <- c("healthy_gingivitis", STATUS_ORDER[3:6])
VALID_STATUS <- c(STATUS_ORDER, "healthy_gingivitis")
collapse5 <- function(s) { s[s %in% c("healthy", "gingivitis")] <- "healthy_gingivitis"; s }

cohen_kappa <- function(a, b) {
  n <- length(a); if (!n) return(NA_real_)
  cats <- union(a, b)
  po <- mean(a == b)
  pe <- sum(vapply(cats, function(c) mean(a == c) * mean(b == c), numeric(1)))
  if (pe == 1) NA_real_ else (po - pe) / (1 - pe)
}

weighted_kappa <- function(a, b, order = NULL) {
  if (is.null(order)) order <- if (any(c(a, b) == "healthy_gingivitis", na.rm = TRUE)) FIVE_ORDER else STATUS_ORDER
  keep <- a %in% order & b %in% order
  x <- match(a[keep], order); y <- match(b[keep], order); k <- length(order)
  if (!length(x)) return(NA_real_)
  O <- table(factor(x, 1:k), factor(y, 1:k)); O <- matrix(O, k, k)
  W <- outer(1:k, 1:k, function(i, j) (i - j)^2 / (k - 1)^2)
  E <- outer(rowSums(O), colSums(O)) / sum(O)
  1 - sum(W * O) / sum(W * E)
}

fleiss_kappa <- function(wide) {
  w <- wide[stats::complete.cases(wide), , drop = FALSE]
  m <- as.matrix(w); n <- ncol(m)
  cats <- sort(unique(as.vector(m)))
  counts <- sapply(cats, function(c) rowSums(m == c))
  if (is.null(dim(counts))) counts <- matrix(counts, nrow = nrow(m))
  p_j <- colSums(counts) / sum(counts)
  P_i <- rowSums(counts * (counts - 1)) / (n * (n - 1))
  (mean(P_i) - sum(p_j^2)) / (1 - sum(p_j^2))
}

consensus <- function(wide) {
  apply(wide, 1, function(r) {
    r <- r[!is.na(r)]; if (!length(r)) return("no_consensus")
    tab <- sort(table(r), decreasing = TRUE)
    if (length(tab) > 1 && tab[[1]] == tab[[2]]) "no_consensus" else names(tab)[1]
  })
}


# ---- spec 002: clinical severity of errors (DRAFT matrix; see python/health_transformation_lab_nlp/harm.py)
severity <- function(truth, pred) {
  # the collapsed label grades like "healthy"; healthy_or_gingivitis is the five-group name (spec 032 US8)
  merged <- c("healthy_gingivitis", "healthy_or_gingivitis")
  truth[truth %in% merged] <- "healthy"; pred[pred %in% merged] <- "healthy"
  t <- match(truth, STATUS_ORDER) - 1; p <- match(pred, STATUS_ORDER) - 1
  ifelse(t == p, "S0",
  ifelse(t < 2 & p < 2, "S0",
  ifelse(t >= 2 & p < 2, ifelse(t >= 4, "S2", "S1"),
  ifelse(t < 2 & p >= 2, "S1",
  ifelse(p < t, ifelse(t >= 4, "S1", "S0"),
  ifelse(p - t == 1, "S0", "S1"))))))
}

unsafe_rates <- function(truth, pred) {
  graded <- c(VALID_STATUS, "healthy_or_gingivitis")
  ok <- truth %in% graded & pred %in% graded
  if (!any(ok)) return(c(unsafe_rate = NA_real_, s2_rate = NA_real_))
  s <- severity(truth[ok], pred[ok])
  c(unsafe_rate = mean(s != "S0"), s2_rate = mean(s == "S2"))
}

by_level <- function(key, cons_df, compare) {
  lev <- setNames(key$difficulty, key$visit_id)[as.character(cons_df$visit_id)]
  cons <- cons_df$consensus
  do.call(rbind, lapply(names(compare), function(nm) {
    s <- unname(compare[[nm]][as.character(cons_df$visit_id)])
    per <- sapply(c("L1", "L2", "L3"), function(l) {
      ok <- lev == l & cons %in% VALID_STATUS & s %in% VALID_STATUS
      if (any(ok, na.rm = TRUE)) mean(s[ok %in% TRUE] == cons[ok %in% TRUE]) else NA_real_
    })
    data.frame(method = nm, level = c("L1", "L2", "L3", "macro"),
               pct_agree_consensus = c(per, mean(per, na.rm = TRUE)))
  }))
}

reliability_report <- function(labels, key, compare) {
  wide <- reshape(labels[, c("visit_id", "reviewer", "status")], idvar = "visit_id",
                  timevar = "reviewer", direction = "wide")
  rownames(wide) <- wide$visit_id; wide$visit_id <- NULL
  names(wide) <- sub("^status\\.", "", names(wide))
  wide <- wide[order(as.numeric(rownames(wide))), , drop = FALSE]
  ids <- rownames(wide)
  cons <- consensus(wide)
  both_k <- function(a, b) { ok <- a %in% VALID_STATUS & b %in% VALID_STATUS; cohen_kappa(a[ok], b[ok]) }

  methods <- c(list(generator_chart_truth = setNames(key$truth_status, key$visit_id)), compare)
  rows <- lapply(names(methods), function(nm) {
    s <- unname(methods[[nm]][ids]); has <- s %in% VALID_STATUS
    ok <- cons %in% VALID_STATUS & has
    data.frame(method = nm, coverage = mean(has), n = sum(ok),
               pct_agree_consensus = mean(s[ok] == cons[ok]),
               kappa_vs_consensus = cohen_kappa(s[ok], cons[ok]),
               weighted_kappa_vs_consensus = weighted_kappa(s[ok], cons[ok]),
               mean_kappa_vs_each_reviewer = mean(sapply(names(wide), function(r) both_k(s, wide[[r]])), na.rm = TRUE),
               unsafe_rate = unsafe_rates(cons[ok], s[ok])[["unsafe_rate"]],
               s2_rate = unsafe_rates(cons[ok], s[ok])[["s2_rate"]])
  })
  list(n_visits = nrow(wide), n_reviewers = ncol(wide), fleiss_kappa = fleiss_kappa(wide),
       consensus_reached = mean(cons %in% VALID_STATUS), methods = do.call(rbind, rows),
       consensus = data.frame(visit_id = as.integer(ids), consensus = cons))
}

# AI vs humans acceptance test (Python: reliability.agreement_vs_humans). Point
# estimates match Python exactly; the bootstrap CI uses R's RNG, so it matches
# only approximately.
agreement_vs_humans <- function(wide, compare, n_boot = 500, seed = 0, margin = 0.05) {
  revs <- names(wide); pairs <- combn(revs, 2, simplify = FALSE)
  both_k <- function(a, b) { ok <- a %in% VALID_STATUS & b %in% VALID_STATUS; cohen_kappa(a[ok], b[ok]) }
  bar <- function(w) mean(sapply(pairs, function(p) both_k(w[[p[1]]], w[[p[2]]])), na.rm = TRUE)
  vs_h <- function(s, w) mean(sapply(revs, function(r) both_k(s, w[[r]])), na.rm = TRUE)
  ids <- rownames(wide)
  al <- lapply(compare, function(s) unname(s[ids]))
  pb <- bar(wide)
  rows <- list(data.frame(rater = "humans (mean pairwise)", kind = "bar", mean_kappa_vs_humans = pb,
                          diff_vs_human_bar = NA, ci_low = NA, ci_high = NA, margin = NA, verdict = NA))
  for (r in revs) {
    o <- setdiff(revs, r)
    rows[[length(rows) + 1]] <- data.frame(rater = paste0("human:", r), kind = "human",
      mean_kappa_vs_humans = mean(sapply(o, function(x) both_k(wide[[r]], wide[[x]])), na.rm = TRUE),
      diff_vs_human_bar = NA, ci_low = NA, ci_high = NA, margin = NA, verdict = NA)
  }
  set.seed(seed); n <- nrow(wide)
  boots <- matrix(NA_real_, n_boot, length(al))
  for (b in seq_len(n_boot)) {
    idx <- sample.int(n, n, replace = TRUE)
    wb <- wide[idx, , drop = FALSE]; bb <- bar(wb)
    boots[b, ] <- sapply(al, function(s) vs_h(s[idx], wb) - bb)
  }
  for (j in seq_along(al)) {
    p <- vs_h(al[[j]], wide)
    ci <- if (n_boot) unname(quantile(boots[, j], c(0.025, 0.975), na.rm = TRUE, type = 7)) else c(NA, NA)
    v <- if (!n_boot || is.na(ci[1])) NA else if (ci[1] > -margin) "non-inferior" else if (ci[2] < -margin) "inferior" else "inconclusive"
    rows[[length(rows) + 1]] <- data.frame(rater = names(al)[j], kind = "method", mean_kappa_vs_humans = p,
      diff_vs_human_bar = p - pb, ci_low = ci[1], ci_high = ci[2], margin = margin, verdict = v)
  }
  do.call(rbind, rows)
}

if (sys.nframe() == 0) {
  sim <- identical(commandArgs(trailingOnly = TRUE)[1], "simulated")
  prefix <- if (sim) "simulated_" else ""
  labels <- read.csv(file.path("data/review", paste0(prefix, "reviewer_labels.csv")), stringsAsFactors = FALSE)
  key <- read.csv("data/datasets/answer_key/review_key.csv", stringsAsFactors = FALSE)
  m <- c("notes", "exam_form", "proc_codes_completed", "proc_codes_planned",
         "proc_dx_completed", "proc_dx_planned", "probing_chart", "radiograph_ai", "algorithm_v0", "algorithm_design")
  compare <- setNames(lapply(m, function(x) setNames(key[[x]], key$visit_id)), m)
  for (f in sort(Sys.glob("data/datasets/ai_predictions_*.csv"))) {
    p <- read.csv(f, stringsAsFactors = FALSE)
    compare[[paste0("ai:", sub("^ai_predictions_(.*)\\.csv$", "\\1", basename(f)))]] <- setNames(p$pred, p$visit_id)
  }
  rep <- reliability_report(labels, key, compare)
  out <- file.path("data/review", paste0(prefix, "reliability"))
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  write.csv(rep$methods, file.path(out, "methods_vs_reviewers_R.csv"), row.names = FALSE)
  w <- reshape(labels[, c("visit_id", "reviewer", "status")], idvar = "visit_id", timevar = "reviewer", direction = "wide")
  rownames(w) <- w$visit_id; w$visit_id <- NULL; names(w) <- sub("^status\\.", "", names(w))
  w <- w[order(as.numeric(rownames(w))), , drop = FALSE]
  vh <- agreement_vs_humans(w, compare)
  write.csv(vh, file.path(out, "agreement_vs_humans_R.csv"), row.names = FALSE)
  cat("\nacceptance test (agree with reviewers at least as much as they agree with each other):\n")
  print(vh[, c("rater", "mean_kappa_vs_humans", "diff_vs_human_bar", "ci_low", "ci_high", "verdict")],
        digits = 3, row.names = FALSE)
  if (sim) cat("*** SIMULATED REVIEWERS: pipeline dry run, not a result ***\n")
  cat(sprintf("charts=%d reviewers=%d Fleiss kappa=%.3f consensus reached=%.1f%%\n",
              rep$n_visits, rep$n_reviewers, rep$fleiss_kappa, 100 * rep$consensus_reached))
  print(rep$methods, digits = 3, row.names = FALSE)

  if (requireNamespace("irr", quietly = TRUE)) {   # optional cross-check
    w <- reshape(labels[, c("visit_id", "reviewer", "status")], idvar = "visit_id", timevar = "reviewer", direction = "wide")
    cat("irr::kappam.fleiss:", round(irr::kappam.fleiss(w[stats::complete.cases(w), -1])$value, 3), "\n")
  }
}
