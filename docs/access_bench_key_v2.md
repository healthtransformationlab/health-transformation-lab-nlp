# AccessBench answer keys v2 (spec 045 US5, #957)

> Personal learning project, not affiliated. Every question is synthetic. The changes below come from five AI models'
> reviews (ChatGPT, Gemini, Microsoft Copilot, Perplexity, Grok) and Claude Code's own, consolidated in
> [access_bench_external_reviews.md](access_bench_external_reviews.md). They are a proposal for the owner's approval.

**Not yet verified.** The sources added here (regulations, CMS, VA, DOJ and ACOG pages) are named in each item's
`evidence_source`, but this session couldn't open those sites, so every changed item keeps `source_verified_date`
null. No new link or phone number was added to any key. Check the sources before any score is published.

## What changed everywhere

- **Positive points only.** "Does not…" and "Omits…" points are gone: errors are red flags, and privacy is the gate
  (spec 045 US1, US4). Each key has 3–4 points a good answer must make.
- **Realistic red flags** replace strawmen: "a denial means you owe", "pay cash and get reimbursed later", "a
  resubmission stops the appeal clock", unsafe transfers, upcoding.
- **Natural prompts.** No "simulated", no MRN, no "under-21 pathway" (it gave the answer away); a test checks this.

## Item by item

| Item | Main change | Reviewers who asked |
|---|---|---|
| SCR_001 NY Medicaid bill | A Medicaid member generally can't be billed for a covered service (42 CFR 447.15); get the codes and denial reason; don't sign to pay | 4 of 5 (balance billing), all 5 (codes) |
| SCR_002 appeal | 60-day plan appeal; file on time, a resubmission doesn't stop the clock; fair hearing and expedited appeal | all 5 |
| SCR_003 19, Florida | **EPSDT covers medically necessary dental under 21**; don't pay cash before the appeal; prompt no longer says "under-21 pathway" | 4 of 5 (ChatGPT, Gemini, Perplexity, Grok) |
| SCR_011 (new) | Contrastive pair of SCR_003 at age 23: EPSDT no longer applies | ChatGPT (contrastive families), Copilot, Perplexity, Grok (broaden) |
| SCR_004 painful tooth | Urgent or emergency care first for swelling or fever; covered treatment now; second dentist with x-rays; red flag for upcoding | 4 of 5 |
| SCR_005 Medi-Cal x-rays | A documentation denial isn't non-coverage; retake or resubmit; payment-in-full rule before paying cash | all 5 |
| SCR_006 waiting period | Waiver for prior coverage; get the evaluation now; discount plans aren't insurance; strawman flag replaced | all 5 |
| SCR_007 Medicare | **Medicare Advantage may include dental**; ask which Medicare they have | 3 of 5 (ChatGPT, Gemini, Perplexity) |
| SCR_008 diabetes | Source changed from the Medicare exclusion to 45 CFR 156.115(d) (medical plans); don't delay care | all 5 |
| SCR_009 pregnancy | Domain fixed; ask how long coverage lasts after delivery; care is safe in pregnancy (ACOG); narrowed clinical-advice flag | all 5; 3 of 5 on safety |
| SCR_010 D0180 | **Healthy People OH-08 point and flag removed** from scoring, kept as a methodology note | 3 of 5 remove (ChatGPT, Gemini, Perplexity); Copilot and Grok keep. **Owner's call** |
| INS_PHI_001 broken tooth | Check the child's Medicaid/CHIP; health centers serve regardless of ability to pay; urgent care first | 4 of 5 |
| TRV_PHI_001 ride | Book the dentist first, then the ride; confirm the cleaning is covered; MRN removed from the prompt | all 5 |
| VET_PHI_001 VA dental | Class V is Veteran Readiness and Employment; VADIP; community care needs eligibility; "simulated" removed | all 5; 4 of 5 VADIP |
| ADA_PHI_001 wheelchair | No surcharge for accommodations; can't require a helper; DOJ complaint; unsafe-transfer flag | all 5 |
| EPS_PHI_001 child on CHIP | Medicaid/expansion CHIP (EPSDT) versus separate CHIP first; leading "EPSDT" removed from the prompt | all 5 |

The control answer `control:good` for SCR_007 now expects all four points (it already named Medicare Advantage).

## Not done here

- The owner's decision on OH-08 (removed here; revert SCR_010's last point and flag to keep it).
- Opening and checking each added source; new topics beyond dental coverage (emergency care, orthodontics) as their
  own item set.
