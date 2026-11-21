# Health Transformation Lab: PerioBench, the dental record (EDR) study, executive pitch: full text and notes
A personal idea, not affiliated with or endorsed by any organization. Built from `slides/` by `docs/build_decks.py`; edit the slides, then rebuild.

## Slide 1 — cover

PerioBench · executive pitch · the dental record (EDR) · October 2026
Gum disease is in the dental record.
It's hard to count.
PerioBench: can finding gum disease accurately in the dental record improve care for millions of patients? Checked against gum specialists, built and tested end to end on synthetic records.
Health Transformation Lab ·
Evidence you can check
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

## Slide 3 — tests

Three tests, three kinds of model
Find the disease, protect the patient, count the teeth
Phenotyping
What stage of gum disease does this visit show?
Reads the note, or the whole record. Compares rules, BERT-family AI trained on notes, and large language models.
203 of 223
charts right, the best AI on the note alone
De-identification
Which words are private, and must go first?
Reads the note. Compares pattern rules, AI that tags each word, a Databricks service, and combinations that keep dental terms.
115 of 2,714
identifiers left in, the best combination
Tooth loss
Was this missing tooth lost to gum disease?
Reads tables, not text: probing, extraction codes, missing teeth. Compares logistic regression and XGBoost.
AUC 0.89 to 0.90
on 469 held-out teeth
How they fit:
privacy runs first on a real note; tooth loss supplies the count that decides stage 4. Each has its own scores, costs and pass bar: the next three slides take them one at a time.
Synthetic patient records, scored against the generator's answer key · Health Transformation Lab · the dental record (EDR) · 3

**Speaker notes:** PerioBench is three tests, and people often blur them, so here they are side by side. First, phenotyping: what stage of gum disease does this visit show? That is the study's answer. Rules read the whole record; AI reads the note alone. We compare BERT-family models trained on our notes with large language models used as they come, and the best AI gets 203 of 223 synthetic charts right. Second, de-identification: before anyone or any AI reads a real note, names, dates and record numbers have to go. Here the AI does a different job, labelling each word private or not, and the best combination leaves 115 of 2,714 identifiers in, while keeping the dental terms that look like names. Third, tooth loss: was a missing tooth lost to gum disease? There is no text here, so no BERT: logistic regression and XGBoost read the probing measurements and extraction codes, with an AUC of about 0.9 on held-out teeth. Why it matters: five or more teeth lost to gum disease is what makes stage 4. Every number is synthetic, scored against the generator's own answer key. Each question has its own leaderboard and its own pass bar, so cost is never compared across them: the next three slides put each one's cost beside its quality. The drill-down for each test ranks its models the same way, with paired tests and what drives the result.

## Slide 4 — phenotyping-cost

Question 1 of 3 · Finding gum disease in the record · cost beside quality ·
explore it ↗
A small trained model is in the top group at about $40 a million notes. The LLMs we ran cost more and are not in it.
Method
Reads
Right status, per 100 charts (95% CI)
Could rank first?
Cost, a million notes
Rules, gum measurements first †
whole record
92.8
(89.2–96.0)
yes
CPU rules, not priced
Small trained model
(ModernBERT-large) + stage 4 rule †
the note
91.0
(87.0–94.2)
yes
~$40*
Word counts (TF-IDF) + stage 4 rule †
the note
85.7
(80.7–89.7)
no
under $1
Open LLM, hosted (Llama 3.3 70B)
the note
83.9
(78.9–88.8)
no
~$260
Own-GPU medical LLM (MedGemma 1.5 4B)
the note
78.5
(73.1–83.4)
no
~$140*
Frontier LLM (Gemini 3.1 Pro, Claude Fable 5.1)
the note
not run
–
~$1,100–$5,500
Frontier LLM, 3 calls a visit
whole record
not run
–
~$260k–$1.2M
Pass bar:
agree with four gum specialists as often as they agree with each other (the acceptance test).
Not run yet, so no method has passed.
Until then the stand-in is the top group on the synthetic answer key: methods whose 95% rank range reaches first place.
Synthetic: the 223 review charts, scored against the generator's answer key (docs/results.md, Phenotyping) · † uses the same 2017 rules as the answer key: an advantage real records won't give · *assumed throughput at an illustrative GPU price (costs.yaml) · LLM list prices 2026-10-26 and 2026-10-28 · 4

