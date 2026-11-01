"""Databricks Asset Bundle: dev / uat / prod targets are complete and consistent.
(`databricks bundle validate` needs workspace auth; CI runs it per target.)"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VAR = re.compile(r"\$\{var\.([a-z_]+)\}")
GOLD_CATALOG = "${resources.schemas.perio_bench_gold.catalog_name}"
GOLD_SCHEMA = "${resources.schemas.perio_bench_gold.name}"
LANDING = "${resources.volumes.perio_bench_data.schema_name}"
LEGACY_TARGETS = ("dev",)   # spec 022: the only target that deployed <layer>_dental_omop_perio (spec 021)
WIDGET = re.compile(r"""widgets\.(?:text|dropdown)\(\s*["']([a-z_]+)["']|CREATE WIDGET TEXT ([a-z_]+)""")


def _load():
    root = yaml.safe_load((ROOT / "databricks.yml").read_text())
    jobs = {}
    for inc in root.get("include", []):
        for f in ROOT.glob(inc):
            for k, j in yaml.safe_load(f.read_text())["resources"].get("jobs", {}).items():
                jobs[k] = (j, f.parent)
    return root, jobs


def _tasks(root, jobs):
    for name, (j, base) in jobs.items():
        for t in j["tasks"]:
            yield name, t, base
    for tgt in root["targets"].values():
        for name, j in tgt.get("resources", {}).get("jobs", {}).items():
            for t in j["tasks"]:
                yield name, t, ROOT


def test_three_targets_with_expected_modes():
    root, _ = _load()
    t = root["targets"]
    assert set(t) == {"dev", "uat", "prod"}
    # No development mode in dev: it prefixes every name ([dev <user>] jobs,
    # dev_<user>_ catalogs/schemas/models). The workspace separates environments.
    assert "mode" not in t["dev"] and t["dev"]["default"]
    assert t["dev"]["presets"] == {"trigger_pause_status": "PAUSED"}
    assert "name_prefix" not in root.get("presets", {})
    for env in ("uat", "prod"):
        assert t[env]["mode"] == "production"
        assert "service_principal_name" in t[env]["run_as"]
        assert "/Shared/" in t[env]["workspace"]["root_path"]


def test_every_target_uses_the_same_catalog_and_legacy_domain():
    # dev, uat and prod are separate workspaces, so the Unity Catalog names are the
    # same everywhere: catalog health_transformation_lab, schemas <layer>_<bench> (spec 022). legacy_domain
    # names the old <layer>_dental_omop_perio schemas dev keeps until they are retired.
    root, _ = _load()
    d = {k: v["default"] for k, v in root["variables"].items() if "default" in v}
    assert "domain" not in root["variables"]
    places = {env: (t.get("variables", {}).get("catalog", d["catalog"]),
                    t.get("variables", {}).get("legacy_domain", d["legacy_domain"])) for env, t in root["targets"].items()}
    assert set(places.values()) == {("health_transformation_lab", "dental_omop_perio")}, places


def test_every_variable_used_is_defined():
    root, _ = _load()
    defined = set(root["variables"])
    text = (ROOT / "databricks.yml").read_text() + "".join(
        f.read_text() for inc in root["include"] for f in ROOT.glob(inc))
    assert set(VAR.findall(text)) <= defined
    for env, t in root["targets"].items():
        assert set(t.get("variables", {})) <= defined, env


def test_notebooks_exist_and_take_the_parameters_passed():
    root, jobs = _load()
    seen = 0
    for name, task, base in _tasks(root, jobs):
        nb = (base / task["notebook_task"]["notebook_path"]).resolve()
        assert nb.exists(), f"{name}: {nb}"
        widgets = {a or b for a, b in WIDGET.findall(nb.read_text())}
        params = set(task["notebook_task"].get("base_parameters", {}))
        assert params <= widgets, f"{name}: {params - widgets} not widgets in {nb.name}"
        seen += 1
    assert seen >= 3


def test_job_notebooks_have_no_placeholders_left():
    """A literal <catalog>.<schema> in a cell runs as SQL and fails the whole job."""
    root, jobs = _load()
    for name, task, base in _tasks(root, jobs):
        cells = (base / task["notebook_task"]["notebook_path"]).resolve().read_text().split("# COMMAND ----------")
        code = [c for c in cells
                if not c.replace("# Databricks notebook source", "").strip().startswith("# MAGIC %md")]
        assert not any("<catalog>" in c or "<schema>" in c for c in code), name


def test_gpu_jobs_run_on_serverless_gpu_in_every_target():
    """Free Edition (the dev workspace) has serverless GPU, so the GPU jobs are in every target and ask
    for a serverless GPU per task; no job cluster or node type."""
    root, jobs = _load()
    for name in ("medgemma_reader", "encoder_gpu"):
        j = jobs[name][0]
        assert "job_clusters" not in j, name
        for t in j["tasks"]:
            assert t["compute"] == {"hardware_accelerator": "${var.gpu_accelerator}"} and "job_cluster_key" not in t
        for env, tgt in root["targets"].items():
            assert name not in tgt.get("resources", {}).get("jobs", {}), (name, env)
    assert root["variables"]["gpu_accelerator"]["default"] == "GPU_1xA10"
    # A serverless task with task-level compute needs an environment (400 INVALID_PARAMETER_VALUE otherwise)
    for name in ("medgemma_reader", "encoder_gpu"):
        j = jobs[name][0]
        envs = {e["environment_key"]: e["spec"] for e in j["environments"]}
        for t in j["tasks"]:
            assert t["environment_key"] in envs, name
            assert envs[t["environment_key"]]["environment_version"] == "${var.gpu_environment_version}"
    assert root["variables"]["gpu_environment_version"]["default"].isdigit()
    assert not {"gpu_node_type", "gpu_spark_version"} & set(root["variables"])


def test_mlflow_experiment_and_uc_model_per_target():
    m = yaml.safe_load((ROOT / "databricks/resources/mlops.yml").read_text())["resources"]
    assert "${bundle.target}" in "".join(m["experiments"]["dental_experiment"]["name"]) or \
        "${workspace.root_path}" in m["experiments"]["dental_experiment"]["name"]
    assert set(m["registered_models"]) == {"perio_bench_note_classifier"}
    rm = m["registered_models"]["perio_bench_note_classifier"]
    assert rm["name"] == "perio_note_classifier"
    assert rm["catalog_name"] == GOLD_CATALOG and rm["schema_name"] == GOLD_SCHEMA


def test_study_benchmark_passes_experiment_id_not_name():
    """MLflow stores /Workspace/Users/... as /Users/..., so passing the name makes Terraform
    see a changed value mid-apply ("Provider produced inconsistent final plan")."""
    _, jobs = _load()
    params = jobs["study_benchmark"][0]["tasks"][0]["notebook_task"]["base_parameters"]
    assert params.get("experiment_id") == "${resources.experiments.dental_experiment.id}"
    assert "experiment" not in params


def test_encoder_is_off_when_the_notebook_runs_by_hand():
    """DistilBERT on serverless CPU took over 16 minutes in dev; the baselines take about 3.
    Per-target settings: test_encoder_rung_off_in_dev_on_in_uat_and_prod."""
    nb = (ROOT / "databricks/notebooks/01_run_benchmark.py").read_text()
    assert 'dbutils.widgets.dropdown("run_encoder", "false"' in nb


def test_judge_monitoring_job_only_in_uat_and_prod():
    """Production monitoring scores live traces, so it exists where there is live traffic."""
    root, jobs = _load()
    assert "judge_monitoring" not in jobs and "judge_monitoring" not in root["targets"]["dev"].get("resources", {}).get("jobs", {})
    for env in ("uat", "prod"):
        t = root["targets"][env]["resources"]["jobs"]["judge_monitoring"]["tasks"][0]["notebook_task"]
        assert t["base_parameters"]["experiment_id"] == "${resources.experiments.dental_experiment.id}"
        assert t["base_parameters"]["sample_rate"] == "${var.judge_sample_rate}"


def test_bundle_creates_the_catalog_bench_schemas_and_landing_volume():
    """One catalog (health_transformation_lab) with a schema per bench and layer (spec 022), all bundle
    resources so a deploy creates them; the data volume lives in landing_perio_bench.
    prevent_destroy keeps `bundle destroy` from dropping data."""
    from health_transformation_lab_nlp import schemas
    uc = yaml.safe_load((ROOT / "databricks/resources/unity_catalog.yml").read_text())["resources"]
    assert {k: c["name"] for k, c in uc["catalogs"].items()} == {"health_transformation_lab": "${var.catalog}"}
    bench = {f"{b}_{layer}": schemas.schema(b, layer) for b, layers in schemas.LAYERS.items() for layer in layers}
    assert {k: sc["name"] for k, sc in uc["schemas"].items()} == bench
    assert {sc["catalog_name"] for sc in uc["schemas"].values()} == {"${resources.catalogs.health_transformation_lab.name}"}
    assert set(uc["volumes"]) == {"perio_bench_data", "opendental_perio_data"}
    od = uc["volumes"]["opendental_perio_data"]                       # spec 029: the extract's files
    assert od["schema_name"] == "${resources.schemas.opendental_perio_landing.name}" and od["name"] == "data"
    assert od["volume_type"] == "MANAGED" and od["lifecycle"]["prevent_destroy"] is True
    vol = uc["volumes"]["perio_bench_data"]
    assert vol["catalog_name"] == "${resources.schemas.perio_bench_landing.catalog_name}" and vol["name"] == "data"
    assert vol["schema_name"] == "${resources.schemas.perio_bench_landing.name}" and vol["volume_type"] == "MANAGED"
    # the admin group create_service_principal.sh makes gets the catalog; the deployer owns it
    assert uc["catalogs"]["health_transformation_lab"]["grants"] == [
        {"principal": "dental_omop_nlp_${bundle.target}_admin", "privileges": ["ALL_PRIVILEGES"]}]
    for r in [*uc["catalogs"].values(), *uc["schemas"].values(), vol]:
        assert r["lifecycle"]["prevent_destroy"] is True


def test_jobs_write_to_the_bundle_schema():
    # Via the resource, not ${var.catalog}, so a deploy creates the schema before
    # any job that writes to it.
    root, jobs = _load()
    seen = 0
    for name, task, _ in _tasks(root, jobs):
        p = task["notebook_task"].get("base_parameters", {})
        if "catalog" in p:
            assert (p["catalog"], p["schema"]) == (GOLD_CATALOG, GOLD_SCHEMA), name
            seen += 1
        if "landing_schema" in p:
            assert p["landing_schema"] == LANDING, name
    assert seen >= 3
    bench = jobs["study_benchmark"][0]["tasks"][0]["notebook_task"]["base_parameters"]
    assert bench["landing_schema"] == LANDING


def test_old_schemas_stay_declared_only_where_they_were_deployed():
    """Spec 022: dev deployed <layer>_dental_omop_perio (spec 021). Their bundle keys stay, under dev only, so a
    deploy neither fails on prevent_destroy nor drops them; uat and prod never had them."""
    root, _ = _load()
    for env, t in root["targets"].items():
        res = t.get("resources", {})
        if env not in LEGACY_TARGETS:
            assert not {"schemas", "volumes", "registered_models"} & set(res), env
            continue
        assert {k: s["name"] for k, s in res["schemas"].items()} == {
            k: f"{k}_${{var.legacy_domain}}" for k in ("landing", "bronze", "silver", "gold")}, env
        assert all(s["lifecycle"]["prevent_destroy"] is True for s in res["schemas"].values())
        vol = res["volumes"]["data"]
        assert vol["schema_name"] == "${resources.schemas.landing.name}" and vol["lifecycle"]["prevent_destroy"] is True
        model = res["registered_models"]["perio_note_classifier"]
        assert model["schema_name"] == "${resources.schemas.gold.name}"


def test_encoder_rung_off_in_dev_on_in_uat_and_prod():
    """Dev is a quick smoke test: no DistilBERT fine-tune, no torch install."""
    root, jobs = _load()
    bench = jobs["study_benchmark"][0]["tasks"][0]["notebook_task"]["base_parameters"]
    assert bench["run_encoder"] == "${var.run_encoder}"
    d = root["variables"]["run_encoder"]["default"]
    got = {env: t.get("variables", {}).get("run_encoder", d) for env, t in root["targets"].items()}
    assert got == {"dev": "false", "uat": "true", "prod": "true"}


def test_benchmark_notebook_installs_cpu_torch_only_for_the_encoder():
    nb = (ROOT / "databricks/notebooks/01_run_benchmark.py").read_text()
    assert "download.pytorch.org/whl/cpu" in nb
    assert 'if run_encoder:\n    results.append(run("distilbert-base"' in nb


def test_deploy_does_not_wait_for_the_benchmark_run():
    wf = (ROOT / ".github/workflows/deploy.yml").read_text()
    assert "bundle run -t \"$TARGET\" --no-wait study_benchmark" in wf


def test_judge_scorecard_job_and_dev_judge_endpoint():
    """Spec 012: the scorecard job writes to the gold schema with the bundle's judge endpoint; dev
    defaults to a pay-per-token endpoint, other targets to none (skip)."""
    root, jobs = _load()
    job, _ = jobs["judge_scorecard"]
    p = job["tasks"][0]["notebook_task"]["base_parameters"]
    assert p["judge_endpoint"] == "${var.judge_endpoint}"
    assert p["catalog"] == GOLD_CATALOG and p["schema"] == GOLD_SCHEMA
    assert p["experiment_id"] == "${resources.experiments.dental_experiment.id}"
    assert root["variables"]["judge_endpoint"]["default"] == "none"
    assert root["targets"]["dev"]["variables"]["judge_endpoint"] == "databricks-meta-llama-3-3-70b-instruct"
    deploy = (ROOT / ".github" / "workflows" / "deploy.yml").read_text()
    assert "JUDGE_ENDPOINT || 'none'" not in deploy     # CI must not mask the dev default


def test_scorecard_dashboard_has_phenotyping_and_deidentification_pages():
    """Spec 012 US3: an AI/BI dashboard deployed with the bundle, same name in every target, reading
    the gold tables the judge_scorecard job writes."""
    import json
    res = yaml.safe_load((ROOT / "databricks/resources/dashboards.yml").read_text())["resources"]["dashboards"]
    d = res["scorecard"]
    assert "${bundle.target}" not in d["display_name"] and d["warehouse_id"] == "${var.warehouse_id}"
    dash = json.loads((ROOT / "databricks/resources" / d["file_path"]).resolve().read_text())
    assert [p["displayName"] for p in dash["pages"]] == ["Phenotyping", "De-identification"]
    names = {ds["name"] for ds in dash["datasets"]}
    tables = {"fact_chart_answer", "fact_judge_call", "judge_metric", "judge_agreement", "judge_cost", "deid_score"}
    for ds in dash["datasets"]:
        sql = " ".join(ds["queryLines"])
        used = set(re.findall(r"health_transformation_lab\.gold_perio_bench\.(\w+)", sql))
        assert used and used <= tables, ds["name"]
    for page in dash["pages"]:
        for item in page["layout"]:
            for q in item["widget"].get("queries", []):
                assert q["query"]["datasetName"] in names, item["widget"]["name"]


def test_dev_catalog_states_its_default_storage_root():
    """dev's health_transformation_lab was made with SQL on Default Storage (docs/deployment.md), which sets a storage
    root; without it in the config the deploy plans to recreate the catalog (prevent_destroy stops it)."""
    root, _ = _load()
    dev = root["targets"]["dev"]["resources"]["catalogs"]["health_transformation_lab"]
    assert dev["storage_root"].startswith("s3://") and "/uc/" in dev["storage_root"]
    for env in ("uat", "prod"):
        assert "catalogs" not in root["targets"][env].get("resources", {})


GPU_ENCODERS = {"modernbert-large", "bioclinical-modernbert-large", "longformer-base", "clinical-longformer",
                "gatortron-base"}


def test_encoder_gpu_job_runs_the_gpu_encoders():
    """spec 002 T017: the encoders that need a GPU, and GatorTron-base at a lower learning rate."""
    root, jobs = _load()
    p = jobs["encoder_gpu"][0]["tasks"][0]["notebook_task"]["base_parameters"]
    assert p["rungs"] == "${var.encoder_gpu_rungs}" and p["lr_overrides"] == "${var.encoder_gpu_lr}"
    assert p["landing_schema"] == LANDING
    assert set(root["variables"]["encoder_gpu_rungs"]["default"].split(",")) == GPU_ENCODERS
    lr = dict(x.split("=") for x in root["variables"]["encoder_gpu_lr"]["default"].split(","))
    assert set(lr) == {"gatortron-base"} and 1e-5 <= float(lr["gatortron-base"]) <= 2e-5


def test_encoder_gpu_notebook_runs_the_script_and_keeps_the_predictions():
    nb = (ROOT / "databricks/notebooks/08_encoder_gpu.py").read_text()
    assert "scripts/11_ai_predict.py" in nb and "--lr" in nb
    assert "/Volumes/" in nb and "encoder_gpu" in nb          # predictions copied to the landing volume
    assert "local_disk0" not in nb                           # serverless has no local_disk0
    assert "saveAsTable" in nb                                # and kept as a table


def test_every_model_that_can_be_scored_has_a_plain_name():
    import yaml
    from health_transformation_lab_nlp import readme_results as rr
    reg = yaml.safe_load((ROOT / "models.yaml").read_text())
    for m in reg["models"]:
        if m["role"] in ("classifier", "long_context", "llm"):
            assert "_" not in rr.plain_system(m["id"]) and rr.plain_system(m["id"] + "+lr2e-05"), m["id"]
    assert "learning rate" in rr._model_method("gatortron-base+lr2e-05")


def test_job_and_dashboard_names_are_short_and_the_same_in_every_target():
    """Readable on a phone; no per-target suffix (AGENTS.md: names identical in every target)."""
    root, jobs = _load()
    names = [j["name"] for j, _ in jobs.values()]
    names += [j["name"] for t in root["targets"].values() for j in t.get("resources", {}).get("jobs", {}).values()]
    for f in (ROOT / "databricks" / "resources").glob("*.yml"):
        names += [d["display_name"] for d in (yaml.safe_load(f.read_text())["resources"].get("dashboards") or {}).values()]
    assert len(names) >= 8
    for n in names:
        assert len(n) <= 20 and "${bundle.target}" not in n and "health-transformation-lab-nlp" not in n, n


def test_medgemma_reader_takes_shots_and_lora_as_settings():
    """MedGemma few-shot and LoRA runs (and other MedGemma versions via reader_rung) without editing the job."""
    root, jobs = _load()
    p = jobs["medgemma_reader"][0]["tasks"][0]["notebook_task"]["base_parameters"]
    assert p["rung"] == "${var.reader_rung}"
    assert p["shots"] == "${var.reader_shots}" and p["lora_train"] == "${var.reader_lora_train}"
    assert root["variables"]["reader_shots"]["default"] == "0" and root["variables"]["reader_lora_train"]["default"] == "0"


def test_deid_ai_job_runs_the_databricks_methods_and_keeps_results_on_the_volume():
    root, jobs = _load()
    j, _ = jobs["deid_ai"]
    p = j["tasks"][0]["notebook_task"]["base_parameters"]
    assert j["tasks"][0]["notebook_task"]["notebook_path"].endswith("06_deid_benchmark.py")
    assert p["engines"] == "${var.deid_ai_engines}"
    assert set(root["variables"]["deid_ai_engines"]["default"].split(",")) == {
        "llm", "llm+regex_v2+guard", "ai_mask", "ai_mask+regex_v2+guard"}
    assert p["llm_endpoint"] == "${var.deid_llm_endpoint}" and p["sql_warehouse_id"] == "${var.warehouse_id}"
    assert p["save_to_repo"] == "no" and p["out_dir"].startswith("/Volumes/${resources.volumes.perio_bench_data.catalog_name}/")
    nb = (ROOT / "databricks/notebooks/06_deid_benchmark.py").read_text()
    assert 'dbutils.widgets.text("out_dir"' in nb


def test_gpu_jobs_retry_a_failed_start():
    """Serverless GPU can fail to come up or to restart Python after the %pip install (seen: a restart
    timing out after 15 minutes); the task is retried rather than the run failing outright."""
    _, jobs = _load()
    for name in ("medgemma_reader", "encoder_gpu"):
        for t in jobs[name][0]["tasks"]:
            assert t["max_retries"] >= 1, name
            assert t["min_retry_interval_millis"] >= 60_000 and t["retry_on_timeout"] is True, name


def test_nhanes_job_downloads_public_files_to_the_volume_and_keeps_only_aggregates():
    _, jobs = _load()
    j, _ = jobs["nhanes_perio"]
    assert len(j["name"]) <= 20
    t = j["tasks"][0]
    p = t["notebook_task"]["base_parameters"]
    assert t["notebook_task"]["notebook_path"].endswith("09_nhanes_perio.py")
    assert p["data_dir"].startswith("/Volumes/${resources.volumes.perio_bench_data.catalog_name}/") and p["data_dir"].endswith("/nhanes_raw")
    assert p["out_dir"].endswith("/nhanes")
    assert j["tags"]["data"] == "public"
    nb = (ROOT / "databricks/notebooks/09_nhanes_perio.py").read_text()
    assert "38_nhanes_perio.py" in nb and "--download" in nb


def test_gpu_jobs_keep_retrying_long_enough_to_outlast_a_gpu_shortage():
    """A start that fails because no GPU is free (seen in dev: "failed to start within 900 seconds", twice,
    two minutes apart) needs retries spread over hours, not minutes: at least 4 hours of retrying."""
    _, jobs = _load()
    for name in ("medgemma_reader", "encoder_gpu"):
        for t in jobs[name][0]["tasks"]:
            start_wait = 15 * 60_000                                       # each attempt waits up to 15 min for a GPU
            span = t["max_retries"] * t["min_retry_interval_millis"] + (t["max_retries"] + 1) * start_wait
            assert span >= 4 * 3_600_000, name
            assert t["min_retry_interval_millis"] >= 20 * 60_000, name     # spaced out, not back to back


def test_pipeline_jobs_send_telemetry_from_the_secret_scope():
    """Spec 014: the jobs that start scripts pass the telemetry switch; the notebook reads the Application
    Insights connection string from the secret scope (never a job parameter)."""
    root, jobs = _load()
    assert root["variables"]["telemetry_exporter"]["default"] == "azure"
    for name, nb in (("medgemma_reader", "03_medgemma_reader.py"), ("encoder_gpu", "08_encoder_gpu.py"),
                     ("nhanes_perio", "09_nhanes_perio.py")):
        p = jobs[name][0]["tasks"][0]["notebook_task"]["base_parameters"]
        assert p["telemetry"] == "${var.telemetry_exporter}", name
        assert not any("InstrumentationKey" in str(v) for v in p.values()), name
        text = (ROOT / "databricks/notebooks" / nb).read_text()
        assert "telemetry.use_databricks_secret(dbutils" in text and 'widgets.text("telemetry"' in text, nb


def test_every_job_and_run_shows_the_commit_it_was_deployed_from():
    """"Is this run on the latest code?" is answered on the job and run pages: every job is tagged with the
    deployed commit, and every Python notebook task gets it as a parameter (shown on each run), which the
    notebook hands to the code so MLflow runs are tagged with it instead of "unknown"."""
    root, jobs = _load()
    all_jobs = {k: j for k, (j, _) in jobs.items()}
    for tgt in root["targets"].values():
        all_jobs.update(tgt.get("resources", {}).get("jobs", {}) or {})
    for name, j in all_jobs.items():
        assert j.get("tags", {}).get("git_commit") == "${bundle.git.commit}", name
        for t in j["tasks"]:
            nb = t.get("notebook_task", {}).get("notebook_path", "")
            if nb.endswith(".py"):
                assert t["notebook_task"]["base_parameters"]["git_commit"] == "${bundle.git.commit}", (name, nb)
                text = (ROOT / "databricks" / "notebooks" / nb.rsplit("/", 1)[1]).read_text()
                assert "tracking.use_git_commit(dbutils)" in text, nb


def test_a_new_gpu_run_does_not_queue_behind_an_old_one_waiting_to_retry():
    """GPU runs retry for hours when no GPU is free. With one run allowed at a time, a run started after a
    deploy (new code) sat "Queued" behind an old run "Waiting for retry". Two at a time lets it start."""
    _, jobs = _load()
    for name in ("medgemma_reader", "encoder_gpu"):
        assert jobs[name][0].get("max_concurrent_runs") == 2, name


# --- spec 027 US5: the pipeline doctor job ---------------------------------------------------------

DOCTOR_NB = ROOT / "databricks" / "notebooks" / "13_pipeline_doctor.py"


def test_pipeline_doctor_job_runs_the_doctor_notebook_with_its_settings():
    """One task on serverless CPU, the gold schema, the bundle's judge endpoint and the scorecard's budget; every
    setting is a bundle variable (declared once, same name in every target), and no target overrides the job."""
    root, jobs = _load()
    j, _ = jobs["pipeline_doctor"]
    assert j["name"] == "Pipeline doctor" and j["tags"]["data"] == "synthetic"
    (t,) = j["tasks"]
    assert t["notebook_task"]["notebook_path"] == "../notebooks/13_pipeline_doctor.py"
    assert "compute" not in t and "job_cluster_key" not in t and "existing_cluster_id" not in t
    p = t["notebook_task"]["base_parameters"]
    assert (p["catalog"], p["schema"]) == (GOLD_CATALOG, GOLD_SCHEMA)
    assert p["judge_endpoint"] == "${var.judge_endpoint}"
    assert p["max_usd"] == "${var.judge_max_usd}"
    assert p["lookback_days"] == "${var.doctor_lookback_days}" and p["span_table"] == "${var.doctor_span_table}"
    assert p["run_id"] == "{{job.run_id}}"                    # the batch key every row carries
    assert p["decisions"] == "" and p["decided_by"] == ""      # approval is a run parameter until an approval UI
    v = root["variables"]
    assert v["judge_max_usd"]["default"] == "5" and v["doctor_lookback_days"]["default"].isdigit()
    assert v["doctor_span_table"]["default"] == "none"
    for env, tgt in root["targets"].items():
        assert "pipeline_doctor" not in tgt.get("resources", {}).get("jobs", {}), env
        assert not {"judge_max_usd", "doctor_lookback_days", "doctor_span_table"} & set(tgt.get("variables", {})), env


def test_the_scorecard_and_the_doctor_share_one_budget_setting():
    _, jobs = _load()
    p = jobs["judge_scorecard"][0]["tasks"][0]["notebook_task"]["base_parameters"]
    assert p["max_usd"] == "${var.judge_max_usd}"


def test_pipeline_doctor_is_created_paused_and_does_not_retry():
    """A deploy creates the job; running it is the owner's decision, so its schedule is paused in every target
    (uat and prod are mode: production, which would otherwise unpause it). No retries: its failures are a bad
    setting, a missing grant or a deliberate page for a new SEV1/SEV2 decision, none of which pass on their own,
    and a retry would swallow the page."""
    _, jobs = _load()
    j, _ = jobs["pipeline_doctor"]
    assert j["schedule"]["pause_status"] == "PAUSED" and j["schedule"]["quartz_cron_expression"]
    assert j.get("max_concurrent_runs", 1) == 1
    (t,) = j["tasks"]
    assert t["max_retries"] == 0 and t["timeout_seconds"] <= 3600


def test_doctor_notebook_checks_settings_first_and_writes_by_run_id():
    text = "\n".join(line for line in DOCTOR_NB.read_text().splitlines() if not line.startswith("# MAGIC"))
    check = text.index("doctor_job.check_settings(")
    assert check < text.index("system.lakeflow.job_run_timeline") and check < text.index("replace_keys(")
    for table in ("fact_pipeline_run", "fact_pipeline_signal", "fact_remediation_decision"):
        assert f'write("{table}",' in text, table
    # one writer: delete-then-append by run_id, under the declared gold columns and types
    assert 'delta.replace_keys(spark, doctor_job.rows(df, name, **batch), table(name), "run_id",' in text
    assert "schema=doctor_job.ddl(name)" in text
    assert '.mode("append")' not in text and "saveAsTable" not in text and "mode(\"overwrite\")" not in text
    assert "DATABRICKS_TOKEN" not in text and "note_text" not in text
    assert "doctor_job.notifications(" in text and "raise RuntimeError" in text
