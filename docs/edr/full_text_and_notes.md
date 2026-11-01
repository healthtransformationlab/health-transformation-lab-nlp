# Health Transformation Lab: PerioBench, the dental record (EDR) study, executive pitch: full text and notes
A personal idea, not affiliated with or endorsed by any organization. Built from `slides/` by `docs/build_decks.py`; edit the slides, then rebuild.

## Slide 1 — cover

PerioBench · executive pitch · the dental record (EDR) · October 2026
Gum disease is in the dental record.
It's hard to count.
PerioBench: can finding gum disease accurately in the dental record improve care for millions of patients? Checked against gum specialists, built and tested end to end on synthetic records.
Health Transformation Lab
Synthetic patient records
Two open benchmarks:
PerioBench
, finding gum disease in dental records, built and tested on synthetic records; and
OralHealthBench
, AI answers on oral health and getting care, planned on top of GlobalDentBench.
John Bowyer · personal project, not affiliated with any organization

**Speaker notes:** Gum disease is one of the most common chronic diseases in adults, and it is written down at almost every dental visit. But it is written down in pieces: a checkbox here, a billing code there, measurements, and a free-text note. That makes it hard to count the same way across clinics, and so hard to study at scale, link to diabetes, or see whether care is working. PerioBench asks one question: can finding gum disease accurately in the dental record improve care for people with it, so it is found earlier, treated, followed over time and managed alongside diabetes? Agreement with gum specialists reviewing the same records is how we check the result; better patient care is the goal. Everything shown is on synthetic records, built so the right answer is known; it is a rehearsal of the real study, not a result on real patients. This is a personal project, not any organization's plan.

## Slide 2 — problem

The problem
Common, linked to diabetes, and invisible in the data
US adults 30+ with teeth
42%
have gum disease (periodontitis); 7.8% have the severe form.
Diabetes
Both ways
Gum disease and diabetes are linked: each is associated with worse control of the other.
In the record
7 places
where a dental chart holds evidence of gum disease: notes, forms, codes, measurements. They often disagree.
Dental records rarely say plainly whether a patient has gum disease.
The status has to be worked out from the evidence, the way a specialist would, before anyone can count it.
NHANES 2009–2014 (Eke et al., J Am Dent Assoc 2018) · EFP and IDF consensus report (Sanz et al., 2018) · seven evidence types: this repo · 2

**Speaker notes:** Three facts. One: about 42 percent of US adults aged 30 and over who have teeth have periodontitis, gum disease that destroys the attachment and bone around teeth, and 7.8 percent have the severe form; that is the national survey, NHANES 2009 to 2014, published by Eke and colleagues in 2018. Two: gum disease and diabetes are linked in both directions; the European Federation of Periodontology and the International Diabetes Federation ask doctors and dentists to manage the two together. Three, and this is the one we can fix: in the dental record, whether a patient has gum disease is rarely written down once, reliably. It is spread over seven kinds of evidence: the clinician's note, an exam form with a score and a checkbox, the procedure codes done and planned, the diagnosis codes on those procedures, and the gum measurements. They often disagree. So before anyone can count gum disease across clinics, or link it to diabetes in the medical record, someone, or something, has to read the chart and work out the status. If asked for sources: Eke PI et al., Periodontitis in US adults: NHANES 2009-2014, JADA 2018, https://doi.org/10.1016/j.adaj.2018.04.023; Sanz et al., J Clin Periodontol 2018, https://doi.org/10.1111/jcpe.12808. The seven evidence types are this study's design; see the evidence rules page.

## Slide 3 — solution

What we built
Read the whole record, then prove it against specialists
1
Synthetic patients
8 clinics, visits over time: notes, forms, codes, gum measurements, with fake names in the notes
2
Privacy first
Names, dates and IDs removed; a final check holds back any note with one left
3
A common format
The record in OMOP, the format medicine already uses, so dental links to medical
4
Rules and AI read it
Rules combine the whole record; AI models read the note alone
5
Specialists check it
Periodontists label the same 240 charts, each on their own (simulated reviewers so far)
6
The acceptance test
AI passes only if it agrees with them as often as they agree with each other
Built to run on a real extract unchanged:
the same code, tests and dashboards, once a de-identified dataset and its approvals exist.
Synthetic patient records · Health Transformation Lab · the dental record (EDR) · 3

