# Spec 029 twins: tooth statuses and planned-extraction copy counts (python/health_transformation_lab_nlp/tooth_loss.py).
# Base R. Reads the Open Dental columns scripts/47_tooth_table.py writes. Synthetic data only.

# The declared diagnosis lookup (open_dental.DIAGNOSIS_LOOKUP): every item of either list -> perio / other
PERIO_ITEMS_029 <- c("Periodontal disease, advanced", "Periodontal disease, moderate",
                     "Periodontitis, stage III", "Periodontitis, stage IV")
OTHER_ITEMS_029 <- c("Caries, non-restorable", "Fractured tooth", "Orthodontic extraction", "Other",
                     "Caries, non-restorable (2017 list)", "Fracture (2017 list)", "Orthodontic (2017 list)",
                     "Other (2017 list)")
EXTRACTIONS_029 <- c("D7140", "D7210")
DEFCAT_DIAGNOSIS_029 <- 16
PLANNED_029 <- 1; COMPLETE_029 <- 2; EXISTING_OTHER_029 <- 4

extractions_029 <- function(pl, pc, defs) {
  codes <- pc$codenum[pc$proccode %in% EXTRACTIONS_029]
  e <- pl[pl$codenum %in% codes, ]
  e$tooth_num <- suppressWarnings(as.integer(e$toothnum))
  e <- e[!is.na(e$tooth_num) & e$tooth_num >= 1 & e$tooth_num <= 32, ]
  d <- defs[defs$category == DEFCAT_DIAGNOSIS_029, ]
  item <- d$itemname[match(e$dx, d$defnum)]
  e$dx_class <- ifelse(item %in% PERIO_ITEMS_029, "perio", ifelse(item %in% OTHER_ITEMS_029, "other", "none"))
  e
}

# One row per patient and tooth: patient_id, tooth_num, tooth_status_code, label_source_code.
# Completed extraction first, then missing at entry, then a planned extraction with a diagnosis, else present.
tooth_status_029 <- function(pl, pc, defs, ti, patients) {
  e <- extractions_029(pl, pc, defs)
  grid <- expand.grid(tooth_num = 1:32, patient_id = sort(patients))[, c("patient_id", "tooth_num")]
  key <- paste(grid$patient_id, grid$tooth_num)
  status <- rep("present", nrow(grid)); source <- rep("none", nrow(grid))

  p <- e[e$procstatus == PLANNED_029 & e$dx_class != "none", ]
  p <- p[order(as.Date(p$datetp), p$procnum), ]
  p <- p[!duplicated(paste(p$patnum, p$tooth_num)), ]
  i <- match(paste(p$patnum, p$tooth_num), key)
  status[i] <- paste0("planned_", p$dx_class); source[i] <- "planned"

  entry <- ti[ti$initialtype == 0, ]
  away <- e[e$procstatus == EXISTING_OTHER_029, ]
  i <- match(c(paste(entry$patnum, entry$toothnum), paste(away$patnum, away$tooth_num)), key)
  i <- i[!is.na(i)]
  status[i] <- "missing_at_entry"; source[i] <- "none"

  done <- e[e$procstatus == COMPLETE_029, ]
  done <- done[order(as.Date(done$datecomplete), done$procnum), ]
  done <- done[!duplicated(paste(done$patnum, done$tooth_num)), ]
  i <- match(paste(done$patnum, done$tooth_num), key)
  status[i] <- paste0("extracted_", ifelse(done$dx_class == "none", "no_dx", done$dx_class))
  source[i] <- ifelse(done$dx_class == "none", "none", "completed")

  data.frame(grid, tooth_status_code = status, label_source_code = source, stringsAsFactors = FALSE)
}

# One row per extraction ever on a plan: procedure_id, plan_copy_count, is_completed.
planned_extraction_029 <- function(pl, pc, defs, tp) {
  e <- extractions_029(pl, pc, defs)
  e <- e[e$procstatus %in% c(PLANNED_029, COMPLETE_029), ]
  n <- table(tp$procnumorig)
  e <- e[as.character(e$procnum) %in% names(n), ]
  out <- data.frame(procedure_id = e$procnum, plan_copy_count = as.integer(n[as.character(e$procnum)]),
                    is_completed = e$procstatus == COMPLETE_029)
  out[order(out$procedure_id), ]
}

# ---- Spec 029 US3 (#371): the tooth-loss model's metrics and the stage IV counting rules
# Twins of tooth_loss_model.py (auc, brier, classification, youden_threshold, calibration_slope,
# calibration_intercept, calibration_table) and labels.py (expected_perio_loss, stage4_tooth_counts, stage4_rule).
# Model fitting stays Python only (FR-005). Base R.
# Spec 032 US4 (#443): teeth_lt_20 and pairs_lt_10 call stage IV from the teeth left (third molars aside).

CLIP_029 <- 1e-8
N_BINS_029 <- 10
STAGE4_COUNT_RULES_029 <- c("recorded_only", "every_missing", "expected_perio_loss", "truth", "teeth_lt_20",
                            "pairs_lt_10")
STAGE4_TEETH_LEFT_MIN_029 <- 20   # fewer than 20 teeth left: stage IV
STAGE4_PAIRS_MIN_029 <- 10        # fewer than 10 occluding pairs: stage IV (periodx.OCCLUDING_PAIRS_MIN)
THIRD_MOLARS_029 <- c(1, 16, 17, 32)

