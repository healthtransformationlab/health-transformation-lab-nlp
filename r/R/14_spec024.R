# Spec 024 twins: the PerioDx Diagnoser of Patel et al. 2022, Fig. 2 (python/health_transformation_lab_nlp/periodx.py).
# Base R. Finds periodontal status, stage, extent and grade in a synthetic chart; every threshold is the Python
# constant of the same name, citing Patel et al. 2022, Fig. 2. Synthetic data only.

BOP_LOCALIZED_PCT_024 <- 10; BOP_GENERALIZED_PCT_024 <- 30; DETECTABLE_BL_PCT_024 <- 0
ENTRY_CAL_MM_024 <- 2; ENTRY_TEETH_024 <- 2; POCKET_PD_MM_024 <- 4; MIDDLE_THIRD_BL_PCT_024 <- 33
III_IV_CAL_MM_024 <- 5; ADJACENT_TEETH_024 <- 2; FURCATION_CLASS_MIN_024 <- 2; VERTICAL_BL_MM_024 <- 3
III_IV_PD_MM_024 <- 5; OCCLUDING_PAIRS_MIN_024 <- 10; TRAUMA_TEETH_MIN_024 <- 5; TOOTH_LOSS_IV_024 <- 5
STAGE_II_BL_PCT_024 <- 15; STAGE_II_PD_MM_024 <- 5; STAGE_II_CAL_MM_024 <- 3; EXTENT_GENERALIZED_PCT_024 <- 30
GRADE_A_RATIO_024 <- 0.25; GRADE_C_RATIO_024 <- 1; HEAVY_SMOKER_PER_DAY_024 <- 10; HBA1C_C_PCT_024 <- 7
III_IV_NO_TOOTH_LOSS_024 <- 3; TEETH_FULL_024 <- 28
BL_BANDS_024 <- list("<15" = c(0, 15), "15-33" = c(15, 33), ">33" = c(33, 100))
STATUS_TO_LABEL_024 <- c(periodontal_health = "healthy", reduced_healthy_periodontium = "healthy",
                         gingival_inflammation_past_periodontitis = "gingivitis",
                         localized_gingivitis = "gingivitis", generalized_gingivitis = "gingivitis")

# Is a tooth involved at the case's stage (Fig. 2 extent box; bands contiguous: 1-2 mm is 1 <= x < 3).
tooth_involved_024 <- function(stage, cal, pd) {
  cal12 <- cal >= 1 & cal < 3; cal34 <- cal >= 3 & cal < 5
  ifelse(stage >= 3, (cal >= 5 & pd >= 4) | (cal34 & pd >= 6),
         ifelse(stage == 2, (cal34 & pd >= 4 & pd < 6) | (cal12 & pd >= 5), cal12 & pd >= 4 & pd < 5))
}