**Speaker notes:** This is the whole pipeline, and it runs end to end today on synthetic data. One: we generate synthetic patients across 8 clinics, visit after visit, with every kind of evidence and fake names in the notes, so the privacy step is tested too. Two: names, dates and IDs are removed, and a final check holds back any note that still has one. Three: the record goes into OMOP, the common data format medicine already uses, which is what lets a dental finding sit next to a diabetes record. Four: rules combine the whole record, and AI models read only the free-text note, for the many charts where the structured fields are missing. Five: gum specialists label the same 240 charts, independently; until real specialists do, simulated reviewers stand in so the reliability code can be tested, and their numbers are never shown as results. Six: the acceptance test. An AI method passes only if it agrees with the specialists at least as often as they agree with each other; that is the standard the OHDSI community uses to check how well records identify a disease. Because it is synthetic, we know the right answer for every chart, so we can test the test. If asked about the platform: Databricks and Unity Catalog, MLflow for models, Postgres and Lakebase for OMOP; Python and R give the same numbers.

## Slide 4 — results

What it shows so far (synthetic)
The whole record answers it. The note alone nearly does.
Whole record, rules
234 of 240
charts given the right status, combining the evidence, gum measurements first.
Note only, trained AI
219 of 240
right from the free-text note alone (ModernBERT, with a rule for the most severe stage).
Note only, medical AI as is
196 of 240
for MedGemma 4B untrained, with the same stage 4 rule; the newer MedGemma 1.5 4B got 185. Both close to keyword rules (189).
Gum measurements alone
193 of 240
right, but 45 charts had no measurements to read: one piece of evidence is not enough.
Training beats size:
a small model trained on dental notes beat a bigger medical AI used as is. Synthetic notes are easier than real ones, so expect the gaps to widen.
Synthetic charts, scored against the generator's truth: not clinical performance · real model runs on CPU and Kaggle GPUs, 2026-10-26 to 2026-10-28 · 4

**Speaker notes:** These are real model runs, on synthetic charts, scored against the generator's truth; they are not clinical performance, and agreement with simulated reviewers is a dry run we do not show. Four numbers out of 240 review charts. Rules that combine the whole record, reading the gum measurements first, got 234 right. Reading only the free-text note, a small model trained on dental notes, ModernBERT with a keyword rule for the most severe stage, got 219. A bigger medical AI used as is, without training and with the same stage 4 rule: MedGemma 4B got 196, and the newer MedGemma 1.5 4B got 185. Both are close to simple keyword rules at 189; on 240 charts neither can be told apart from them. Alone they get about 187 and 182. And any single piece of evidence falls short: the gum measurements alone got 193 right, because 45 of the 240 charts had no measurements at all. Two lessons: combine the evidence, and train on the domain. If asked about uncertainty: every number has a 95 percent bootstrap interval on the full results page; on 240 charts, many methods cannot be told apart. If asked whether MedGemma can improve: few-shot and fine-tuned runs are next, on a GPU. If asked why synthetic: no identifiable patient data may be used here; synthetic data lets us build and test everything, including the privacy checks, before any approvals.

## Slide 5 — economics

What it costs
Software costs depend on the model; choose the least costly one that passes.
By hand
33,333 h
a million visits, one specialist, 2 minutes a chart
To prove it
~31 h
233 charts, 4 reviewers: the acceptance test
By software, a million visits
Model
Reads
Cost
Small trained model, own hardware
the note
under $15*
Open LLM, hosted (Llama 3.3 70B)
the note
~$260
Frontier LLM (Gemini 3.1 Pro, Claude Fable 5.1)
the note
~$1,100–$5,500
Frontier LLM, 3 calls a visit
whole record, examples, reasoning†
~$260k–$1.2M
List prices: Databricks (2026-10-26), ai.google.dev, claude.com (2026-10-28) · *illustrative compute · †assumed 20k tokens in, 4k out a call · 5

