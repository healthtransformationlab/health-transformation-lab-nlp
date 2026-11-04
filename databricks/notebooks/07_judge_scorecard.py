# Databricks notebook source
# MAGIC %md
# MAGIC # Judge scorecard (spec 012)
# MAGIC
# MAGIC Every README phenotyping metric for every system, against the generator's truth and against an
# MAGIC LLM judge's own reading of the same synthetic review charts, plus how often the judge agrees
# MAGIC with the truth. Metrics are computed in code (`health_transformation_lab_nlp.judge_scorecard`), never by the LLM.
# MAGIC
# MAGIC * Notes: `data/datasets/answer_key/review_key.csv`: synthetic, de-identified, through the leak gate.
# MAGIC * Judge: `judge_endpoint` (a pay-per-token serving endpoint; `none` skips the judge and publishes
# MAGIC   the truth-based metrics only). The job prints the token cost first and stops above `max_usd`.
# MAGIC * Resumes: calls already in the `fact_judge_call` table aren't asked again (endpoint errors are).
# MAGIC * Writes to the gold schema, under the gold names (spec 018, `health_transformation_lab_nlp.gold_names`): `fact_chart_answer`,
# MAGIC   `fact_judge_call`, `judge_metric`, `judge_agreement`, `judge_cost`, `deid_score` (for the dashboard's
# MAGIC   de-identification page). One MLflow trace per judge call.

# COMMAND ----------

import subprocess, sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-e", "../../python[track]"])

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("git_commit", "")   # set by the job: the commit it was deployed from
from health_transformation_lab_nlp import tracking as _tracking
_tracking.use_git_commit(dbutils)   # MLflow runs and the scripts it starts are tagged with it
dbutils.widgets.text("catalog", "health_transformation_lab")
dbutils.widgets.text("schema", "gold_perio_bench")
dbutils.widgets.text("judge_endpoint", "none")
dbutils.widgets.text("experiment_id", "")
dbutils.widgets.text("usd_per_million_in", "")    # the endpoint's list price; required to call it
dbutils.widgets.text("usd_per_million_out", "")
dbutils.widgets.text("max_usd", "5")
catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
endpoint = dbutils.widgets.get("judge_endpoint").strip()
experiment_id = dbutils.widgets.get("experiment_id")

# COMMAND ----------

import mlflow
import pandas as pd

from health_transformation_lab_nlp import gold_names
from health_transformation_lab_nlp import judge as jg
from health_transformation_lab_nlp import judge_scorecard as js
from health_transformation_lab_nlp import readme_results as rr
from health_transformation_lab_nlp import table_comments
from health_transformation_lab_nlp.paths import DEID_DIR

inp = rr.load_inputs()
answers = js.chart_answers(inp)
queue = js.judge_queue(answers, inp["key"])
table = lambda name: f"{catalog}.{schema}.{name}"  # noqa: E731

# Spec 018: earlier calls still under the old name would be missed and paid for again: migrate them first.
old = {n: spark.table(table(n)).columns for n in ("judgments", "fact_judge_call") if spark.catalog.tableExists(table(n))}
if ("copy", "judgments", "fact_judge_call") in gold_names.migration_plan(old):    # once merged, both exist: carry on
    raise RuntimeError(f"{table('judgments')} holds judge calls not yet in fact_judge_call: run Load results first "
                       "(its migrate_gold_names task moves them), then this job")

done = None
if spark.catalog.tableExists(table("fact_judge_call")) and endpoint != "none":
    done = js.reusable(gold_names.from_gold(spark.table(table("fact_judge_call")).toPandas(), "fact_judge_call"), endpoint)

if endpoint in ("", "none"):
    print("judge_endpoint is none: publishing truth-based metrics only")
    judgments = js.empty_judgments()
