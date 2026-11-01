# Spec 026 twins: record-mismatch rules and their scores (python/health_transformation_lab_nlp/case_profile.py).
# Base R. A failed rule is a record mismatch to recheck, usually a coding or charting gap. Synthetic data only.

LABELS_026 <- c("healthy", "gingivitis", paste0("periodontitis_stage_", 1:4))
RULES_026 <- c("code_vs_chart", "code_above_chart", "code_below_chart", "no_periodontal_care",
               "code_vs_radiograph", "stage_drop")
PERIO_026 <- 2; STAGE2_026 <- 3; STAGE3_026 <- 4
HIGH_CODE_MAX_CAL_MM_026 <- 3; HIGH_CODE_RBL_PCT_026 <- 15; HIGH_CODE_MAX_PD_MM_026 <- 6
LOW_CODE_CAL_MM_026 <- 3; LOW_CODE_RBL_PCT_026 <- 15; CHART_STEPS_026 <- 1

rank_026 <- function(s) match(s, LABELS_026) - 1   # NA for unknown or missing

# Each visit's highest earlier periodontitis code (rank and visit), by date as check_history orders visits.
peaks_026 <- function(v) {
  o <- v[order(v$person_id, v$visit_date, v$visit_id), ]
  peak_rank <- rep(NA_real_, nrow(o)); peak_visit <- rep(NA_real_, nrow(o))
  best_r <- NA; best_v <- NA; pid <- NULL
  for (i in seq_len(nrow(o))) {
    if (is.null(pid) || o$person_id[i] != pid) { pid <- o$person_id[i]; best_r <- NA; best_v <- NA }
    peak_rank[i] <- best_r; peak_visit[i] <- best_v
    r <- rank_026(o$proc_dx_completed[i])
    if (!is.na(r) && r >= PERIO_026 && (is.na(best_r) || r > best_r)) { best_r <- r; best_v <- o$visit_id[i] }
  }
  data.frame(visit_id = o$visit_id, peak_rank = peak_rank, peak_visit = peak_visit)
}

# One row per (visit, rule): visit_id, rule, outcome, related_visit_id.
check_rules_026 <- function(v) {
  v <- merge(v, peaks_026(v), by = "visit_id")
  code <- rank_026(v$proc_dx_completed); chart <- rank_026(v$probing_chart); rad <- rank_026(v$radiograph_ai)
  charted <- as.logical(v$charted)
  cal <- v$rec_max_cal_mm; rbl <- v$rec_rbl_pct; pdmm <- v$rec_max_probing_depth_mm; lost <- v$rec_teeth_lost_perio
  care <- pmax(ifelse(is.na(rank_026(v$proc_codes_completed)), 0, rank_026(v$proc_codes_completed)),
               ifelse(is.na(rank_026(v$proc_codes_planned)), 0, rank_026(v$proc_codes_planned))) >= PERIO_026
  out_of <- function(checkable, fail) ifelse(is.na(code), "no_code", ifelse(!checkable, "not_checkable",
                                                                            ifelse(fail, "fail", "pass")))
  ok <- function(x) !is.na(x) & x
  rules <- list(
    code_vs_chart = out_of(charted & !is.na(chart), ok(abs(code - chart) > CHART_STEPS_026)),
    code_above_chart = out_of(charted & !is.na(cal) & !is.na(rbl) & !is.na(pdmm) & !is.na(lost),
                              ok(code >= STAGE3_026 & cal < HIGH_CODE_MAX_CAL_MM_026 & rbl < HIGH_CODE_RBL_PCT_026 &
                                 lost == 0 & pdmm < HIGH_CODE_MAX_PD_MM_026)),
    code_below_chart = out_of(charted & !is.na(cal) & !is.na(rbl),
                              ok(code < PERIO_026 & (cal >= LOW_CODE_CAL_MM_026 | rbl >= LOW_CODE_RBL_PCT_026))),
    no_periodontal_care = out_of(rep(TRUE, nrow(v)), ok(code >= PERIO_026 & !care)),
    code_vs_radiograph = out_of(!is.na(rad), ok(code < PERIO_026 & rad >= STAGE2_026)),
    stage_drop = out_of(!is.na(v$peak_rank), ok(code < v$peak_rank)))
  do.call(rbind, lapply(RULES_026, function(r) data.frame(
    visit_id = v$visit_id, rule = r, outcome = rules[[r]],
    related_visit_id = if (r == "stage_drop") ifelse(is.na(code), NA, v$peak_visit) else NA,
    stringsAsFactors = FALSE)))
}

scores_026 <- function(g) {
  checkable <- g$outcome %in% c("fail", "pass"); flagged <- g$outcome == "fail"; true <- flagged & g$wrong
  n_flag <- sum(flagged); n_wrong <- sum(checkable & g$wrong)
  data.frame(checkable_count = sum(checkable), not_checkable_count = sum(g$outcome == "not_checkable"),
             flagged_count = n_flag, code_truth_mismatch_count = n_wrong, true_flag_count = sum(true),
             precision = if (n_flag > 0) sum(true) / n_flag else NA,
             recall = if (n_wrong > 0) sum(true) / n_wrong else NA,
             only_rule_count = sum(flagged & g$n_failed == 1),
             injected_checkable_count = sum(checkable & g$injected), injected_caught_count = sum(flagged & g$injected))
}

# Each rule, and any_rule, scored against the truth over the visits it can check; clinic "All" and each clinic.
score_rules_026 <- function(checks, v, truth) {
  t <- truth[match(v$visit_id, truth$visit_id), ]
  own_wrong <- v$proc_dx_completed != "unknown" & v$proc_dx_completed != t$truth_status
  injected <- !is.na(t$record_error) & t$record_error != ""
  idx <- function(ids) match(ids, v$visit_id)
  checks$wrong <- own_wrong[idx(checks$visit_id)]
  rel <- checks$rule == "stage_drop" & !is.na(checks$related_visit_id)
  checks$wrong[rel] <- checks$wrong[rel] | own_wrong[idx(checks$related_visit_id[rel])]
  checks$injected <- injected[idx(checks$visit_id)]
  checks$clinic <- as.character(v$clinic_id[idx(checks$visit_id)])
  n_failed <- tapply(checks$outcome == "fail", checks$visit_id, sum)
  checks$n_failed <- as.vector(n_failed[as.character(checks$visit_id)])
  coded <- !is.na(rank_026(v$proc_dx_completed))
  nf <- as.vector(n_failed[as.character(v$visit_id)])
  anyr <- data.frame(visit_id = v$visit_id, outcome = ifelse(!coded, "no_code", ifelse(nf > 0, "fail", "pass")),
                     wrong = own_wrong, injected = injected, clinic = as.character(v$clinic_id), n_failed = nf,
                     stringsAsFactors = FALSE)
  rows <- list()
  for (r in c(RULES_026, "any_rule")) {
    g <- if (r == "any_rule") anyr else checks[checks$rule == r, ]
    for (cl in c("All", sort(unique(g$clinic)))) {
      part <- if (cl == "All") g else g[g$clinic == cl, ]
      rows[[length(rows) + 1]] <- cbind(data.frame(rule = r, clinic = cl, stringsAsFactors = FALSE), scores_026(part))
    }
  }
  do.call(rbind, rows)
}
