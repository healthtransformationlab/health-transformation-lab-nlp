# Spec 032 twins, R side. Base R. r/tests/test_parity.R checks they match Python.
#
# US3 (#442): how the diagnosis-code source reads a visit with no gum-disease code (phenotype.read_dx_code; parity cases from python/scripts/export_rules_predictions.py).
# "no_answer" (default): the code alone, as sources.read_proc_dx reads it. "healthy_or_gingivitis": a visit with a
# treatment plan but no gum-disease code (ICD-10-CM K05) reads as ABSENT_CODE_STATUS_032, "healthy", which here
# stands for healthy or gingivitis: the code list can't tell them apart. A visit with no plan stays no answer.

ABSENT_CODE_RULES_032 <- c("no_answer", "healthy_or_gingivitis")
ABSENT_CODE_STATUS_032 <- "healthy"

blank_032 <- function(v) is.na(v) | trimws(as.character(v)) %in% c("", "(none)")

# sources.read_proc_dx, vectorised
read_proc_dx_032 <- function(v) {
  v <- ifelse(is.na(v), "", as.character(v))
  out <- rep("unknown", length(v))
  out[v == "Z01.20"] <- "healthy"
  out[startsWith(v, "K05.0") | startsWith(v, "K05.1")] <- "gingivitis"
  perio <- startsWith(v, "K05.3") & nchar(v) == 7
  sev <- substr(v, 7, 7)
  out[perio & sev == "1"] <- "periodontitis_stage_1"
  out[perio & sev == "2"] <- "periodontitis_stage_2"
  out[perio & sev == "3"] <- "periodontitis_stage_3"
  out
}

read_dx_code_032 <- function(dx, plan, absent_code = "no_answer") {
  stopifnot(absent_code %in% ABSENT_CODE_RULES_032)
  out <- read_proc_dx_032(dx)
  if (absent_code == "no_answer") return(out)
  d <- ifelse(is.na(dx), "", trimws(as.character(dx)))
  absent <- out == "unknown" & !startsWith(d, "K05") & !blank_032(plan)
  out[absent] <- ABSENT_CODE_STATUS_032
  out
}
