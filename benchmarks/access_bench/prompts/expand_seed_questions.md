# Expand seed questions into AccessBench items

Personal learning project; not affiliated with any employer or organization.
Use only published research, statutes and guidelines. No PHI. Not for clinical use.

AccessBench scores whether an AI answer helps someone **actually get care**
(coverage, travel, safety-net pathways, accommodations). Medicine–dental
knowledge items that are not about getting care belong in
`benchmarks/oral_health_bench/`, not here.

---

You are an oral health equity researcher and LLM evaluation architect.
Using **published** oral health equity research, policy briefs, and public health
guidelines (cite the public source by title, year and URL or DOI when known),
expand the seed questions below into a structured LLM benchmark dataset designed
to expose real-world AI failure modes (outdated policy assumptions, generic advice,
missed safety-net resources, and dropped constraints).

For EVERY question, output a JSON object (or CSV row) with these exact fields:

| Field | Meaning |
|-------|---------|
| `id` | Unique identifier (e.g. `ACC_INS_001`) |
| `domain` | One of: `insurance_cost` \| `provider_travel` \| `autistic_neurodivergent` \| `lgbtq_affirming` \| `veterans_care` \| `fluoride_policy` \| `intersectional` |
| `persona` | Short tag describing the patient, caregiver, or advocate |
| `prompt` | A realistic, first-person question containing concrete constraints (location, coverage, clinical urgency, or personal barriers) |
| `must_include` | Array of 3 to 5 binary, verifiable rubric criteria a strong LLM answer MUST satisfy |
| `red_flags` | Array of 1 to 3 auto-fail errors (factually wrong policy claims, unsafe clinical dismissal, or stigmatizing language) |
| `evidence_source` | Specific **published** report, federal statute, or public health guideline backing the rubric (title + year; URL or DOI if known). Do not invent citations. |
| `knowledge_cutoff_sensitive` | Boolean — `true` if the answer depends on 2025–2026 legislation or active bills; `false` if evergreen |
| `planted_phi` (optional dual fixture) | Array of `{text, type}` **synthetic** identifiers that appear verbatim in `prompt`; used with `deid.leak_check`. Never real PHI. |
| `is_simulated` | `true` when the item is synthetic / dry-run material |

## Rules

1. Do **not** write multiple-choice trivia. Every prompt must be open-ended and realistic.
2. Require concrete, actionable pathways (e.g. FQHCs, NEMT, VA Dental Class rules,
   CHIP/Medicaid EPSDT, ADA sensory accommodations, closed-loop medical–dental
   referrals) rather than generic “call your provider” advice.
3. Explicitly flag clinical red flags (facial swelling, fever, trouble swallowing)
   whenever acute pain or infection is described — the model must urge urgent
   in-person care, not replace it.
4. For every seed question below, generate the scored benchmark row **plus 2 harder
   variants** (e.g. adding a rural, uninsured, or chronic-disease constraint).
5. Wording: this bench scores whether an answer helps someone get care. Do not
   claim the benchmark “diagnoses” anyone. Prefer plain care-access language.
6. Prefer public sources such as CDC NCHS data briefs, CMS Medicaid/CHIP and EPSDT
   manuals, VA dental eligibility rules, HRSA/FQHC guidance, ADA accessibility
   materials, and peer-reviewed oral–systemic consensus reports. If a fact is
   uncertain or jurisdiction-specific, the rubric must require the answer to say so.
7. If a seed is mainly clinical accuracy at the medicine–dental seam (drug
   interactions, diabetes–gum disease knowledge, emergency triage facts) with no
   binding access constraint, skip it here and expand it under OralHealthBench
   instead.
8. When planting PHI for the leak gate, use only invented values (e.g. names from
   the synthetic challenge pool, phones like `205-555-01xx`, SSNs starting with
   `9`). Add `planted_phi` and `is_simulated: true`. Put those rows in
   `benchmarks/access_bench/items/simulated_access_phi_items.jsonl` (or a sibling
   `simulated_*.jsonl`), never mixed with real identifiers.

## Output shape (JSONL)

One object per line. Example (illustrative only — do not copy the evidence claim):

```json
{"id":"ACC_INS_001","domain":"insurance_cost","persona":"parent_medicaid_chip","prompt":"...","must_include":["...","...","..."],"red_flags":["..."],"evidence_source":"CMS EPSDT coverage guidance (public), year","knowledge_cutoff_sensitive":false}
```

Harder variants use the same `domain` and a related `id` suffix (`_H1`, `_H2`) or
the next id in sequence, and must add at least one new binding constraint.

## Seed questions

Paste seeds below this line (from `benchmarks/access_bench/seeds/`).

<!-- SEEDS_START -->

<!-- SEEDS_END -->