**Speaker notes:** The economics, and it depends on the model. Reading a million visits by hand, at the protocol's pace of about 2 minutes a chart, is 33,333 hours of a specialist's time. Software for the same million visits ranges from under 15 dollars to about 1.2 million, depending on the model. A small model trained on dental notes, on our own hardware, costs under 15 dollars, at illustrative compute prices. An open model hosted per token, Llama 3.3 70B at Databricks list price, costs about 260 dollars for the note alone. A frontier commercial model at list price costs about 1,100 dollars for the note alone with Google's Gemini 3.1 Pro, and about 5,500 with Anthropic's Claude Fable 5.1. And if a frontier model reads the whole record, with worked examples and reasoning, three calls a visit, it is about 260 thousand dollars with Gemini and about 1.2 million with Fable; batch pricing halves either. Those token counts are assumed, about 20 thousand in and 4 thousand out a call, not measured. The note-only token count is estimated from our synthetic notes, characters divided by four, and they are shorter than real ones; the prompt and answer lengths are assumed. The acceptance test is small: about 31 specialist hours, 233 charts each read by 4 reviewers. So the choice is the least costly model that passes the acceptance test. If asked for a dollar figure for people: at an illustrative 100 dollars an hour, validation is about 3,100 dollars and reviewing everything by hand about 3.3 million. If asked about errors: the study also counts unsafe errors, such as missing severe disease, and reports them separately.

## Slide 6 — ask

The ask
From synthetic to real
What we do
Run the same pipeline on a de-identified extract, inside its owner's environment and approvals
Four gum specialists label the validation charts, each on their own (~8 hours each)
Publish the acceptance-test result, good or bad, with the code
If it works
Gum disease countable across clinics, in the format medicine uses
The medical-dental link, such as diabetes, studied at scale
A tested reader that checks AI answers against the record
The ask:
a data partner willing to run it on a de-identified extract in its own environment, under its own approvals; four periodontists for about a day each; and a few days of GPU time. No partner has been contacted.
Health Transformation Lab · the dental record (EDR) · 6

**Speaker notes:** The ask is small, because the build is done. We need three things. One: a data partner willing to run the pipeline on a de-identified extract, under its own approvals; the code is built to run unchanged on a real extract, and nothing leaves their environment. Two: four gum specialists, about a day each, to label the validation charts independently; that is the 31 hours on the previous slide. Three: a few days of GPU time, for the larger models. In return: we publish the acceptance-test result, good or bad, with the code. If it works, gum disease becomes something you can count across clinics, in the same format as the medical record, so the link with diabetes can be studied at scale; and the same reader becomes a way to check AI answers against the record, which is the other path on the landing page. No partner has been contacted, and nothing here is any organization's plan. If asked what could go wrong: real notes are harder than synthetic ones, and the AI may not pass; that is still a publishable answer.

## Slide 7 — drill

Health Transformation Lab · the dental record
Drill-down
Backup slides for questions. The full science is on the study page.
The order the evidence is read in, and why it changes the answer
How we know it is right: the acceptance test, and an AI that checks AI
Privacy first: removing names before anything reads a note
How this path feeds the other: test questions with known right answers

**Speaker notes:** Do not present these. Jump to one only when asked. Everything here is detailed on the study page, docs/edr/README.md, with every method, interval and model.

## Slide 8 — evidence

The order matters
Same evidence, read in a different order: a different answer
Gum measurements first
234 of 240
right: then the note, exam form and codes fill the gaps (the first rule set, v0).
Exam form first
173 of 240
right (72%): the study design's order, exam form, diagnosis codes, note, then measurements.
Orders to test
24
four sources can be ranked 4×3×2×1 ways; each ranking is scored against the specialists.
So the order is a finding, not a setting:
the ranking that agrees best with the specialists is the one to keep. Procedure codes are a rough guess from the treatment, so they are compared, not used.
Synthetic charts, scored against the generator's truth · 2017 AAP/EFP classification · rules and worked examples: docs/evidence_rules.md · 8

**Speaker notes:** A dental chart holds seven kinds of evidence: the clinician's note; the exam form, with a gum score and a status checkbox; the procedure codes done and planned; the diagnosis codes on those procedures, done and planned; and the probing chart of gum measurements, turned into a stage with the 2017 American Academy of Periodontology and European Federation of Periodontology worksheet. Procedure codes are only a rough guess from the treatment, so they are compared, not used. When the other sources disagree, the rules take the first one, in a fixed order, that gives a status. The order matters a lot. Reading the gum measurements first, the first rule set, gets 234 of 240 synthetic charts right; it is the 234 on the results slide. The study design's order, exam form first, then diagnosis codes, the note, and the measurements last, gets about 173, 72 percent. On synthetic charts the measurements are the generator's own evidence, which flatters reading them first; on real charts the answer may differ. Four sources can be ranked 24 ways; each ranking is scored against the specialists, and the one that agrees best is kept. A radiograph reading can only raise the stage.