# One chart (a one-row list): list(status, stage, extent, grade, partial = character vector of fallbacks used).
# bone loss: bl (number, NA) or band (one of names(BL_BANDS_024), "" or NA).
chart_status_one_024 <- function(x) {
  used <- character(0)
  nz <- function(v) length(v) == 1 && !is.na(v)
  band <- if (nz(x$band) && x$band != "") x$band else NA
  has_bl <- !is.na(band) || nz(x$bl)
  # entry: three questions
  bl_yes <- has_bl && (!is.na(band) || x$bl > DETECTABLE_BL_PCT_024)
  entry <- bl_yes || (nz(x$interproximal_cal_teeth) && x$interproximal_cal_teeth >= ENTRY_TEETH_024) ||
    (nz(x$recession_teeth) && x$recession_teeth >= ENTRY_TEETH_024)
  if (!entry) {
    used <- c(if (!has_bl) "bone_loss_pct", if (!nz(x$interproximal_cal_teeth)) "interproximal_cal_teeth",
              if (!nz(x$recession_teeth)) "recession_teeth")
    status <- if (x$bop_pct < BOP_LOCALIZED_PCT_024) "periodontal_health" else
      if (x$bop_pct <= BOP_GENERALIZED_PCT_024) "localized_gingivitis" else "generalized_gingivitis"
    return(list(status = status, stage = NA, extent = "NA", grade = "NA", partial = used))
  }
  if (x$max_pd_mm < POCKET_PD_MM_024) {
    status <- if (x$bop_pct < BOP_LOCALIZED_PCT_024) "reduced_healthy_periodontium" else
      "gingival_inflammation_past_periodontitis"
    return(list(status = status, stage = NA, extent = "NA", grade = "NA", partial = used))
  }
  # stage: four III/IV criteria in the figure's order
  tests <- c(bone_loss_pct = if (!has_bl) NA else if (!is.na(band)) band == ">33" else x$bl > MIDDLE_THIRD_BL_PCT_024,
             cal5_adjacent_teeth = if (nz(x$cal5_adjacent_teeth)) x$cal5_adjacent_teeth >= ADJACENT_TEETH_024 else NA,
             furcation_class = if (nz(x$furcation_class)) x$furcation_class >= FURCATION_CLASS_MIN_024 else NA,
             vertical_bone_loss_mm = if (nz(x$vertical_bone_loss_mm)) x$vertical_bone_loss_mm >= VERTICAL_BL_MM_024 else NA,
             pd5_adjacent_teeth = if (nz(x$pd5_adjacent_teeth)) x$pd5_adjacent_teeth >= ADJACENT_TEETH_024 else NA)
  severe <- any(tests, na.rm = TRUE)
  if (!severe) used <- c(used, names(tests)[is.na(tests)])
  stage <- NA
  if (severe) {
    pairs <- x$occluding_pairs
    if (!nz(pairs)) { used <- c(used, "occluding_pairs"); pairs <- OCCLUDING_PAIRS_MIN_024 }
    mob <- x$mobility2_teeth
    if (pairs < OCCLUDING_PAIRS_MIN_024) stage <- 4 else {
      if (!nz(mob)) { used <- c(used, "mobility2_teeth"); mob <- 0 }
      if (mob >= TRAUMA_TEETH_MIN_024) stage <- 4 else {
        if (!nz(x$complex_rehab)) used <- c(used, "complex_rehab") else if (x$complex_rehab) stage <- 4
      }
    }
  }
  if (is.na(stage)) {
    lost <- x$teeth_lost_perio
    if (lost >= TOOTH_LOSS_IV_024) stage <- 4 else if (lost >= 1) stage <- 3 else if (severe) {
      stage <- III_IV_NO_TOOTH_LOSS_024
    } else {
      if (!has_bl) { used <- c(used, "bone_loss_pct"); bl_ii <- FALSE } else
        bl_ii <- if (!is.na(band)) band %in% c("15-33", ">33") else x$bl >= STAGE_II_BL_PCT_024
      if (!nz(x$max_cal_mm)) used <- c(used, "max_cal_mm")
      cal_ii <- nz(x$max_cal_mm) && x$max_cal_mm >= STAGE_II_CAL_MM_024
      stage <- if (bl_ii || x$max_pd_mm >= STAGE_II_PD_MM_024 || cal_ii) 2 else 1
    }
  }
  # extent
  extent <- if (isTRUE(as.logical(x$molar_incisor))) "molar_incisor" else if (!nz(x$pct_teeth_involved)) {
    used <- c(used, "pct_teeth_involved"); "not_assessable"
  } else if (x$pct_teeth_involved >= EXTENT_GENERALIZED_PCT_024) "generalized" else "localized"
  # grade: % bone loss / age, then smoking, then HbA1c
  ratio_band <- function(r) if (r < GRADE_A_RATIO_024) "low" else if (r <= GRADE_C_RATIO_024) "mid" else "high"
  grade_of <- function() {
    if (!has_bl || !nz(x$age) || x$age == 0) {
      used <<- c(used, if (!has_bl) "bone_loss_pct" else "age"); return("not_assessable")
    }
    rng <- if (!is.na(band)) BL_BANDS_024[[band]] else c(x$bl, x$bl)
    b <- ratio_band(rng[1] / x$age)
    if (ratio_band(rng[2] / x$age) != b) { used <<- c(used, "bone_loss_pct"); return("not_assessable") }
    if (b == "high") return("C")
    cig <- x$cigarettes_per_day; dm <- x$diabetes
    if (!nz(cig)) { used <<- c(used, "cigarettes_per_day"); cig <- 0 }
    if (!nz(dm)) { used <<- c(used, "diabetes"); dm <- FALSE }
    dm <- as.logical(dm)
    if (b == "low" && cig <= 0 && !dm) return("A")
    to_hba1c <- b == "low" && cig <= 0 && dm
    if (!to_hba1c && cig >= HEAVY_SMOKER_PER_DAY_024) return("C")
    if (!nz(x$hba1c)) { if (dm) used <<- c(used, "hba1c"); return("B") }
    if (x$hba1c >= HBA1C_C_PCT_024) "C" else "B"
  }
  grade <- grade_of()
  list(status = "periodontitis", stage = stage, extent = extent, grade = grade, partial = unique(used))
}

