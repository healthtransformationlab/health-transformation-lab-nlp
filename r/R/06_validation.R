# Spec 005 twins of python/health_transformation_lab_nlp/plausibility.py and prevalence.py.
# Base R. r/tests/test_parity.R checks they match Python.

PERIO_LABELS6 <- c("healthy", "gingivitis", "periodontitis_stage_1", "periodontitis_stage_2",
                   "periodontitis_stage_3", "periodontitis_stage_4")
PLAUS_FLAGS <- c("cal_drop", "rbl_drop", "teeth_regained", "perio_resolved", "stage_drop")

# visits: visit_id, person_id, visit_date, charted, max_cal_mm, rbl_pct, teeth_lost_perio, <status_col>
check_history <- function(visits, status_col = "status", cal_tol = 1.5, rbl_tol = 5) {
  v <- visits[order(visits$person_id, as.character(visits$visit_date), visits$visit_id), ]
  out <- data.frame(visit_id = v$visit_id, person_id = v$person_id)
  for (f in PLAUS_FLAGS) out[[f]] <- FALSE
  last <- NULL; best <- NA; pid <- NA
  charted <- as.logical(v$charted)
  for (i in seq_len(nrow(v))) {
    if (!identical(v$person_id[i], pid)) { pid <- v$person_id[i]; last <- NULL; best <- NA }
    if (isTRUE(charted[i]) && !is.na(v$max_cal_mm[i])) {
      if (!is.null(last)) {
        out$cal_drop[i] <- last[1] - v$max_cal_mm[i] > cal_tol
        out$rbl_drop[i] <- last[2] - v$rbl_pct[i] > rbl_tol
        out$teeth_regained[i] <- v$teeth_lost_perio[i] < last[3]
      }
      last <- c(v$max_cal_mm[i], v$rbl_pct[i], v$teeth_lost_perio[i])
    }
    s <- v[[status_col]][i]
    if (s %in% PERIO_LABELS6) {
      rank <- match(s, PERIO_LABELS6) - 1
      if (!is.na(best) && best >= 2) {
        out$perio_resolved[i] <- rank < 2
        out$stage_drop[i] <- rank < best
      }
      best <- if (is.na(best)) rank else max(best, rank)
    }
  }
  out$any_flag <- apply(out[PLAUS_FLAGS], 1, any)
  out
}

wilson_ci <- function(k, n, z = 1.959963984540054) {
  if (n == 0) return(c(NA_real_, NA_real_))
  p <- k / n; d <- 1 + z^2 / n
  c0 <- (p + z^2 / (2 * n)) / d
  h <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / d
  c(max(0, c0 - h), min(1, c0 + h))
}

prevalence_by <- function(visits, status_col, by = NULL) {
  known <- c(PERIO_LABELS6, "healthy_gingivitis")
  perio <- PERIO_LABELS6[3:6]; severe <- PERIO_LABELS6[5:6]
  v <- visits[order(visits$person_id, as.character(visits$visit_date)), ]
  k <- v[v[[status_col]] %in% known, ]
  last <- k[!duplicated(k$person_id, fromLast = TRUE), ]
  people <- v[!duplicated(v$person_id), ]
  groups <- if (is.null(by)) list(all = TRUE) else sort(unique(people[[by]]))
  rows <- lapply(groups, function(g) {
    ppl <- if (is.null(by)) people else people[people[[by]] == g, ]
    lk <- if (is.null(by)) last else last[last[[by]] == g, ]
    n <- nrow(lk); k1 <- sum(lk[[status_col]] %in% perio); k2 <- sum(lk[[status_col]] %in% severe)
    c1 <- wilson_ci(k1, n); c2 <- wilson_ci(k2, n)
    data.frame(group = if (is.null(by)) "all" else g, n_people = n, n_unknown = nrow(ppl) - n,
               periodontitis = if (n) k1 / n else NA, periodontitis_ci_low = c1[1], periodontitis_ci_high = c1[2],
               stage3_4 = if (n) k2 / n else NA, stage3_4_ci_low = c2[1], stage3_4_ci_high = c2[2])
  })
  out <- do.call(rbind, rows)
  if (!is.null(by)) names(out)[1] <- by
  out
}