**Speaker notes:** This is the first of the three questions: what gum-disease status a chart shows, which researchers call phenotyping. Each row puts a method's cost for a million notes beside how often it gave the right status on our 223 synthetic review charts, with its 95 percent interval. The pass bar is the acceptance test: a method passes if it agrees with four gum specialists as often as they agree with each other. That test needs real specialists and has not been run, so nothing on this slide has passed yet. Until it is run, the stand-in is the top group: on resampled charts, could this method come first? Three can, and the table shows two of them: the whole-record rules and a small model trained on notes, ModernBERT-large with a rule for stage 4, at about 40 dollars a million notes on our own GPU, at an assumed speed and an illustrative price. The third, BioClinical ModernBERT-large with the same rule, is the same size and cost, and scores 90.1. Are the less costly models as good? Word counts cost under a dollar but are not in the top group: 85.7, and their interval reaches only 89.7. The open LLM we ran, Llama 3.3 70B, costs about 260 dollars and scores 83.9; the medical model MedGemma about 140 and 78.5. Neither is in the top group, so on this question paying more for a bigger general model did not buy a place in it. Frontier models such as Gemini 3.1 Pro and Claude Fable 5.1 have not been run on this question, so we do not know whether they are as good; we show their price only. Two cautions. The dagger rows use the same 2017 rules that made the answer key, which flatters them on synthetic charts. And synthetic notes are shorter and easier than real ones. If asked about the full table: it is in the appendix and in docs/results.md, every method with its interval and rank range.

## Slide 5 — tooth-loss-cost

Question 2 of 3 · Was a missing tooth lost to gum disease? · cost beside quality ·
explore it ↗
Two small models on CPU, no LLM run, and no pass bar set yet. They score well on extractions, less well on teeth already missing.
Method
Learns from
AUC, held-out extractions (95% CI)
AUC, teeth missing at the first visit
Cost
Logistic regression
completed extractions
0.89
(0.86–0.92)
0.59
CPU, not priced
XGBoost
completed extractions
0.90
(0.87–0.93)
0.63
CPU, not priced
Logistic regression
completed + planned
0.88
(0.85–0.92)
0.64
CPU, not priced
XGBoost
completed + planned
0.90
(0.87–0.93)
0.70
CPU, not priced
Any LLM
–
not run
not run
–
Pass bar: none set yet.
The analysis plan fixes what is measured (AUC, calibration, sensitivity and specificity), not the score that passes. It should be set on the teeth missing at the first visit: those are the ones the model is used for.
AUC:
the chance the model ranks a tooth lost to gum disease above one lost for another reason. 0.5 is a coin toss; 1 is perfect.
Synthetic Open Dental-style extract, scored against the generator's answer key: 469 held-out extractions; teeth missing at the first visit, generator seed 42 (docs/tooth_loss.md, after the tooth-table fixes) · structured tables only, no note · 5

**Speaker notes:** The second question is narrower: when a tooth is missing, was it lost to gum disease? It matters because five or more teeth lost to gum disease is what makes stage 4. This one reads tables, not text: extraction codes, probing measurements, the teeth missing at the first exam. Only two kinds of model have been run, logistic regression and XGBoost, both small enough to run on an ordinary CPU, so we have not priced them; there is no costly option to compare them with, because no LLM has been run on this question. They score well on extractions whose reason was recorded and held out of training: an AUC of about 0.9. But on the teeth that were already missing at the first visit, which is what the model is actually used for, the AUC drops to between 0.59 and 0.70. And there is no pass bar yet: the analysis plan says what is measured, not what score passes. So the honest answer to "is the less costly model good enough" here is that we have not set what good enough means. That is part of the ask: the study lead sets the bar before a real record is read. If asked about other models: a comparison with more kinds of model is in progress in its own pull request; the full score table, with sensitivity and specificity, is in the appendix. All synthetic.

## Slide 6 — deid-cost