# Every row of a data frame with the PerioDxChart columns plus age, cigarettes_per_day, diabetes, hba1c
# (bone_loss_pct numeric and bone_loss_band character). Returns status, stage, extent, grade, label, partial
# (fallbacks, sorted, joined with ";").
chart_status_024 <- function(d) {
  out <- lapply(seq_len(nrow(d)), function(i) {
    r <- d[i, ]
    x <- list(bop_pct = r$bop_pct, max_pd_mm = r$max_pd_mm, bl = r$bone_loss_pct, band = r$bone_loss_band,
              max_cal_mm = r$max_cal_mm, interproximal_cal_teeth = r$interproximal_cal_teeth,
              recession_teeth = r$recession_teeth, cal5_adjacent_teeth = r$cal5_adjacent_teeth,
              pd5_adjacent_teeth = r$pd5_adjacent_teeth, furcation_class = r$furcation_class,
              vertical_bone_loss_mm = r$vertical_bone_loss_mm, occluding_pairs = r$occluding_pairs,
              mobility2_teeth = r$mobility2_teeth, complex_rehab = as.logical(r$complex_rehab),
              teeth_lost_perio = r$teeth_lost_perio, pct_teeth_involved = r$pct_teeth_involved,
              molar_incisor = r$molar_incisor, age = r$age, cigarettes_per_day = r$cigarettes_per_day,
              diabetes = as.logical(r$diabetes), hba1c = r$hba1c)
    f <- chart_status_one_024(x)
    label <- if (f$status == "periodontitis") paste0("periodontitis_stage_", f$stage) else
      unname(STATUS_TO_LABEL_024[f$status])
    data.frame(status = f$status, stage = f$stage, extent = f$extent, grade = f$grade, label = label,
               partial = paste(sort(as.character(f$partial), method = "radix"), collapse = ";"), stringsAsFactors = FALSE)
  })
  do.call(rbind, out)
}

# The repo's summary chart as the figure's inputs (periodx.chart_from_summary): worst-site values held at the
# round(share x teeth present) teeth with attachment loss; recession, furcation, vertical defects, occluding pairs,
# mobility and complexity factors not in the summary (NA).
summary_chart_024 <- function(max_pd_mm, bop_pct, max_cal_mm, rbl_pct, teeth_lost_perio, pct_teeth_involved) {
  lost <- as.integer(teeth_lost_perio)
  n <- floor(pct_teeth_involved / 100 * (TEETH_FULL_024 - lost) + 0.5)
  at <- function(ok) ifelse(is.na(n), NA, ifelse(ok, n, 0))
  data.frame(bop_pct = bop_pct, max_pd_mm = max_pd_mm, bone_loss_pct = rbl_pct, bone_loss_band = NA_character_,
             max_cal_mm = max_cal_mm,
             interproximal_cal_teeth = ifelse(is.na(max_cal_mm), NA, at(max_cal_mm > ENTRY_CAL_MM_024)),
             recession_teeth = NA, cal5_adjacent_teeth = ifelse(is.na(max_cal_mm), NA, at(max_cal_mm >= III_IV_CAL_MM_024)),
             pd5_adjacent_teeth = at(max_pd_mm > III_IV_PD_MM_024), furcation_class = NA, vertical_bone_loss_mm = NA,
             occluding_pairs = NA, mobility2_teeth = NA, complex_rehab = NA, teeth_lost_perio = lost,
             pct_teeth_involved = ifelse(is.na(n), NA, 100 * (n + lost) / TEETH_FULL_024), molar_incisor = FALSE,
             stringsAsFactors = FALSE)
}
