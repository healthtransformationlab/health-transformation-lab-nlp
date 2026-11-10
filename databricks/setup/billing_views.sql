-- Billing for the doctor job (spec 036 US1, #568, #654): views over system.billing that the job's identity can read.
--
-- Why views: only an account admin, or someone with MANAGE on system.billing, can grant on it. A workspace owner who
-- can read system.billing but not grant on it makes these views instead. A Unity Catalog view reads its source with
-- its owner's rights, so the job's identity needs access to the views only.
--
-- Only the columns the doctor reads (doctor_job.BILLING_USAGE_SQL, BILLING_PRICES_SQL).
--
-- Run once per workspace, in the SQL editor, as the workspace owner (who can read system.billing), with "Run all".
-- Parameter service_principal: the job's service principal's application id, from GitHub, this repository,
-- Settings -> Environments -> <target> -> variable SERVICE_PRINCIPAL (or DATABRICKS_CLIENT_ID). Enter it without
-- quotes or backticks. Re-running is safe: every statement replaces or repeats.
-- The doctor reads these through the bundle variable billing_schema (default health_transformation_lab.ops_billing).

create schema if not exists health_transformation_lab.ops_billing
  comment 'Views over system.billing for the pipeline doctor: one row per billing usage line, and per list price (spec 036, #654)';

create or replace view health_transformation_lab.ops_billing.usage
  comment 'system.billing.usage as the workspace owner reads it: one row per billing usage line'
as
select usage_metadata, sku_name, usage_unit, usage_quantity, usage_start_time, usage_date
from system.billing.usage;

create or replace view health_transformation_lab.ops_billing.list_prices
  comment 'system.billing.list_prices as the workspace owner reads it: one row per SKU price in effect for a period'
as
select sku_name, usage_unit, pricing, currency_code, price_start_time, price_end_time
from system.billing.list_prices;

-- The grants take the principal from the :service_principal parameter (the SQL editor shows a box for it); a grant
-- can't take a parameter directly, so each is built as text and run with execute immediate.
declare or replace variable billing_grant string;
set var billing_grant = 'grant use schema on schema health_transformation_lab.ops_billing to `' || :service_principal || '`';
execute immediate billing_grant;
set var billing_grant = 'grant select on schema health_transformation_lab.ops_billing to `' || :service_principal || '`';
execute immediate billing_grant;

-- Check: the service principal is listed with USE SCHEMA and SELECT.
show grants on schema health_transformation_lab.ops_billing;