Question 3 of 3 · Removing names, dates and IDs · cost beside quality ·
explore it ↗
Two AI taggers plus patterns are in the top group for about $100 a million notes. Azure and Amazon are not run.
Method
Identifiers left in, of 2,714 (95% range of the rate)
Could rank first?
Dental words removed, of 2,462
Engine cost, a million notes
Patterns alone
645
(22.2–25.4 in 100)
no
0
under $1
Presidio + patterns + guard
376
(12.6–15.2 in 100)
no
122
~$5
Stanford AI + patterns + guard
226
(7.3–9.4 in 100)
no
41
~$23
Stanford AI + OBI AI + patterns + guard
115
(3.5–5.1 in 100)
yes
41
~$98
Routed by identifier type + guard
129
(4.0–5.6 in 100)
yes
154
~$103
Databricks AI mask + patterns + guard
155
(4.9–6.6 in 100)
yes
2
~$295
Paid services (Azure, Amazon) and our LLM prompt
not run
–
not run
~$18–$2,650
Pass bar: no leak rate set yet.
Every method leaves some identifiers in. On synthetic notes a final check holds back any note with one left, because we know what was planted; on real notes only a second scan and a person checking 1 in 1,000 notes (about $3,000 a million) remain. Until a bar is set: the top group, fewest left in.
Synthetic: 400 notes with fake identifiers, scored against what was planted (docs/results.md, De-identification) · engine cost: measured speed at an illustrative $1 CPU hour; AI mask and paid services at list price, 2026-10-26 (docs/deidentification.md) · 6

**Speaker notes:** The third question comes first in practice: before anyone or any AI reads a real note, names, dates and record numbers have to come out. We planted 2,714 fake identifiers in 400 synthetic notes, and count how many each method leaves in, with its 95 percent range, and how many dental words it removes by mistake, words like Glickman or Gracey that look like names. There is no pass bar set as a leak rate yet. On synthetic notes a final check holds back any note with an identifier left, but only because we know every identifier we planted. On real notes nothing is known in advance, so what remains is a second scan for anything shaped like an identifier and a person checking one note in a thousand, about 3,000 dollars a million notes whichever method is used; that review is most of the cost. That is why the leak rate matters, and why a bar has to be set. Until a bar is set we use the top group: methods that could rank first on leaks. Are the less costly ones as good? No: patterns alone cost under a dollar but leave 645 in; Presidio with patterns about 5 dollars and 376; the Stanford tagger with patterns about 23 dollars and 226. The top group, the methods that could rank first, starts at about 98 dollars: the Stanford and OBI taggers together with patterns and the dental-word guard, 115 left in and 41 dental words removed; routing by identifier type is in the same group. Databricks' AI mask with patterns is in the same group and damages only 2 dental words, but at about 295 dollars. The paid services, Azure and Amazon, and our own LLM prompt have not been run, so we show their prices only, from about 18 to about 2,650 dollars. Engine costs use measured speeds on CPU at an illustrative node price. All synthetic.

## Slide 7 — ask

The ask
From synthetic to real
What we do
Run the same pipeline on a de-identified extract, inside its owner's environment and approvals
Four gum specialists label the validation charts, each on their own (~8 hours each)
Set the pass bars for tooth loss and de-identification before a real record is read
Publish each result against its bar, good or bad, with the code
If it works
Gum disease countable across clinics, in the format medicine uses
The medical-dental link, such as diabetes, studied at scale
A tested reader that checks AI answers against the record
The ask:
a data partner willing to run it on a de-identified extract in its own environment, under its own approvals; four periodontists for about a day each; and a few days of GPU time. No partner has been contacted.
Health Transformation Lab · the dental record (EDR) · 7

**Speaker notes:** The ask is small, because the build is done. We need three things. One: a data partner willing to run the pipeline on a de-identified extract, under its own approvals; the code is built to run unchanged on a real extract, and nothing leaves their environment. Two: four gum specialists, about a day each, to label the validation charts independently; that is the 31 hours in the appendix's cost slide. Three: a few days of GPU time, for the larger models. And before any real record is read, the study lead sets the two pass bars that are still missing: the score a tooth-loss model must reach on teeth missing at the first visit, and the leak rate a de-identification method must stay under. In return: we publish each question's result against its bar, good or bad, with the code. If it works, gum disease becomes something you can count across clinics, in the same format as the medical record, so the link with diabetes can be studied at scale; and the same reader becomes a way to check AI answers against the record, which is the other path on the landing page. No partner has been contacted, and nothing here is any organization's plan. If asked what could go wrong: real notes are harder than synthetic ones, and the AI may not pass; that is still a publishable answer.

## Slide 8 — drill