auc_029 <- function(y, p) {
  pos <- p[y == 1]; neg <- p[y == 0]
  if (!length(pos) || !length(neg)) return(NA_real_)
  r <- rank(c(pos, neg))
  (sum(r[seq_along(pos)]) - length(pos) * (length(pos) + 1) / 2) / (length(pos) * length(neg))
}

brier_029 <- function(y, p) mean((p - y)^2)

classification_029 <- function(y, p, threshold) {
  pred <- p >= threshold
  tp <- sum(pred & y == 1); fp <- sum(pred & y == 0); fn <- sum(!pred & y == 1); tn <- sum(!pred & y == 0)
  ratio <- function(a, b) if (b > 0) a / b else NA_real_
  list(tp = tp, fp = fp, fn = fn, tn = tn, sensitivity = ratio(tp, tp + fn), specificity = ratio(tn, tn + fp),
       ppv = ratio(tp, tp + fp), npv = ratio(tn, tn + fn))
}

logit_029 <- function(p) { q <- pmin(pmax(p, CLIP_029), 1 - CLIP_029); log(q / (1 - q)) }

# Newton steps for the logistic regression of y on logit(p): intercept and slope, or the intercept with logit(p) as
# an offset. NA when it can't be fitted (one class, no spread, separation).
newton_029 <- function(y, lp, slope, max_iter = 100, tol = 1e-10) {
  if (all(y == y[1]) || (slope && diff(range(lp)) == 0)) return(c(NA_real_, NA_real_))
  a <- 0; b <- 1
  for (it in seq_len(max_iter)) {
    mu <- 1 / (1 + exp(-(a + b * lp)))
    w <- mu * (1 - mu); r <- y - mu
    if (slope) {
      g0 <- sum(r); g1 <- sum(r * lp)
      h00 <- sum(w); h01 <- sum(w * lp); h11 <- sum(w * lp * lp)
      det <- h00 * h11 - h01 * h01
      da <- (h11 * g0 - h01 * g1) / det; db <- (h00 * g1 - h01 * g0) / det
    } else {
      da <- sum(r) / sum(w); db <- 0
    }
    if (!is.finite(da) || !is.finite(db)) return(c(NA_real_, NA_real_))
    a <- a + da; b <- b + db
    if (max(abs(da), abs(db)) < tol) return(c(a, b))
  }
  c(NA_real_, NA_real_)
}

calibration_slope_029 <- function(y, p) newton_029(y, logit_029(p), TRUE)
calibration_intercept_029 <- function(y, p) newton_029(y, logit_029(p), FALSE)[1]

# The smallest predicted probability that maximises sensitivity + specificity - 1 (p >= it is positive).
youden_threshold_029 <- function(y, p) {
  o <- order(p); ps <- p[o]; ys <- y[o]
  u <- sort(unique(p))
  pos <- sum(ys); neg <- length(ys) - pos
  if (pos == 0 || neg == 0) return(NA_real_)
  i <- findInterval(u, ps, left.open = TRUE)            # teeth below each threshold
  tp <- pos - c(0, cumsum(ys))[i + 1]
  fp <- (length(ys) - i) - tp
  j <- tp / pos + (neg - fp) / neg - 1
  u[which.max(j)]
}

calibration_table_029 <- function(y, p) {
  b <- pmin(floor(p * N_BINS_029), N_BINS_029 - 1)
  do.call(rbind, lapply(0:(N_BINS_029 - 1), function(k) {
    m <- b == k; n <- sum(m)
    data.frame(bin_num = k, tooth_count = n, mean_predicted_ratio = if (n) mean(p[m]) else NA_real_,
               observed_ratio = if (n) mean(y[m]) else NA_real_)
  }))
}

expected_perio_loss_029 <- function(recorded_perio, unlabelled_probs) recorded_perio + sum(unlabelled_probs)

# (teeth, occluding pairs) left, from the tooth numbers present; third molars left out; upper t opposes lower 33 - t
stage4_tooth_counts_029 <- function(teeth_present) {
  kept <- setdiff(unique(as.integer(teeth_present)), THIRD_MOLARS_029)
  c(teeth = length(kept), pairs = sum(vapply(2:15, function(k) (k %in% kept) && ((33 - k) %in% kept), logical(1))))
}

stage4_rule_029 <- function(rule, recorded_perio, missing, unlabelled_probs = numeric(0), true_perio = NA,
                            teeth_present = NULL) {
  if (!rule %in% STAGE4_COUNT_RULES_029) stop("unknown stage IV counting rule ", rule)
  if (rule %in% c("teeth_lt_20", "pairs_lt_10")) {
    if (is.null(teeth_present)) stop("the ", rule, " rule needs teeth_present")
    n <- stage4_tooth_counts_029(teeth_present)
    return(if (rule == "teeth_lt_20") n[["teeth"]] < STAGE4_TEETH_LEFT_MIN_029 else n[["pairs"]] < STAGE4_PAIRS_MIN_029)
  }
  n <- switch(rule, recorded_only = recorded_perio, every_missing = missing,
              expected_perio_loss = expected_perio_loss_029(recorded_perio, unlabelled_probs), truth = true_perio)
  n >= 5
}
