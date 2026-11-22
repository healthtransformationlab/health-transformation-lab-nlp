-- Coding-agent trace views (spec 041 US4, #859): our names over Databricks' UC span tables.
--
-- Source tables (bundle: databricks/resources/agent_traces.yml, prefix coding_agent):
--   coding_agent_trace_metadata  — tags and assessments per trace
--   coding_agent_otel_spans      — one row per span; facts live in attributes (variant)
--
-- Attribute keys used (listed from migrated spans, November 2026):
--   mlflow.spanType          AGENT | LLM | TOOL
--   mlflow.chat.tokenUsage   {input_tokens, output_tokens, total_tokens} on LLM turns
--   gen_ai.usage.input_tokens / gen_ai.usage.output_tokens  (same counts when present)
--   gen_ai.tool.name / gen_ai.operation.name
--   step_num                 tool / turn order within the task
--   agent_seconds            wall time on the AGENT root span
--   status.code              STATUS_CODE_OK | STATUS_CODE_ERROR
--
-- Run once per workspace in the SQL editor (or databricks api), with "Run all". Re-running is safe:
-- every statement is create or replace.

create schema if not exists health_transformation_lab.ops_agent_trace
  comment 'Unity Catalog storage for coding-agent MLflow traces (spec 041)';

create or replace view health_transformation_lab.ops_agent_trace.agent_task_run
  comment 'one row per coding-agent task-run: tags plus tool and token totals from its spans (spec 041 US4)'
as
with span_facts as (
  select
    trace_id,
    cast(attributes:['mlflow.spanType'] as string) as span_type,
    cast(attributes:['gen_ai.usage.input_tokens'] as bigint) as input_tokens,
    cast(attributes:['gen_ai.usage.output_tokens'] as bigint) as output_tokens,
    cast(attributes:['agent_seconds'] as double) as agent_seconds,
    start_time_unix_nano,
    end_time_unix_nano
  from health_transformation_lab.ops_agent_trace.coding_agent_otel_spans
),
per_trace as (
  select
    trace_id,
    min(case when span_type = 'AGENT' then start_time_unix_nano end) as task_start_ns,
    max(case when span_type = 'AGENT' then agent_seconds end) as agent_seconds,
    max(case when span_type = 'AGENT' then end_time_unix_nano end)
      - min(case when span_type = 'AGENT' then start_time_unix_nano end) as agent_duration_ns,
    sum(case when span_type = 'TOOL' then 1 else 0 end) as tool_call_count,
    sum(case when span_type = 'LLM' then coalesce(input_tokens, 0) else 0 end) as input_token_count,
    sum(case when span_type = 'LLM' then coalesce(output_tokens, 0) else 0 end) as output_token_count
  from span_facts
  group by trace_id
)
select
  m.trace_id as trace_id,
  m.tags['run_label'] as run_label,
  m.tags['agent_name'] as agent_name,
  m.tags['instance_id'] as instance_id,
  m.tags['repo_name'] as repo_name,
  cast(m.tags['is_resolved'] as boolean) as is_resolved,
  m.tags['outcome_code'] as outcome_code,
  m.tags['ended_code'] as ended_code,
  cast(p.task_start_ns / 1e9 as timestamp) as task_start_ts,
  coalesce(p.agent_seconds, cast(p.agent_duration_ns as double) / 1e9) as task_seconds,
  cast(coalesce(p.tool_call_count, 0) as bigint) as tool_call_count,
  cast(coalesce(p.input_token_count, 0) as bigint) as input_token_count,
  cast(coalesce(p.output_token_count, 0) as bigint) as output_token_count
from health_transformation_lab.ops_agent_trace.coding_agent_trace_metadata as m
left join per_trace as p
  on m.trace_id = p.trace_id;

create or replace view health_transformation_lab.ops_agent_trace.agent_tool_call
  comment 'one row per tool call on a coding-agent task-run (spec 041 US4)'
as
select
  s.trace_id as trace_id,
  s.span_id as span_id,
  m.tags['run_label'] as run_label,
  m.tags['agent_name'] as agent_name,
  m.tags['instance_id'] as instance_id,
  cast(s.attributes:['step_num'] as bigint) as step_num,
  s.name as tool_name,
  cast(s.start_time_unix_nano / 1e9 as timestamp) as call_start_ts,
  cast(s.end_time_unix_nano - s.start_time_unix_nano as double) / 1e9 as call_seconds,
  (s.status.code = 'STATUS_CODE_ERROR') as is_error
from health_transformation_lab.ops_agent_trace.coding_agent_otel_spans as s
inner join health_transformation_lab.ops_agent_trace.coding_agent_trace_metadata as m
  on s.trace_id = m.trace_id
where cast(s.attributes:['mlflow.spanType'] as string) = 'TOOL';