Health Transformation Lab · the dental record
Drill-down
Backup slides for questions. The full science is on the study page.
What "passes" means for each question, and how cost was computed (
interactive version
)
Each question's full scores: finding gum disease, tooth loss, removing names
How the models rank in each test, and what drives their scores
The order the evidence is read in, and why it changes the answer
How we know it is right: the acceptance test, and an AI that checks AI
Who it is for, and what we built
How this path feeds the other: test questions with known right answers

**Speaker notes:** Do not present these. Jump to one only when asked. Everything here is detailed on the study page, docs/edr/README.md, with every method, interval and model; how the models rank in each of the three tests, and what drives their scores, is on its drill-down pages (docs/model_drivers.md for phenotyping).

## Slide 9 — passes

Appendix · What "passes" means
One question has a pass bar, not yet run. Two have none set.
Finding gum disease
Bar:
agrees with four gum specialists at least as often as they agree with each other: mean Cohen's kappa, a margin of 0.05 fixed before looking (OHDSI case validation).
Status:
not run. The reviewers so far are simulated, a dry run we don't show as a result.
Stand-in:
could rank first on the synthetic answer key: the 95% range of its rank, over chart resamples shared by every method, reaches first place.
Tooth loss
Bar:
none set. The analysis plan fixes the measures: AUC, Brier score, calibration, and sensitivity and specificity at 0.5 and at a threshold chosen on training teeth.
To decide:
the AUC, or sensitivity at a fixed specificity, that passes, on teeth missing at the first visit, the ones the model is used for.
Stand-in:
none; the slide shows the scores only.
De-identification
Bar:
no leak rate set. On synthetic notes a final check holds back any note with a planted identifier left; on real notes only a second scan and a person checking 1 in 1,000 notes remain.
To decide:
the leak rate a data owner accepts, and on which notes (the hardest tier leaks most).
Stand-in:
could rank first on identifiers left in (95% Wilson ranges); dental words removed break ties.
Every score is synthetic,
against the generator's own answer key: it shows the method works on records whose answer we know, not how it does on real records.
docs/process.md (validation criterion) · specs/029-tooth-loss/analysis_plan.md · docs/deidentification.md · rank ranges: docs/results.md · 9

**Speaker notes:** What passes means is different for each question, and only one has a bar today. For finding gum disease, the bar is the acceptance test from OHDSI's case-validation work: a method passes if it agrees with four gum specialists at least as often as they agree with each other, measured with Cohen's kappa, with a margin of 0.05 fixed before anyone looks. It has not been run, because our reviewers are simulated so far, and a simulated result is a dry run we never show as a result. So the cost slide uses a stand-in, the top group: could this method rank first, over resamples of the same charts? For tooth loss, no bar is set: the analysis plan names the measures but not a passing score; we suggest setting it on the teeth missing at the first visit, because that is where the model is used and where it scores lowest. For de-identification, no leak rate is set either: on synthetic notes a final check holds back any note with a planted identifier left, but on real notes, where nothing is known in advance, only a second scan and a person checking one note in a thousand remain, so the leak rate needs a bar. Setting the two missing bars is part of the ask.

## Slide 10 — costing

Appendix · How cost was computed
Dated list prices and illustrative hardware prices, a million notes, one note a visit. People's time is the larger cost.
By hand
33,333 h
a million visits, one specialist, 2 minutes a chart
To prove it
~31 h
233 charts, 4 reviewers: the acceptance test
Kind
How
Inputs and price date
Hosted LLM
tokens × list price
453 in (note + prompt), 20 out; Llama 3.3 70B, Databricks, 2026-10-26: ~$260
Frontier LLM, the note
tokens × list price
same tokens; Gemini 3.1 Pro (ai.google.dev) and Claude Fable 5.1 (claude.com), 2026-10-28: ~$1,100 and ~$5,500
Frontier LLM, whole record
tokens × price × 3 calls
assumed 20k in, 4k out a call: ~$260k and ~$1.2M; batch pricing halves either
Own GPU model
hours × GPU price, + training
assumed speed; illustrative $4 GPU hour (costs.yaml): ~$40 for ModernBERT-large, ~$140 for MedGemma 1.5 4B
CPU method
hours × CPU price
measured speed; illustrative $1 CPU hour: word counts and patterns under $1, taggers ~$5–$103
Paid de-identification
vendor's billing unit
list price, 2026-10-26 (docs/deidentification.md): ~$18–$2,650
Read the costs as an order of size, not a quote.
Note tokens are from synthetic notes, which are shorter than real ones; the whole-record tokens and the GPU speeds are assumed, not measured. Every method, with its sources:
the interactive version
.
docs/claims.yaml (tiers), costs.yaml, data/corpus/cost_benchmark.csv, data/deid/cost_effectiveness.csv, docs/financial_tradeoffs.md · illustrative prices · 10

