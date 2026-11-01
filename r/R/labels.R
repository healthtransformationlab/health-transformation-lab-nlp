# Periodontal status from a perio chart. R twin of python/health_transformation_lab_nlp/labels.py.
# Same rules, same thresholds; r/tests/test_parity.R checks the two agree.
# Follows the AAP staging and grading worksheet (docs/staging_grading.md):
# https://www.perio.org/wp-content/uploads/2019/08/Staging-and-Grading-Periodontitis.pdf
#   1. initial stage from interdental CAL; RBL only when CAL is NA
#   2. tooth loss: 1-4 teeth -> at least III, >= 5 -> IV
#   3. complexity shifts up: PD > 4 -> >= II; PD >= 6, vertical defect >= 3 mm,
#      furcation class >= II -> >= III; at III, complex rehabilitation
#      (mobility >= 2, < 20 teeth, other) -> IV

PERIO_LABELS <- c("healthy", "gingivitis", "periodontitis_stage_1",
                  "periodontitis_stage_2", "periodontitis_stage_3", "periodontitis_stage_4")

# Spec 032 US1 (#440): status groupings, twin of labels.GROUPINGS / group_status. `six` the six statuses (default),
# `five` healthy and gingivitis merged, `three` that merge plus stage I-II as `mild` and III-IV as `severe`.
# Anything that is not a status (no answer, NA, "unknown", a group name already) keeps its value.
STATUS_GROUPINGS <- list(
  six = PERIO_LABELS,
  five = c("healthy_or_gingivitis", PERIO_LABELS[3:6]),
  three = c("healthy_or_gingivitis", "mild", "severe"))
.status_group_of <- function(grouping) {
  hg <- c(healthy = "healthy_or_gingivitis", gingivitis = "healthy_or_gingivitis",
          healthy_gingivitis = "healthy_or_gingivitis")
  switch(grouping, six = character(0), five = hg,
         three = c(hg, setNames(c("mild", "mild", "severe", "severe"), PERIO_LABELS[3:6])),
         stop("unknown status grouping '", grouping, "'; one of ", paste(names(STATUS_GROUPINGS), collapse = ", ")))
}
group_status <- function(status, grouping = "five") {
  # Vectorised. The group each status falls in under `grouping`.
  m <- .status_group_of(grouping)
  out <- as.character(status)
  hit <- !is.na(out) & out %in% names(m)
  out[hit] <- unname(m[out[hit]])
  out
}

label_chart <- function(max_probing_depth_mm, bop_pct, max_cal_mm, rbl_pct, teeth_lost_perio = 0,
                        vertical_defect_mm = 0, furcation_class = 0, mobility_degree = 0,
                        remaining_teeth = NA, complex_rehab = FALSE) {
  # Vectorised over equal-length inputs; scalars recycle.
  n <- length(bop_pct)
  rep_n <- function(x) if (length(x) == 1) rep(x, n) else x
  pd <- rep_n(max_probing_depth_mm); cal <- rep_n(max_cal_mm); rbl <- rep_n(rbl_pct)
  lost <- rep_n(ifelse(is.na(teeth_lost_perio), 0, teeth_lost_perio))
  vd <- rep_n(vertical_defect_mm); fc <- rep_n(furcation_class); mob <- rep_n(mobility_degree)
  rem <- rep_n(remaining_teeth); rehab <- rep_n(complex_rehab)
  stopifnot(all(!(is.na(cal) & is.na(rbl))), all(bop_pct >= 0 & bop_pct <= 100),
            all(is.na(rbl) | (rbl >= 0 & rbl <= 100)))

  no_loss <- ifelse(!is.na(cal), cal < 1, rbl <= 0) & lost == 0
  by_cal <- ifelse(cal <= 2, 1, ifelse(cal <= 4, 2, 3))
  by_rbl <- ifelse(rbl < 15, 1, ifelse(rbl <= 33, 2, 3))
  stage <- ifelse(!is.na(cal), by_cal, by_rbl)
  stage <- ifelse(lost > 0, pmax(stage, 3), stage)
  stage[lost >= 5] <- 4
  stage <- ifelse(pd > 4, pmax(stage, 2), stage)
  stage <- ifelse(pd >= 6 | vd >= 3 | fc >= 2, pmax(stage, 3), stage)
  stage <- ifelse(stage == 3 & (rehab | mob >= 2 | (!is.na(rem) & rem < 20)), 4, stage)

  ifelse(no_loss, ifelse(bop_pct >= 10, "gingivitis", "healthy"),
         paste0("periodontitis_stage_", stage))
}

# ---- rules baseline: regex over the note text, then label_chart -------------
.num <- "(\\d+(?:\\.\\d+)?)"
.patterns <- list(
  pd   = c(paste0("PD max ", .num), paste0("probing depths up to ", .num), paste0("deepest pocket ", .num)),
  bop  = c(paste0("BOP ", .num, "%"), paste0("bleeding at ", .num, "%")),
  cal  = c(paste0("CAL ", .num), paste0("attachment loss ", .num)),
  rbl  = c(paste0("RBL ~?", .num, "%"), paste0(.num, "% horizontal bone loss")),
  lost = c(paste0(.num, " teeth previously lost"))
)

.find <- function(text, key) {
  for (p in .patterns[[key]]) {
    m <- regmatches(text, regexec(p, text, ignore.case = TRUE, perl = TRUE))[[1]]
    if (length(m) >= 2) return(as.numeric(m[2]))
  }
  NA_real_
}

rules_predict <- function(texts) {
  vapply(texts, function(t) {
    neg <- grepl("no BOP|BOP neg|no bleeding on probing", t, ignore.case = TRUE)
    z <- function(x) ifelse(is.na(x), 0, x)
    bop <- if (neg) 0 else z(.find(t, "bop"))
    cal <- .find(t, "cal"); rbl <- .find(t, "rbl")
    if (is.na(cal) && is.na(rbl)) rbl <- 0
    label_chart(z(.find(t, "pd")), min(bop, 100), cal, if (is.na(rbl)) NA else min(rbl, 100),
                z(.find(t, "lost")))
  }, character(1), USE.NAMES = FALSE)
}

# Ladder interface (base R, no tidymodels needed).
rung_rules <- function(train, test) list(pred = rules_predict(test$note_text), proba = NULL)
