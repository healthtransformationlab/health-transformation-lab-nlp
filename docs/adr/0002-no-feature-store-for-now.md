# ADR 0002: No feature store for now

Date: 2026-10-28 · Status: accepted · Issue: #135

## Context

Databricks offers a feature store (feature tables in Unity Catalog, with online serving). It pays off
when engineered features are computed once and shared by several models, or looked up at low latency
when a model is served.

Neither applies here. The MedGemma reader works directly from note text. The other methods read the
synthetic notes and charts, or the OMOP tables built from them. Their inputs are versioned as
datasets and their outputs as results tables. No engineered feature is shared across models, and
nothing is served online.

## Decision

Don't add a feature store. Model inputs stay as the existing tables and files, and are versioned
the way they are now.

## Consequences

- One less service to deploy, secure and pay for in each environment.
- If two models compute the same feature, each does its own computation, so the two can drift
  apart. Today no two models do.

## Revisit when

- several models use the same engineered features (for example the progression model and a
  serving-time risk score), or
- a model is served online and needs features looked up per request, or
- we need point-in-time-correct training sets that we can't easily build from the OMOP tables.

## Confirmations

- 2026-11-06 (#625): still holds. The SHAP-by-outcome drilldown (`classify_status.shap_drilldown_by_outcome`) explains
  existing models' answers from their own inputs; it adds no shared or served feature.