**Speaker notes:** How the cost figures were made, so a reader can check them. Hosted models are priced per token: each call sends the note plus the prompt, about 453 tokens, and gets about 20 back; at Databricks' list price for Llama 3.3 70B, checked October 26, that is about 260 dollars a million notes. The same tokens at Google's and Anthropic's list prices, checked October 28, give about 1,100 for Gemini 3.1 Pro and 5,500 for Claude Fable 5.1. If a frontier model reads the whole record with worked examples and reasoning, three calls a visit, with an assumed 20 thousand tokens in and 4 thousand out a call, it is about 260 thousand and 1.2 million; batch pricing halves either. Models on our own GPU are priced as hours at an assumed speed times an illustrative 4 dollars an hour, plus training: about 40 dollars for ModernBERT-large and 140 for MedGemma. CPU methods use the speed we measured, at an illustrative dollar an hour. Paid de-identification services are priced in their own billing units at list price. And the larger cost is people: reviewing a million visits by hand is about 33,333 specialist hours at two minutes a chart, while the acceptance test needs about 31, 233 charts read by 4 reviewers. If asked for a dollar figure for people: at an illustrative 100 dollars an hour, about 3,100 dollars to validate against 3.3 million to review everything.

## Slide 11 — results

Appendix · Finding gum disease, by evidence (synthetic)
The whole record answers it. The note alone nearly does.
Whole record, rules
207 of 223
charts given the right status, combining the evidence, gum measurements first.
Note only, simple text model
191 of 223
right from the free-text note alone (word counts, with a rule for the most severe stage); keyword rules got 183.
Note only, trained AI
203 of 223
right with ModernBERT-large and the stage 4 rule; the LLMs Llama 3.3 70B got 187 and MedGemma 4B 178.
Gum measurements alone
166 of 223
right, but 53 charts had no measurements to read: one piece of evidence is not enough.
Combine the evidence:
the whole record beats any one part of it. Synthetic notes are easier than real ones, so expect the gaps to widen.
Synthetic charts, scored against the generator's truth at five status groups (healthy and gingivitis together), adults from 2021-04-01: the 223 review charts · real model runs on CPU · 11

**Speaker notes:** These are real model runs, on synthetic charts, scored against the generator's truth; they are not clinical performance, and agreement with simulated reviewers is a dry run we do not show. Numbers out of 223 review charts: the notes were rebuilt for adults' visits from April 2021, the start date the scores use, with healthy and gingivitis counted as one group. Rules that combine the whole record, reading the gum measurements first, got 207 right. Reading only the free-text note, a simple word-count model with a keyword rule for the most severe stage got 191, and the keyword rules alone 183. Reading the note with AI, a small model trained on our notes, ModernBERT-large with the stage 4 rule, got 203; the general LLM Llama 3.3 70B got 187 and the medical LLM MedGemma 4B 178. And any single piece of evidence falls short: the gum measurements alone got 166 right, because 53 of the 223 charts had no measurements at all. The lesson: combine the evidence. If asked about uncertainty: every number has a 95 percent bootstrap interval on the full results page; on 223 charts, many methods cannot be told apart. If asked why synthetic: no identifiable patient data may be used here; synthetic data lets us build and test everything, including the privacy checks, before any approvals.

## Slide 12 — tooth-loss

