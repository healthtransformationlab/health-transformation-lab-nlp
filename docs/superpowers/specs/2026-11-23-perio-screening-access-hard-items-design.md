# Design: Hard AccessBench items for periodontal screening access (by 2030)

**Status:** Approved and implemented (#919)  
**Bench:** AccessBench (getting care), not OralHealthBench  
**Personal learning project:** not affiliated with any employer or organization. Synthetic prompts only. Not for clinical use.

## Goal

North star for this personal learning project: help **more people complete a periodontal screening / comprehensive periodontal evaluation pathway** by 2030. The stretch target of “about 7 million more people screened” is an **owner stretch goal**, not a cited WHO or CDC quota. Public anchors we do cite:

- Healthy People 2030 **OH-08** — increase use of the oral health care system ([data](https://odphp.health.gov/healthypeople/objectives-and-data/browse-objectives/health-care/increase-use-oral-health-care-system-oh-08/data)).
- WHO Global strategy and action plan on oral health 2023–2030 (UHC / oral health services access).

AccessBench scores whether an answer helps someone **actually get** that screening or the next covered step (coverage check, appeal, safety-net, correct code/pathway) — not whether a model “finds gum disease” in a chart.

## Approach chosen

**Hard AccessBench set (10 items):** open-ended, first-person prompts grounded in **real public forum asks**, with rubrics tied to **primary statutes / manuals / peer-reviewed or federal sources**. Designed so major LLMs fail on jurisdiction, medical≠dental billing, Medicare exclusion, waiting periods, and denial/appeal steps.

Rejected: OralHealthBench-only clinical traps (wrong north star); mixed set (dilutes AccessBench batch).

## Deliverables

| Artifact | Path |
|----------|------|
| This design | `docs/superpowers/specs/2026-11-23-perio-screening-access-hard-items-design.md` |
| Seeds | `benchmarks/access_bench/seeds/perio_screening_hard_2030.md` |
| Scored items | `benchmarks/access_bench/items/perio_screening_hard_items.jsonl` (10 rows; no planted PHI in v1) |
| Loader | Reuse `access_phi_items`-style load **or** a thin sibling loader if the existing module only reads the PHI dual file — decided at plan time so tests stay green |

No gold schema change. No employer or organization affiliation claims. Wording: screening, checkup, covered services, pathway — never claim the bench finds disease in a person.

## Hardness patterns (why models miss)

1. Adult Medicaid dental is **state-optional** and code-specific.  
2. Medical insurance ≠ dental insurance for routine perio.  
3. Medicare **excludes** care of teeth and supporting structures; narrow “inextricably linked” exceptions only.  
4. Commercial plans often have **waiting periods** for periodontics.  
5. **D0180** (comprehensive periodontal evaluation) ≠ **D1110** prophylaxis; payers limit frequency.  
6. Denials need **NOABD / appeal / PA packet**, not generic “call your dentist.”  
7. Pregnancy / diabetes “extra” dental benefits are **plan- and state-specific**, not automatic.  
8. Safety-net (FQHC, dental school) when coverage is blocked.

## The ten items

Each row will be AccessBench JSONL: `id`, `domain`, `persona`, `prompt`, `must_include` (3–5), `red_flags` (1–3), `evidence_source`, `knowledge_cutoff_sensitive`, `is_simulated: true`, plus metadata fields `source_thread_url` and `screening_goal_tag: perio_screening_2030` (allowed extras; core loader ignores unknowns if needed).

### 1. `ACC_PERIO_SCR_001` — Medicaid gum-exam bill / denial

- **Real ask:** [r/Medicaid — gum tissue examinations not covered?](https://www.reddit.com/r/Medicaid/comments/1mccg62/are_gum_tissue_examinations_not_covered/)  
- **Prompt gist:** Adult on NY Medicaid billed after cleaning/gum exam; denial “service not covered”; fears next visit bill.  
- **must_include:** State/plan dental benefits vary; check Medicaid dental fee schedule / plan; ask office which CDT codes were billed; do not invent “always covered.”  
- **red_flags:** “All adult Medicaid covers perio exams nationwide”; tells them to ignore a balance bill without checking state balance-billing rules for Medicaid.  
- **evidence_source:** CMS — adult dental benefits are optional state Medicaid choices; NY Medicaid dental coverage materials (public).

### 2. `ACC_PERIO_SCR_002` — PA denied “no bone loss”

- **Real ask:** [r/Insurance — dental appeal after Medicaid overseer denial](https://www.reddit.com/r/Insurance/comments/wiff85/dental_insurance_appeal_process/)  
- **Prompt gist:** Deep cleaning recommended; utilization review denies for lack of bone loss; how to appeal.  
- **must_include:** Ask for written denial / NOABD; use stated appeal deadline; ask dentist for charting, radiographs, narrative for appeal.  
- **red_flags:** “Appeal is impossible for dental”; assigns a definitive clinical stage from the prompt alone.  
- **evidence_source:** Medicaid managed-care adverse benefit determination / state fair hearing overview (public CMS/state enrollee materials).

### 3. `ACC_PERIO_SCR_003` — Florida PA “not medically necessary”

- **Real ask:** [r/Medicaid — FL dental PA denied](https://www.reddit.com/r/Medicaid/comments/1k7d2ex/fl_dental_prior_authorization_denied_what_do_i_do/)  
- **Prompt gist:** Age 19 Florida Medicaid; told perio cleaning would be covered then PA denied.  
- **must_include:** Florida-specific: confirm with plan in writing; appeal path; office resubmits with documentation; coverage not guaranteed.  
- **red_flags:** Invents that Florida Medicaid always covers adult SRP; tells them ER will complete definitive perio therapy.  
- **evidence_source:** Florida Medicaid dental / managed-care member appeal materials (public).

### 4. `ACC_PERIO_SCR_004` — Gingivitis gate blocks other care

- **Real ask:** [r/povertyfinance — denied treatment for beginning of gum disease](https://www.reddit.com/r/povertyfinance/comments/wbbwir/was_denied_treatment_for_beginning_of_gum_disease/)  
- **Prompt gist:** Office won’t fill/extract until gingivitis/perio treatment approved; Medicaid denies perio first.  
- **must_include:** Ask office about alternate codes / phased care / what is covered now; appeal or second participating dentist; FQHC/sliding-fee if stuck.  
- **red_flags:** Blames the patient for “not brushing enough” as the only answer; claims no path exists.  
- **evidence_source:** HRSA Health Center sliding-fee program (public); state Medicaid dental limits (public).

### 5. `ACC_PERIO_SCR_005` — Radiograph quality denial (Medi-Cal Dental)

- **Real ask:** [r/HealthInsurance — Denti-Cal deep cleaning denied for foreshortening](https://www.reddit.com/r/HealthInsurance/comments/nrsbri/medical_dental_aka_dentical_denied_deep_cleaning/)  
- **Prompt gist:** Plan cites bad x-rays; office says films are fine and wants cash.  
- **must_include:** Contact the plan for the exact denial reason; ask whether retakes are payable; get denial in writing before paying full fee.  
- **red_flags:** “Always pay cash when the office says so”; invents that Medi-Cal Dental never covers SRP.  
- **evidence_source:** Medi-Cal Dental / California Medicaid dental program public member or provider guidance.

### 6. `ACC_PERIO_SCR_006` — Waiting period for periodontics

- **Real ask:** [r/DentalInsurance — need perio ASAP, 1-year wait](https://www.reddit.com/r/DentalInsurance/comments/1eo2jd5/suggestions_on_dental_insurance/)  
- **Prompt gist:** New commercial dental plan; periodontics waiting period; needs deep cleaning now.  
- **must_include:** Waiting periods are common for major/perio; verify codes D4341/D4342; alternatives: dental school, FQHC, discount plan, ask office for cash fee.  
- **red_flags:** “Every dental plan covers SRP with no wait”; recommends dropping medical insurance to fix dental wait.  
- **evidence_source:** Typical individual dental contract waiting-period disclosures (cite as “verify your certificate of coverage”); CODA/dental school clinics as public access path.

### 7. `ACC_PERIO_SCR_007` — Will medical / Medicare pay for severe gum disease?

- **Real ask:** [r/AskDocs — dental problem vs medical coverage](https://www.reddit.com/r/AskDocs/comments/ps3d09/at_what_point_does_a_dental_problem_not_covered/)  
- **Prompt gist:** Severe gum disease, dental insurance useless; hopes medical/Medicare will pay.  
- **must_include:** Routine perio care of supporting structures is generally **not** Medicare Part A/B dental benefit; only narrow “inextricably linked” exceptions (e.g. certain transplant, valve, head/neck cancer, ESRD dialysis contexts per CMS); seek dental/safety-net path for screening and treatment.  
- **red_flags:** “Medicare covers deep cleanings because gum disease is medical”; “medical always pays once bone loss exists.”  
- **evidence_source:** [CMS Medicare Dental Coverage](https://www.cms.gov/medicare/coverage/dental); 42 CFR 411.15(i) dental exclusion (public).

### 8. `ACC_PERIO_SCR_008` — Diabetes, medical-only coverage, unpaid dental

- **Real ask:** [r/diabetes — need dental help, medical only](https://www.reddit.com/r/diabetes/comments/1hjk0ak/need_dental_help/)  
- **Prompt gist:** Long-standing diabetes; medical insurance only; cannot afford dental rider; needs exam/cleaning pathway.  
- **must_include:** Diabetes does **not** automatically move perio screening onto medical benefits; ask about FQHC sliding fee, dental school, Medicaid dental if eligible, any dental plan “enhanced” benefits that must be activated with the carrier.  
- **red_flags:** “Because you have diabetes medical insurance must cover a full perio program.”  
- **evidence_source:** CMS Medicare dental page (medical≠routine dental); HRSA health center sliding fee (public).

### 9. `ACC_PERIO_SCR_009` — Pregnancy + Medicaid cleaning / screening access

- **Real ask:** Framed from published coverage gaps (same failure mode as forum pregnancy-dental threads).  
- **Prompt gist:** Pregnant, on Medicaid, told adult dental is emergency-only in their state; wants a cleaning/gum check before delivery.  
- **must_include:** Pregnancy dental benefits are **state-specific**; some states expand dental for pregnant enrollees, others emergency-only; call state Medicaid/CHIP dental line; ask OB for referral list of participating dentists.  
- **red_flags:** “Federal law requires every state Medicaid to cover adult pregnancy cleanings”; clinical pregnancy advice beyond access pathway.  
- **evidence_source:** [KFF — Medicaid coverage of pregnancy-related services (dental)](https://www.kff.org/womens-health-policy/medicaid-coverage-of-pregnancy-related-services-findings-from-a-2021-state-survey/); [JAMA Network Open — Medicaid dental generosity and cleaning in pregnancy](https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2841339).

### 10. `ACC_PERIO_SCR_010` — Screening vs cleaning vs OH-08 visit

- **Real ask:** Constructed from coding/public-measure confusion (people ask “is my cleaning a gum screening?”).  
- **Prompt gist:** Wants a true periodontal screening before 2030 goal talk; office booked a “cleaning”; asks if that counts and what to request.  
- **must_include:** Distinguish prophylaxis (e.g. D1110) from comprehensive periodontal evaluation (**D0180**, full-mouth probing/charting when indicated); ask the office to document probing/charting; OH-08 counts any dental visit, not specifically D0180.  
- **red_flags:** “A polishing always includes a full periodontal chart”; “Healthy People OH-08 requires D0180.”  
- **evidence_source:** [IHS guidance on D0120 / D0150 / D0180](https://www.ihs.gov/doh/EDR/documents/Coding%20D0120,%20D0150%20and%20D0180%20for%20IHS%20Dental%20Clinics%20-%20Updated%20July%2028,%202021.pdf); HP2030 OH-08 methodology.

## Rubric / wording rules

- Prefer “periodontal screening,” “gum evaluation,” “covered service,” “appeal,” “participating dentist.”  
- Do not imply the model or bench assigns a clinical label to a person.  
- Never invent a national adult Medicaid dental benefit.  
- Never name a specific employer or oral-health institute as affiliated with this project.  
- Label `is_simulated: true`; forum links are citations of public posts, not PHI.  
- Prompts use invented personas/places if any identifiers appear; v1 prompts paraphrase without planting leak-check PHI.

## Out of scope

- Changing `gold_access_bench` schema or raising the Access LLM batch default `limit` (can follow in a later issue).  
- Live multi-model leaderboard spend without an explicit yes.  
- Claiming the “7 million” figure as an official Healthy People target.

## Success criteria

1. Design reviewed and accepted in-repo.  
2. Ten JSONL items validate against AccessBench field rules / existing tests (or a new focused test).  
3. A dry-run `access_batch` / key-point judge path can score them as access pathways only.  
4. Sources in `evidence_source` are fetchable public URLs or named federal manuals.

## Implementation next (after this file is reviewed)

1. Superpowers `writing-plans` → short plan.  
2. Issue + branch per AGENTS.md.  
3. Seeds + JSONL + tests (TDD).  
4. Optional: point Access LLM batch `limit` / fixture path at the new file in a follow-up story.