## Slide 9 — acceptance

How we know it is right
The acceptance test, and an AI that checks AI
The bar
As good as us
AI passes only if it agrees with specialists as often as they agree with each other.
AI as checker
83%
of charts where a general-purpose AI's own reading matched the answer key; 53% on hard notes.
Catching mistakes
26%
of the best note model's mistakes caught by that AI checker: mostly near-misses, one stage off.
So on real notes, people still set the answer key:
the AI checker spots weak methods, but cannot yet stand in for specialists on good ones.
Synthetic charts; LLM judgments checked against the generator's truth · the bar: OHDSI 2023 plenary on case validation; npj Digit Med 2025 · 9

**Speaker notes:** How do we know an answer is right? On real records there is no answer key, so the acceptance test is the bar: an AI method passes only if it agrees with the specialists at least as often as they agree with each other, the standard from the OHDSI 2023 plenary on case validation, with the LLM review work published in npj Digital Medicine in 2025. We also tested whether a general-purpose AI, a large language model, could stand in for the answer key. Reading each note itself, it matched the answer key on 83 percent of charts but only 53 percent of hard notes, the ones that leave out what the answer key is built from. Asked whether a method's answer was right, it caught most mistakes of weak methods, but only 26 percent of the best note model's, which are near-misses such as one stage off. So it cannot replace specialists yet. These are AI judgments on synthetic notes, checked against the generator's truth. If asked about statistics: kappa for agreement beyond chance, 95 percent bootstrap intervals over charts, and unsafe errors counted separately.

## Slide 10 — privacy

Privacy first
No note reaches a model with a name left in it
Identifiers missed
115 of 2,714
by the best combination of tools on 400 synthetic notes; the final check holds those notes back.
Dental words damaged
41 of 2,462
terms that look like names or codes (Glickman, Gracey 11/12) removed by mistake.
Methods compared
15
pattern matching, single AI tools, and combinations, with a dental-word guard.
Two numbers that pull against each other:
remove too little and patients are at risk; remove too much and the note the AI reads is damaged.
Synthetic notes with fake names and dates; also tested on public benchmark sets · Health Transformation Lab · the dental record (EDR) · 10

**Speaker notes:** Before any software or person reads a note, names, dates and IDs come out. We compared 15 methods on 400 synthetic notes with fake identifiers planted in them. The best was a combination of tools with a guard that protects dental words; it still missed 115 of 2,714 identifiers, which is why a final check holds back any note with one left, and nothing goes on until it passes. It also removed 41 of 2,462 dental terms that look like names or codes, such as Glickman or Gracey 11/12, which would damage what the AI reads. The two numbers pull against each other, like a spam filter. We also tested on public benchmark sets, including published, already de-identified case reports. All synthetic, or published by others already de-identified.

## Slide 11 — connect

How the two paths connect
The record gives the test its right answers
PerioBench
The record
Synthetic patients whose right answer is known, in the format medicine uses.
The bridge
Test questions
Case questions written from those patients, with the right answer already scored.
OralHealthBench
AI answers
AI tested where medicine meets dentistry and access to care, in public.
One way to test AI, narrow to broad:
the same models, harm grades and leaderboards score AI first on gum charts, then on case questions, then on broader medical-dental ones.
OralHealthBench pitch: docs/pitch/ · Health Transformation Lab · the dental record (EDR) · 11

**Speaker notes:** The landing page has two paths, and this is how they meet. This path builds synthetic patients whose right answers are known, in the same format medicine uses. That makes them a source of test questions: case questions written from those patients, with the right answer already scored. The other path, OralHealthBench, is about testing AI where medicine meets dentistry and on access to care, in public. Both test AI the same way: the same models, harm grades and leaderboards, scoring AI first on gum charts, then on case questions from synthetic patients, then on broader medical-dental questions. The OralHealthBench pitch is in docs/pitch.