Appendix · Tooth loss, the full scores (synthetic)
On held-out extractions, about three in four teeth lost to gum disease are found
At a threshold of 0.5
Completed: logistic
Completed: XGBoost
Completed + planned: logistic
Completed + planned: XGBoost
Sensitivity (lost to gum disease, found)
0.74
0.73
0.75
0.78
Specificity (other reason, ruled out)
0.90
0.93
0.87
0.89
Positive predictive value
0.82
0.86
0.78
0.81
F1
0.78
0.79
0.77
0.79
AUC (95% CI)
0.89 (0.86–0.92)
0.90 (0.87–0.93)
0.88 (0.85–0.92)
0.90 (0.87–0.93)
AUC, teeth missing at the first visit
0.59
0.63
0.64
0.70
Held out:
469 extractions with a recorded reason (178 lost to gum disease), 322 patients.
Teeth missing at the first visit:
10,761 teeth, scored against the synthetic answer key; 0.59 to 0.77 across five generator seeds.
Synthetic Open Dental-style extract, generator seed 42, shared predictors (docs/tooth_loss.md; specs/029-tooth-loss/analysis_plan.md) · 12

**Speaker notes:** The full tooth-loss scores behind the cost slide, all on synthetic records. On extractions whose reason was recorded and held out of training, 469 teeth, the models find about three in four of the teeth lost to gum disease and rule out about nine in ten of the others, with an AUC of about 0.9. Two label sets are shown: completed extractions only, and completed plus planned extractions whose tooth is later recorded missing. The bottom row is the one to watch: on the 10,761 teeth already missing at the first visit, which is where the model is used, the AUC is 0.59 to 0.70, and 0.59 to 0.77 across five generator seeds. No pass bar is set yet. If asked why no LLM: this question reads structured tables, not text, so the first models are small tabular ones; a comparison with more kinds of model is in progress.

## Slide 13 — privacy

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
Synthetic notes with fake names and dates; also tested on public benchmark sets · Health Transformation Lab · the dental record (EDR) · 13

**Speaker notes:** Before any software or person reads a note, names, dates and IDs come out. We compared 15 methods on 400 synthetic notes with fake identifiers planted in them. The best was a combination of tools with a guard that protects dental words; it still missed 115 of 2,714 identifiers, which is why a final check holds back any note with one left, and nothing goes on until it passes. It also removed 41 of 2,462 dental terms that look like names or codes, such as Glickman or Gracey 11/12, which would damage what the AI reads. The two numbers pull against each other, like a spam filter. We also tested on public benchmark sets, including published, already de-identified case reports. All synthetic, or published by others already de-identified.

## Slide 14 — evidence

The order matters
Same evidence, read in a different order: a different answer
Gum measurements first
207 of 223
right: then the note, exam form and codes fill the gaps (the first rule set, v0).
Exam form first
176 of 223
right (79%): the study design's order, exam form, diagnosis codes, note, then measurements.
Orders to test
24
four sources can be ranked 4×3×2×1 ways; each ranking is scored against the specialists.
So the order is a finding, not a setting:
the ranking that agrees best with the specialists is the one to keep. Procedure codes are a rough guess from the treatment, so they are compared, not used.
Synthetic charts, scored against the generator's truth · 2017 AAP/EFP classification · rules and worked examples: docs/evidence_rules.md · 14

**Speaker notes:** A dental chart holds seven kinds of evidence: the clinician's note; the exam form, with a gum score and a status checkbox; the procedure codes done and planned; the diagnosis codes on those procedures, done and planned; and the probing chart of gum measurements, turned into a stage with the 2017 American Academy of Periodontology and European Federation of Periodontology worksheet. Procedure codes are only a rough guess from the treatment, so they are compared, not used. When the other sources disagree, the rules take the first one, in a fixed order, that gives a status. The order matters a lot. Reading the gum measurements first, the first rule set, gets 207 of 223 synthetic charts right; it is the 207 on the results slide. The study design's order, exam form first, then diagnosis codes, the note, and the measurements last, gets about 176, 79 percent. On synthetic charts the measurements are the generator's own evidence, which flatters reading them first; on real charts the answer may differ. Four sources can be ranked 24 ways; each ranking is scored against the specialists, and the one that agrees best is kept. A radiograph reading can only raise the stage.

## Slide 15 — acceptance

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
Synthetic charts; LLM judgments checked against the generator's truth, on the notes before they were rebuilt for adults (rerun pending) · the bar: OHDSI 2023 plenary on case validation; npj Digit Med 2025 · 15