# Spec 032 US1 (#440): twin of prevalence.prevalence_by_group. Person-level share in each status group of
# `grouping`, Wilson 95% interval, one row per group (and per <by> value). Uses group_status from r/R/labels.R.
prevalence_by_group <- function(visits, status_col, grouping = "six", by = NULL) {
  known <- c(PERIO_LABELS6, "healthy_gingivitis")
  groups_of <- STATUS_GROUPINGS[[grouping]]
  v <- visits[order(visits$person_id, as.character(visits$visit_date)), ]
  k <- v[v[[status_col]] %in% known, ]
  last <- k[!duplicated(k$person_id, fromLast = TRUE), ]
  last$.group <- group_status(last[[status_col]], grouping)
  people <- v[!duplicated(v$person_id), ]
  parts <- if (is.null(by)) list("all") else as.list(sort(unique(people[[by]])))
  rows <- lapply(parts, function(g) {
    ppl <- if (is.null(by)) people else people[people[[by]] == g, ]
    lk <- if (is.null(by)) last else last[last[[by]] == g, ]
    n <- nrow(lk)
    do.call(rbind, lapply(groups_of, function(grp) {
      kk <- sum(lk$.group == grp); ci <- wilson_ci(kk, n)
      data.frame(group = g, grouping = grouping, status_group = grp, n_people = n, n_unknown = nrow(ppl) - n,
                 n_in_group = kk, share = if (n) kk / n else NA_real_, share_ci_low = ci[1], share_ci_high = ci[2])
    }))
  })
  out <- do.call(rbind, rows)
  if (!is.null(by)) names(out)[1] <- by
  out
}

# Spec 013 G8: twin of plausibility.transition_pairs (five categories; first visit 365-730 days later;
# pairs with therapy in between dropped).
PERIO_FIVE <- c("healthy_gingivitis", PERIO_LABELS6[3:6])
transition_pairs <- function(visits, status_col = "status", min_days = 365, max_days = 730) {
  v <- visits[visits[[status_col]] %in% PERIO_LABELS6, ]
  v$date <- as.Date(v$visit_date)
  v$five <- ifelse(v[[status_col]] %in% c("healthy", "gingivitis"), "healthy_gingivitis", v[[status_col]])
  v$treated <- v$treated_before == TRUE | v$treated_before == "True"
  v <- v[order(v$person_id, v$date, v$visit_id), ]
  rows <- list()
  for (g in split(v, factor(v$person_id, levels = unique(v$person_id)))) {
    n <- nrow(g)
    for (i in seq_len(n)) for (j in seq_len(n)[seq_len(n) > i]) {
      d <- as.numeric(g$date[j] - g$date[i])
      if (d > max_days) break
      if (d < min_days) next
      if (g$treated[j] && !g$treated[i]) break
      ra <- match(g$five[i], PERIO_FIVE); rb <- match(g$five[j], PERIO_FIVE)
      rows[[length(rows) + 1]] <- data.frame(person_id = g$person_id[i], visit_id = g$visit_id[i],
        next_visit_id = g$visit_id[j], days = d, from_status = g$five[i], to_status = g$five[j],
        change = if (rb < ra) "better" else if (rb > ra) "worse" else "same")
      break
    }
  }
  if (length(rows)) do.call(rbind, rows) else data.frame()
}

# Spec 013 G7: twin of completeness.complete_cases and prevalence_by_scale.
CHART_INPUTS <- c("rec_max_cal_mm", "rec_bop_pct", "rec_max_probing_depth_mm", "rec_teeth_lost_perio")
is_missing <- function(x) is.na(x) | as.character(x) %in% c("unknown", "")
complete_cases <- function(v) {
  charted <- v$charted == TRUE | v$charted == "True"
  chart_ok <- charted & !Reduce(`|`, lapply(CHART_INPUTS, function(c) is_missing(v[[c]])))
  v[!is_missing(v$exam_form) & !is_missing(v$proc_codes_planned) & chart_ok & !is_missing(v$notes), ]
}
prevalence_by_scale <- function(v, status_col) {
  rev <- v$in_review == TRUE | v$in_review == "True"
  scales <- list(all_visits = v, complete_cases = complete_cases(v), reference_set = v[rev, ])
  do.call(rbind, lapply(names(scales), function(nm) {
    s <- scales[[nm]][[status_col]]; k <- s[!is_missing(s)]
    data.frame(scale = nm, status_col = status_col, n_visits = length(s), n_known = length(k),
               periodontitis = mean(k %in% PERIO_LABELS6[3:6]), stage3_4 = mean(k %in% PERIO_LABELS6[5:6]))
  }))
}