else:
    usd_in, usd_out = dbutils.widgets.get("usd_per_million_in"), dbutils.widgets.get("usd_per_million_out")
    if not usd_in or not usd_out:
        raise ValueError("set usd_per_million_in and usd_per_million_out to the endpoint's current list prices")
    judged = set() if done is None else {js._key(d) for d in done.itertuples()}
    todo = queue[[js._key(r) not in judged for r in queue.itertuples()]]
    est = js.estimate_cost(todo, float(usd_in), float(usd_out))
    print(f"{est['calls']} calls to judge on {endpoint}, ~{est['input_tokens']:,.0f} input tokens, ~US${est['usd']:.2f}")
    if est["usd"] > float(dbutils.widgets.get("max_usd")):
        raise ValueError(f"estimated cost over max_usd; not calling {endpoint}")

    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    token = w.config.authenticate()["Authorization"].split(" ", 1)[1]
    judge = jg.OpenAIJudge(model=endpoint, base_url=f"{w.config.host.rstrip('/')}/serving-endpoints", api_key=token)

    if experiment_id:
        mlflow.set_experiment(experiment_id=experiment_id)

    def trace(r, v):
        with mlflow.start_span(name=f"judge_{r.kind}") as span:
            span.set_inputs({"visit_id": int(r.visit_id), "kind": r.kind, "answer": r.answer,
                             "note_text": r.note_text, "endpoint": endpoint})
            span.set_outputs({"verdict": v.verdict, "judge_status": v.supported_status, "quote": v.quote,
                              "gate_ok": v.quote_ok, "error": v.error})
            span.set_attributes({"data": "synthetic", "kind": "LLM judgment"})

    judgments = js.run_judge(queue, judge, endpoint=endpoint, done=done, trace=trace if experiment_id else None)

metrics = js.judge_metrics(inp, answers, judgments)
agreement = js.judge_agreement(inp, judgments)
usd_in_, usd_out_ = (float(dbutils.widgets.get(k) or d) for k, d in
                     (("usd_per_million_in", js.LIST_USD_PER_1M_IN), ("usd_per_million_out", js.LIST_USD_PER_1M_OUT)))
run = js.judge_run_summary(judgments, usd_in_, usd_out_)
if len(judgments) and experiment_id:      # cost and speed next to the traces, as MLflow metrics
    with mlflow.start_run(run_name=f"judge_scorecard {endpoint}"):
        mlflow.set_tags({"data": "synthetic", "kind": "LLM judgment", "endpoint": endpoint})
        t = run.set_index("kind").loc["all"]
        mlflow.log_metrics({k: float(t[k]) for k in ("usd", "usd_per_chart", "calls", "endpoint_errors",
                                                     "gate_failures", "latency_mean_s", "latency_p95_s")})
        a = agreement.set_index(["group", "value"]).loc[("all", "all")]
        mlflow.log_metrics({"judge_agreement": float(a["agreement"]), "judge_kappa": float(a["kappa"])})

# COMMAND ----------

def save(pdf: pd.DataFrame, name: str):
    # typed schema from pandas: with no judge run the judge columns are all empty and Spark can't infer them
    pdf = gold_names.to_gold(pdf, name)
    spark.createDataFrame(js.spark_rows(pdf), schema=js.spark_ddl(pdf)).write.mode("overwrite") \
         .option("overwriteSchema", "true").saveAsTable(table(name))
    table_comments.apply(spark, table(name))  # noqa: F821  spec 034: an overwrite drops the comments

save(answers, "fact_chart_answer")
if len(judgments) or not spark.catalog.tableExists(table("fact_judge_call")):   # keep an earlier run's calls
    save(judgments, "fact_judge_call")
save(metrics, "judge_metric")
save(agreement, "judge_agreement")
save(run, "judge_cost")
save(pd.read_csv(DEID_DIR / "scores.csv").assign(group=lambda d: d["method"].map(rr.deid_group)), "deid_score")

label = "LLM judgment" if len(judgments) else "no judge run"
print(f"{label}: {len(judgments)} calls; tables written to {catalog}.{schema}")
display(agreement)
display(metrics[metrics.metric == "correct"].sort_values("vs_truth", ascending=False))
