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
