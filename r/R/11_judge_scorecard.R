# Judge scorecard in R (spec 012). Twin of python/health_transformation_lab_nlp/judge_scorecard.py: every README
# phenotyping metric per system against the truth and against the judge's own status, and the
# judge's agreement with the truth. Point estimates match Python exactly (r/tests/test_parity.R);
# the 95% ranges (bootstrap) and judge-corrected accuracy are Python's.
#
#   Rscript r/R/11_judge_scorecard.R              # data/datasets/judge/judge_*.csv (LLM judge)
#   Rscript r/R/11_judge_scorecard.R simulated    # the simulated dry run
# Base R only. Reads data/datasets/judge/{prefix}{chart_answers,judgments}.csv and the answer key.

if (!exists("unsafe_rates")) source("r/R/04_reliability.R")
if (!exists("score_run")) source("eval/score.R")

JUDGE_LEVELS <- c("L1", "L2", "L3")
JUDGE_METRICS <- c("correct", "incorrectly_assigned", "incorrectly_ruled_out", "incorrect_stage", "no_answer",
                   "unsafe_rate", "sensitivity", "specificity", "ppv", "npv", "stage4_correct",
                   paste0("correct_", JUDGE_LEVELS))

# The README's five outcomes, adding to 1 (twin of readme_results.breakdown): correct; periodontitis
# incorrectly assigned / ruled out (wrong about yes/no); incorrect stage (right yes/no, wrong status); no answer.
judge_breakdown <- function(ref, p) {
  answered <- !is.na(p)
  perio_t <- startsWith(ref, "periodontitis"); perio_p <- answered & startsWith(ifelse(answered, p, ""), "periodontitis")
  right <- answered & p == ref
  right[is.na(right)] <- FALSE
  said_no <- answered & perio_t & !perio_p; said_yes <- answered & !perio_t & perio_p
  c(correct = mean(right), incorrectly_assigned = mean(said_yes), incorrectly_ruled_out = mean(said_no),
    incorrect_stage = mean(answered & !right & !said_no & !said_yes), no_answer = mean(!answered))
}

# Every metric for one system's answers p against reference ref (aligned; ref has no NA).
judge_point <- function(ref, p, level) {
  ok <- !is.na(p) & p == ref                     # no status is wrong, as in the README
  s4 <- ref == "periodontitis_stage_4"
  sc <- score_run(ref, ifelse(is.na(p), "none", p), model_id = "judge", run_id = "judge")
  yn <- setNames(sc$value[sc$class == ""], sc$metric[sc$class == ""])
  out <- c(judge_breakdown(ref, p), unsafe_rate = unsafe_rates(ref, ifelse(is.na(p), "", p))[["unsafe_rate"]],
           sensitivity = yn[["sensitivity"]], specificity = yn[["specificity"]], ppv = yn[["ppv"]], npv = yn[["npv"]],
           stage4_correct = if (any(s4)) mean(ok[s4]) else NA_real_)
  for (lv in JUDGE_LEVELS) out[[paste0("correct_", lv)]] <- if (any(level == lv)) mean(ok[level == lv]) else NA_real_
  out
}

judge_status_of <- function(judgments) {
  st <- judgments[judgments$kind == "status" & as.logical(judgments$gate_ok) & !is.na(judgments$judge_status), ]
  setNames(st$judge_status, st$visit_id)
}

judge_metrics_point <- function(answers, judgments, truth) {
  js <- judge_status_of(judgments)
  judged <- intersect(names(truth), names(js))
  rows <- list()
  for (s in unique(answers$system)) {
    a <- answers[answers$system == s, ]
    p <- setNames(a$answer, a$visit_id); lev <- setNames(a$difficulty, a$visit_id)
    ids <- names(truth)
    t_all <- judge_point(truth[ids], p[ids], lev[ids])
    t_j <- judge_point(truth[judged], p[judged], lev[judged])
    j <- judge_point(js[judged], p[judged], lev[judged])
    # how well the judge caught this system's answers (Rogan-Gladen assumes the same rate for every system)
    vd <- judgments[judgments$kind == "verdict", ]
    a <- answers[answers$system == s & !is.na(answers$answer), ]
    v <- vd[match(paste(a$visit_id, a$answer), paste(vd$visit_id, vd$answer)), ]
    has <- v$verdict %in% c("correct", "incorrect") & as.logical(v$gate_ok) & !is.na(v$gate_ok)
    right <- a$answer == truth[as.character(a$visit_id)]; ok <- v$verdict == "correct"
    sh <- function(x, m) if (any(m)) mean(x[m]) else NA_real_
    check <- c(judged_correct = sh(ok, has), verdict_sensitivity = sh(ok, has & right),
               verdict_specificity = sh(!ok, has & !right))
    rows[[s]] <- data.frame(system = s, metric = JUDGE_METRICS, vs_truth = t_all[JUDGE_METRICS],
                            vs_truth_judged = t_j[JUDGE_METRICS], vs_judge = j[JUDGE_METRICS],
                            difference = j[JUDGE_METRICS] - t_j[JUDGE_METRICS], n_judged = length(judged),
                            judged_correct = ifelse(JUDGE_METRICS == "correct", check[["judged_correct"]], NA_real_),
                            verdict_sensitivity = ifelse(JUDGE_METRICS == "correct", check[["verdict_sensitivity"]], NA_real_),
                            verdict_specificity = ifelse(JUDGE_METRICS == "correct", check[["verdict_specificity"]], NA_real_))
  }
  out <- do.call(rbind, rows); rownames(out) <- NULL; out
}