**Speaker notes:** How do we know an answer is right? On real records there is no answer key, so the acceptance test is the bar: an AI method passes only if it agrees with the specialists at least as often as they agree with each other, the standard from the OHDSI 2023 plenary on case validation, with the LLM review work published in npj Digital Medicine in 2025. We also tested whether a general-purpose AI, a large language model, could stand in for the answer key. Reading each note itself, it matched the answer key on 83 percent of charts but only 53 percent of hard notes, the ones that leave out what the answer key is built from. Asked whether a method's answer was right, it caught most mistakes of weak methods, but only 26 percent of the best note model's, which are near-misses such as one stage off. So it cannot replace specialists yet. These are AI judgments on synthetic notes, checked against the generator's truth, made on the review notes before they were rebuilt for adults; the judge is being rerun on the new notes. If asked about statistics: kappa for agreement beyond chance, 95 percent bootstrap intervals over charts, and unsafe errors counted separately.

## Slide 16 — audience

Who it’s for, what we ask, what changes
Built for the people who count gum disease in dental records
Who
What we ask them to do
What changes
Dental data and quality teams
at clinic groups and record vendors
Run PerioBench on a de-identified extract, in their own environment
Records to recheck are found; gum disease is counted the same way across clinics
Researchers
in oral and overall health
Use the open method to study gum disease alongside diabetes
The medical-dental link could be studied at scale, in OMOP
Gum specialists
(periodontists)
Label the validation charts, about a day each
Agreement measured on real records, not only synthetic ones
AI builders
Score their record readers on the same charts
Public, comparable scores
The impact:
gum disease that can be counted, followed over time and linked to diabetes care. So far it runs only on synthetic records; nothing has been run on real ones.
A personal project: no partner has been contacted · 16

**Speaker notes:** Before the problem, the three answers people ask for first: who this is for, what we want them to do, and what changes. PerioBench is for the people who have to count gum disease from dental records. First, the data and quality teams at clinic groups and record vendors: we ask them to run PerioBench on a de-identified extract, inside their own environment and approvals, so they find the records to recheck and count gum disease the same way across clinics. A record to recheck is often a coding or charting gap, not a clinical error. Second, researchers in oral and overall health: the method is open, so gum disease can be studied alongside diabetes, in OMOP, the format medicine already uses. Third, gum specialists: about a day each to label the validation charts, so agreement is measured on real records, not only synthetic ones. Fourth, the people who build AI record readers: they can score them on the same charts, in public. The impact is gum disease that can be counted, followed over time and linked to diabetes care. Today it runs end to end only on synthetic records; nothing has been run on real ones, and no partner has been contacted.

## Slide 17 — solution

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
Periodontists label the same 223 charts, each on their own (simulated reviewers so far)
6
The acceptance test
AI passes only if it agrees with them as often as they agree with each other
Built to run on a real extract unchanged:
the same code, tests and dashboards, once a de-identified dataset and its approvals exist.
Synthetic patient records · Health Transformation Lab · the dental record (EDR) · 17

**Speaker notes:** This is the whole pipeline, and it runs end to end today on synthetic data. One: we generate synthetic patients across 8 clinics, visit after visit, with every kind of evidence and fake names in the notes, so the privacy step is tested too. Two: names, dates and IDs are removed, and a final check holds back any note that still has one. Three: the record goes into OMOP, the common data format medicine already uses, which is what lets a dental finding sit next to a diabetes record. Four: rules combine the whole record, and AI models read only the free-text note, for the many charts where the structured fields are missing. Five: gum specialists label the same 223 charts, independently; until real specialists do, simulated reviewers stand in so the reliability code can be tested, and their numbers are never shown as results. Six: the acceptance test. An AI method passes only if it agrees with the specialists at least as often as they agree with each other; that is the standard the OHDSI community uses to check how well records identify a disease. Because it is synthetic, we know the right answer for every chart, so we can test the test. If asked about the platform: Databricks and Unity Catalog, MLflow for models, Postgres and Lakebase for OMOP; Python and R give the same numbers.

## Slide 18 — connect

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
OralHealthBench pitch: docs/pitch/ · Health Transformation Lab · the dental record (EDR) · 18

**Speaker notes:** The landing page has two paths, and this is how they meet. This path builds synthetic patients whose right answers are known, in the same format medicine uses. That makes them a source of test questions: case questions written from those patients, with the right answer already scored. The other path, OralHealthBench, is about testing AI where medicine meets dentistry and on access to care, in public. Both test AI the same way: the same models, harm grades and leaderboards, scoring AI first on gum charts, then on case questions from synthetic patients, then on broader medical-dental questions. The OralHealthBench pitch is in docs/pitch.