judge_agreement_point <- function(judgments, truth, level) {
  js <- judge_status_of(judgments)[names(truth)]
  names(js) <- names(truth)
  groups <- c(list(list("all", "all", rep(TRUE, length(truth)))),
              lapply(sort(unique(truth)), function(v) list("truth_status", v, truth == v)),
              lapply(JUDGE_LEVELS, function(v) list("difficulty", v, level == v)))
  do.call(rbind, lapply(groups, function(g) {
    m <- g[[3]]; t <- truth[m]; j <- js[m]; has <- !is.na(j)
    data.frame(group = g[[1]], value = g[[2]], n = sum(m), coverage = mean(has),
               agreement = if (any(has)) mean(j[has] == t[has]) else NA_real_,
               kappa = if (any(has) && g[[1]] != "truth_status") cohen_kappa(t[has], j[has]) else NA_real_)
  }))
}

# Cost and speed of a judge run (twin of judge_scorecard.judge_run_summary): per call type and overall.
judge_run_summary <- function(judgments, usd_in, usd_out) {
  parts <- c(split(judgments, judgments$kind)[sort(unique(judgments$kind))], list(all = judgments))
  do.call(rbind, lapply(names(parts), function(k) {
    g <- parts[[k]]; err <- as.logical(g$api_error); lat <- as.numeric(g$latency_s[!err])
    tin <- sum(g$prompt_tokens); tout <- sum(g$completion_tokens); usd <- tin / 1e6 * usd_in + tout / 1e6 * usd_out
    charts <- length(unique(g$visit_id))
    q <- function(p) if (length(lat)) unname(quantile(lat, p, type = 7)) else NA_real_
    data.frame(kind = k, calls = nrow(g), charts = charts, endpoint_errors = sum(err),
               gate_failures = sum(!as.logical(g$gate_ok) & !err), usd = usd, usd_per_chart = usd / charts,
               latency_mean_s = if (length(lat)) mean(lat) else NA_real_, latency_p50_s = q(0.5), latency_p95_s = q(0.95))
  }))
}

read_judge_inputs <- function(prefix = "") {
  dir <- "data/datasets/judge/"
  na <- c("", "NA")
  answers <- read.csv(paste0(dir, prefix, "chart_answers.csv"), stringsAsFactors = FALSE, na.strings = na)
  judgments <- read.csv(paste0(dir, prefix, "judgments.csv"), stringsAsFactors = FALSE, na.strings = na)
  key <- read.csv("data/datasets/answer_key/review_key.csv", stringsAsFactors = FALSE)
  key <- key[key$visit_id %in% answers$visit_id, ]
  truth <- key$truth_status
  # spec 032 US8: a scorecard written at the five status groups has grouped answers; group the truth and the judge's
  # status the same way (a run committed before it stays at six statuses)
  if (any(answers$answer %in% "healthy_or_gingivitis")) {
    truth <- .score_group(truth, "five")
    judgments$judge_status <- .score_group(judgments$judge_status, "five")
  }
  list(answers = answers, judgments = judgments,
       truth = setNames(truth, key$visit_id), level = setNames(key$difficulty, key$visit_id))
}

if (sys.nframe() == 0) {
  args <- commandArgs(trailingOnly = TRUE)
  inp <- read_judge_inputs(if (length(args) && args[1] == "simulated") "simulated_" else "")
  m <- judge_metrics_point(inp$answers, inp$judgments, inp$truth)
  print(head(m[m$metric == "correct", ], 10))
  print(judge_agreement_point(inp$judgments, inp$truth, inp$level))
}
