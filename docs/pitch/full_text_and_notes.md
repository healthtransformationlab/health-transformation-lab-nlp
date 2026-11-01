# Health Transformation Lab: Shark Tank pitch: full text and notes
A personal idea, not affiliated with or endorsed by any organization. Built from `slides/` by `docs/build_decks.py`; edit the slides, then rebuild.

## Slide 1 — cover

Shark Tank pitch · October 2026
AI passes the dental exam.
It fails the real patient.
Most benchmarks test exam knowledge. Studies of real patient cases, including drug interactions, have found AI falling short. Oral health for all means fixing the test.
Health Transformation Lab
A personal idea
Two open benchmarks:
PerioBench
, finding gum disease in dental records, built and tested on synthetic records; and
OralHealthBench
, AI answers on oral health and getting care, planned on top of GlobalDentBench.
John Bowyer · personal project, not affiliated with any organization

**Speaker notes:** AI passes the dental exam, and it fails the real patient. Most AI benchmarks test exam knowledge, and published studies of real patient cases have found AI falling short. On real hospital cases, AI models didn't follow the clinical guidelines doctors use (Hager and colleagues, Nature Medicine, 2024). Members of the public using AI did no better than those using a source of their choice (Bean and colleagues, Nature Medicine, 2026). And on drug interactions, chatbots were often wrong where a standard interaction checker was right (Al-Ashwal and colleagues, 2023). I am proposing an independent, open lab, called the Health Transformation Lab. Its mission: better oral health for millions of Americans, and better overall health through the links between medical and dental care. It does that by making AI accurate on two things today's tests leave out. One is where medicine meets dentistry: medicines, chronic disease such as diabetes, and emergencies. The other is the social factors that decide whether people get care: cost, coverage, distance and transportation, what researchers call the social determinants of health. This is a personal idea: nothing has been registered or built, no organization is behind it, and no partner has agreed to anything.

## Slide 2 — problem

How AI is graded today
Exam: pass. Patient: fail. Social factors: untested.
The exam
81%
AI’s score on dental licensing-exam questions.
Real patients
22%
Its score on questions built from published patient cases.
Safety
1 in 3
answers was rated unsafe. Where medicines are involved, 1 in 7 risked harm that cannot be undone.
The missing test: social factors
None
No scorecard we found checks if AI is accurate on the social factors that decide care: cost, coverage, distance, transportation.
AI is graded on public scorecards
(called benchmarks), and AI companies compete on the scores. The first one for dentistry came out this year, so the questions are being written now.
Averages for 12 AI models, from OpenAI, Google, Anthropic, xAI and others · GlobalDentBench 2026; first search Oct 2026 · 2

**Speaker notes:** First, how AI gets graded. Independent researchers publish tests and score every major AI on them, like a public report card. The technical word is benchmark. AI companies compete to raise those scores, so what is on the scorecard is what gets better. Now four facts from the first dental scorecard. One: AI scores 81 percent on multiple-choice questions from dental licensing exams. Two: on questions built from published patient case reports, the score falls to 22 percent. Three: nearly one in three of those answers was rated unsafe, and about one in twenty risked harm that cannot be undone. Four, and this is the one we can change: we found nothing that tests the social side. No scorecard we found checks whether AI answers accurately on the social factors that decide whether people get care: cost, coverage, distance and transportation. US emergency rooms see about 1.9 million visits a year for tooth problems, and Medicaid is the most common payer for them (CDC, NCHS Data Brief 531, 2025); for people without a dentist, the untested questions are the ones that matter most. Why now: the first global dental scorecard for AI was published this year, so the questions are being written right now, and the people who show up shape them. If asked for detail: the first three are from GlobalDentBench, published in 2026: 12 leading AI models, from OpenAI, Google, Anthropic, xAI and others, 8,978 questions from 88 countries; the scores are averages across all 12, not one company's product, and Google's model scored highest overall; 31 percent of case answers were unsafe and 4.5 percent carried a risk of irreversible harm. The fourth is from a first search of benchmarks, not a full review: existing tests check whether AI can spot social factors in medical records, or whether answers are biased, but none we found checks accuracy on access to care. If asked whether anyone has studied AI in dentistry: yes. A systematic review of 38 studies (Kaplan and Akyol, Japanese Dental Science Review, 2026; literature searched January 2025) found no universally accepted framework for evaluating AI in dentistry, test methods and sizes that vary widely, mostly simulated scenarios rather than real-world use, and limited evidence on how patients interpret and act on AI answers. Its categories are patient questions about treatment, diagnosis, model comparisons and decision support; none is access to care. The authors also say continuous monitoring is essential because new models keep appearing. Sources: https://doi.org/10.1016/j.jdsr.2026.01.002 (open access: https://pmc.ncbi.nlm.nih.gov/articles/PMC12865642/); https://www.cdc.gov/nchs/products/databriefs/db531.htm

## Slide 3 — harm

What unsafe looks like
Where AI is most dangerous: medicines and emergencies
1 in 7
answers involving medicines and medical conditions risked harm that cannot be undone.
1 in 11
answers on anesthesia and medical emergencies did the same.
Someone asks
“I take a bone-strengthening medicine. Is it fine to get a tooth pulled?”
The unsafe answer
“Yes, it is a routine procedure.” It never asks about the medicine.
The harm
In some patients on these medicines, the jawbone does not heal after an extraction. That is permanent.
The pattern across medicine:
about 3 in 4 harmful AI errors are things it left out, not things it got wrong.
The example illustrates a harm GlobalDentBench (2026) names. The 3 in 4 is from NOHARM (Stanford-led ARISE network, 2026) · 3

**Speaker notes:** Here is what unsafe means. The study found AI is most dangerous in two areas. Where medicines and medical conditions are involved, about one in seven answers risked harm that cannot be undone. On anesthesia and medical emergencies, about one in eleven. The simplest example: someone on a bone-strengthening medicine for osteoporosis asks if it is fine to have a tooth pulled. The unsafe answer says yes, it is routine, and never asks about the medicine. In some patients on these medicines the jawbone does not heal after an extraction, and that is permanent. If asked for detail: the figures are 14.15 percent for the category the study calls Systemic Health, Pharmacology and Safety, and 8.93 percent for Anesthesia and Medical Emergencies, averaged across 12 AI models. The study lists this jaw condition, medication-related osteonecrosis of the jaw, among its examples of irreversible harm, along with avoidable tooth loss, permanent nerve injury and delayed treatment of cancer or severe infection. The question and answer on this slide are my illustration of that harm: the study publishes the rates, not the individual wrong answers. The risk to any one patient is low at osteoporosis doses and higher at cancer-treatment doses, which is why the dentist needs to know about the medicine. The line at the bottom is from a different study, called First, Do NOHARM, run by the Stanford-led ARISE network on 1,100 real medical cases: 76.6 percent of the harmful errors were omissions, things the AI left out. That is the same pattern as this example, and it is also how AI fails on social factors: an answer that never asks about cost, coverage or transportation leaves out what decides whether the person gets care. NOHARM is a preprint, not yet peer reviewed, and it has no oral health cases. If asked for an emergency example: a person with a swollen face and a fever from a toothache is told to rinse with salt water and wait; a spreading infection can become life-threatening.

## Slide 4 — mdi

Where oral health meets overall health
The mouth is part of the body. Real patient questions cross that line.
Emergency rooms
1.9M
visits a year to US emergency rooms for tooth problems. Medicaid is the most common payer.
Chronic disease
Both ways
Diabetes and gum disease (periodontitis) are linked: each is associated with worse control of the other.
Medicines
Ask first
A bone-strengthening medicine can change whether a tooth extraction is safe. The answer has to ask.
The biggest lift is at the seam.
The ER doctor sees the tooth; the dentist sees the medicine list. Both now ask AI, and studies have found AI falling short on questions like drug interactions.
CDC NCHS Data Brief 531 (2025; visits 2020–2022) · EFP and IDF consensus report on periodontitis and diabetes (Sanz et al., 2018) · GlobalDentBench 2026 · 4

**Speaker notes:** This is where the biggest health gain is: the seam between medical and dental care. Three facts. One: US emergency rooms see about 1.9 million visits a year for tooth problems, on average over 2020 to 2022, and Medicaid is the most common payer; an emergency room can relieve pain and infection but rarely treats the tooth, so many people come back. Two: diabetes and gum disease are linked in both directions. A joint consensus report from the European Federation of Periodontology and the International Diabetes Federation asks doctors and dentists to screen for and manage the two together. Three: medicines change dental care; a bone-strengthening medicine can make an extraction unsafe, which is the harm on the previous slide. In each case the doctor holds half the picture and the dentist holds the other half, and both now ask AI. Studies of real patient cases have found AI falling short on questions like these, drug interactions among them, so that is where the questions go first, alongside the social factors that decide whether the person gets care at all. If asked for sources: CDC, NCHS Data Brief 531, Emergency Department Visits for Tooth Disorders: United States, 2020-2022 (June 2025), https://www.cdc.gov/nchs/products/databriefs/db531.htm; Sanz et al., Scientific evidence on the links between periodontal diseases and diabetes, EFP and IDF consensus report, Journal of Clinical Periodontology 2018, https://doi.org/10.1111/jcpe.12808. The visit count is a national survey estimate, and the diabetes link is an association described by the consensus, not a promise that treating one cures the other.

## Slide 5 — reach

Where the impact is
From thousands, indirectly, to millions, directly
How oral health research reaches people today
What OralHealthBench adds
Who it reaches
Thousands of experts
Millions: 40 million a day ask OpenAI’s AI about health
How
Indirectly: experts find the papers
Directly: the questions are on the scorecard
Where
Journals, reports and data portals
Public AI tools and public scorecards
Who checks
Each study measures itself
Third parties verify it
The main move.
Put the medical-dental link and the social factors of care on AI’s public scorecards, each question traced to published evidence. An open AI agent then shows the lift.
Research keeps its place. This adds a public channel · Source: OpenAI, Jan 2026 (global) · 5

**Speaker notes:** Today, oral health research reaches thousands of experts, indirectly: they find the papers, reports and data portals, and each study measures its own impact. That work stays. What OralHealthBench adds reaches millions, directly, in public, with third parties verifying it. The main move is this: put the medical-dental link and the social factors of care on the public scorecards that grade AI. Every question traces back to published evidence, so anyone can drill down from the test to the science behind it. Once the questions are on the scorecard, every AI model tested on that scorecard is graded on them, and AI companies work to improve what they are graded on. An open AI agent is the second step: it shows how much better the answers get with the evidence. If asked about the numbers: thousands is my description of the research audience, not a measured figure. Millions is the audience of the public AI tools: OpenAI reported in January 2026 that more than 40 million people a day ask its AI assistant health questions, worldwide, including 1.6 to 1.9 million health insurance questions a week; Google reported 950 million monthly users of its AI assistant in July 2026. That is the reach available, not a promise. We found no published count of how many of those questions are dental; measuring that could be an early result of the 180 days. If asked whether the people who run the scorecards will accept the questions: it is their decision, so we ask as partners.

## Slide 6 — ask

The ask
180 days to make the test fairer
What we do
Write the missing scorecard questions on the medical-dental link and the social factors of care, each linked to published evidence
Test the major AI models, with and without an open agent, and publish the results
With partners, take the results to the AI companies and the scorecard owners, and ask for change
If it works
AI graded on the medical-dental link and the social factors of care, not only clinical knowledge
Public evidence as the source behind every question
The major AI models held publicly accountable for accuracy, for the size of a small marketing budget
The ask:
a small team, 5 to 10 hours a week each, for 180 days; $50,000; and partners: the owners of the public dental benchmarks, the Stanford-led ARISE network, which ranks AI on patient harm; and, for the data platform, Databricks for Good as a candidate.
Databricks for Good: databricks.com, Data + AI Summit session · Health Transformation Lab · 6

**Speaker notes:** The ask has three parts. One: a small team, each giving 5 to 10 hours a week for 180 days. Two: 50 thousand dollars. That is the size of a small marketing budget, and it buys something marketing cannot: a public, accurate way to hold the major AI models accountable on oral health. Three: partners. The people who run the public dental benchmarks, because the questions belong on their scorecards. And the ARISE network, led from Stanford, which ranks AI on patient harm and has no oral health cases; we would offer them ours. For the data platform, the candidate is Databricks for Good, which, in Databricks' own words, helps mission-driven organizations through nonprofit pricing, technical enablement and hands-on support from Databricks experts. It has not been contacted, and whether a personal project qualifies has not been checked. If asked why ARISE would work with us: their cases come from primary care and emergency rooms, which is where a patient with a toothache and no dentist ends up, and they have found that most harmful errors are things AI leaves out. We bring oral health cases, the medical-dental questions and the social-factors questions they lack. Nobody has been contacted yet, no partner has agreed to anything, and it is their decision. If asked what the 50 thousand dollars pays for: AI usage for the testing, clinician time to write and check the questions, and publishing the results; a line-by-line budget is not set yet. The team needs at least one clinician or scientist, to write and judge the questions, and one engineer, to build the agent and the software that runs the tests. In that time we do three things. We write the missing scorecard questions on the medical-dental link and the social factors of care, each linked to the published evidence behind it. We test the major AI models on them, with and without an open agent, and publish the results. And with partners, we take those results to the AI companies and the people who run the scorecards, and ask for change. Publishing is what creates the pressure: a public result is harder for the AI companies to ignore. We found no measurement of this, so the gain could be large or small. 180 days tells us. If asked what the questions cover: what a doctor, a dentist or a person with no dentist asks where medical meets dental, and about getting care, such as when to go, where to go and how to pay, judged on whether the answer works given their circumstances. If asked what the agent is built on: published research, public clinical guidelines and public data, plus synthetic patient records whose right answers are known. If asked about safety: the agent is built to point people toward care, not to replace a dentist or doctor, and an answer that would delay urgent care is scored as unsafe. If asked about sample size: about 25 questions per round is a pilot, enough to see direction. If asked why 180 days: at 5 to 10 hours a week each, the work needs the time, and nobody is pulled off their main job. If asked how this holds anyone accountable: the scores are public and checked by third parties, so when a major AI model answers poorly, anyone can see it, and the companies have a reason to fix it. That depends on the scorecard owners accepting the questions; if they do not, we can still publish our own results. If asked what happens if there is no uplift: we learned it at small cost, and the questions are still a contribution. If asked about the moonshot: AI that works for everyone on oral health and connects it to the rest of their health, reached one public, measured step at a time.

## Slide 7 — drill

Health Transformation Lab
Drill-down
Backup slides for questions.
From the test to the evidence, the two moves, how the agent works, and the uplift
The benchmarks, testing our own models, and the double-click
Why a network, the precedents, and building on the standards
The phased plan and the success metrics

**Speaker notes:** Do not present these. Jump to one only when a shark asks.

## Slide 8 — drilldown

From the test to the evidence
Each question drills down to published science
1 · On the benchmark
The question
“I have no dental insurance and a bad toothache. How can I pay for care, and where can I go?”
2 · From clinicians and scientists
The right answer
What a correct, safe answer must include, and what would make it wrong or unsafe.
3 · One click further
The evidence
The published studies and guidelines the question and its answer come from, so anyone can check it.
Experts decide the questions. Public evidence backs the answers.
Every AI model that takes the test is measured against the same science.
Illustrative question. Clinicians and scientists choose the real questions and the evidence behind each · Drill-down

**Speaker notes:** This is what one benchmark question looks like. On the test is the question, the kind a person without a dentist actually asks. Behind it is the right answer, written by clinicians and scientists: what a correct, safe answer has to include, and what would make it wrong. And one click further are the published studies and guidelines the question and answer come from. So when a leading AI model takes the test, it is measured against the same science, and anyone who doubts the answer can drill down to the source. A medical-dental question works the same way: a person with diabetes asks why their gums bleed, and the right answer covers both the dentist and the doctor. The questions on these slides are illustrations; the real questions and the evidence behind each are chosen by the people who write the test.

## Slide 9 — solution

The two moves
Make the test fair, and show the gain
1 · The main move
Put the right questions on the test
Write the questions the tests leave out: where medical meets dental (medicines, chronic disease, emergencies), and the social factors of care (cost, coverage, distance, transportation). Each one traces back to published evidence.
2 · Then show the lift
Show what the evidence adds
Publish one open AI agent built on public research and guidelines, to show and encourage measurable lift in the leading AI models on those questions.
What gets tested is what AI developers improve.
A high score helps one model. A fairer test helps everyone.
Health Transformation Lab · Drill-down

**Speaker notes:** Two things. First, we put the missing questions on the benchmarks: where medical meets dental, and the social factors of care. We write them, and we take them to the people who run the tests. Second, we show what the evidence adds: one open AI agent built on public research and guidelines, connected to leading AI models, with the gain measured in public. Why the first one matters most: what gets tested is what AI developers improve. A high score helps one model. A fairer test helps everyone. If asked how the agent works: someone asks a question in the AI tool they already use, the AI checks the published evidence through the agent's connection, and answers from it with the source shown; see the next slide. If asked whether the benchmark owners will agree: it is their decision, so we ask as partners; the dental test's authors note it covers clinical dentistry only and that their expert panel came from one institution, so there is an opening.

## Slide 10 — workflow

How the agent works
One question, and where the open agent fits
1
Someone asks
A person with no dentist, a doctor or a policymaker asks an oral health question.
2
Their AI
The AI tool they already use, such as ChatGPT, Claude or Copilot.
3
The open agent
The AI checks published research, public guidelines and public data.
4
A better answer
The story, the number and the source, built on public evidence.
Two ways we help.
Make the answers better with public evidence. And shape the benchmarks, so they not only measure accuracy but also include the social determinants of health that are missing today.
We measure in public: accuracy, safety, and the agent’s share of the gain. The goal is to shape the benchmarks, not only to score well · Drill-down

**Speaker notes:** Here is how it works, in one question. Someone asks an oral health question: a doctor, a patient, a policymaker. They ask it in the AI tool they already use. Today that AI answers from whatever it already knows. With the open agent connected, the AI first checks published research, public guidelines and public data, and answers from that, showing the source. Over time the answer carries three things: the human story, the number behind it, and the source. We do not replace their AI. We sit behind it. The uplift is how much better the answer gets with the agent than without it. And because the connection is published, any organization can plug it into the AI it already uses. The bigger goal is not just a high score. It is to shape the tests themselves, because what gets tested is what AI developers work to improve. So there is a second way to help: work with the people who run the dental test to add the questions that are missing, on the medical-dental link and on access to care and its barriers. Where we expect the most gain, to be straight about it: public evidence is strongest on access, cost, coverage and the link between oral and overall health, and the dental test does not cover those areas yet. Exact terms if a technical person asks: the AI is the model; the published connection is an MCP server; the model using that connection is the agent.

## Slide 11 — uplift

What we would bring back
The uplift, starting with access to care
Category
AI on its own
With the agent
Uplift
Cost per answer
Getting care: when, where, how to pay (first)
To measure
To measure
To measure
To measure
Clinical cases
To measure
To measure
To measure
To measure
Medical-dental integration
To measure
To measure
To measure
To measure
Barriers to care
To measure
To measure
To measure
To measure
Cost and coverage
To measure
To measure
To measure
To measure
Start where the mission is, then compare.
First the questions people ask about getting care. Then the same test in other areas, to see where the evidence adds the most for the least cost.
Nothing here is measured yet. A fair test: same questions, and judges who do not know which answer is which · Drill-down

**Speaker notes:** This is the shape of what we bring back after 180 days: access to care first, then one row per category. For each, the AI's score on its own, its score with the agent, the difference, which is the uplift, and what each answer costs. There is a good chance the evidence adds little on clinical cases, and more on medical-dental integration, access and barriers to care. That is fine. The goal is to find where the evidence makes the most difference for the least cost, and put the effort there. Two more points. The overall score can rise because the AI models improve on their own or because the evidence adds more; we track both. And the dental test found that paying more for an AI model did not reliably buy a better answer, so cost belongs in the table. Limits: about 25 questions per round shows direction only, and the uplift can be small, zero or negative. Nothing on this slide has been measured yet.

## Slide 12 — tests

Where no test exists, we can help write it
Public AI tests across oral health
Area
Closest public test today
The gap
Medical-dental integration
One category in the global dental test: systemic health, medicines and safety
No test of its own
Social needs (SDOH)
Tests of AI finding social factors in medical records, and Google’s health equity question sets
None checks if an answer works for someone with no coverage or transport
Education
Dental and medical licensing-exam questions, including the exam part of the dental test
Tests what AI knows, not whether professionals learn
Grants
One 2026 study of AI reviewing six research grant proposals
No standing test, and none for philanthropy
Policy and advocacy
A UK public health guidance test with 8,000 questions, and a government policy test
Nothing on oral health policy
arXiv 2605.24636, 2603.08281, 2505.06046, 2511.04705, 2406.06056, 2403.12025. A first search, not a full review · Drill-down

**Speaker notes:** Someone may ask whether public AI tests exist beyond clinical dentistry. From a first search: partly, and nothing specific to oral health. For medical-dental integration, the closest is one category of the global dental test, covering systemic health, medicines and safety. For the social side of health, often called social determinants or SDOH, the existing tests mostly check whether AI can spot social factors, such as housing or transport, inside medical records. Google has also published health equity question sets that check for biased answers. I found none that tests whether an AI answer actually works for a person given their circumstances, such as no coverage, no car, or no dentist nearby, and none for oral health. That is the test most worth writing, and it is the same ground as the access-to-care questions. For education, there are many tests built from licensing exams, but they measure what the AI knows, not whether a professional learned anything. For grants, I found one 2026 study that had AI review six UK research grant proposals; it is a method, not a standing test, and nothing covers philanthropic grantmaking. For policy and advocacy, there is a UK public health guidance test called PubHealthBench, with over eight thousand questions, and a government policy test called POLIS-Bench; nothing covers oral health policy. So the gap is the opening: where no test exists, OralHealthBench can help write one with partners. This was a first search, not a full review, so say that if pressed.

## Slide 13 — leaderboard

Frontiers are where the future is settled
Get in the game
The leading models, extended
Rank
Health AI model
With the open agent
1
Claude Sonnet 5.5
+ uplift, to be measured
2
Claude Mythos 5
+ uplift, to be measured
3
Claude Mythos Preview
+ uplift, to be measured
We do not compete with these models. They are the teams. Oral health evidence is a talented rookie no scout has seen.
Next: in the game
1
Publish one open AI agent built on public evidence
2
Connect it to the leading AI models
3
Measure the overall score and the uplift, and publish both
Context matters. Relationships matter.
Today oral health plays the AI game in private, and unmeasured.
Time to rethink publishing: papers, plus an AI agent that is tested in public.
Source: HealthBench leaderboard, benchmarklist.com, updated Sep 29, 2026 · Health Transformation Lab · Drill-down

**Speaker notes:** How do you pick a hospital or a college? Most of us check the rankings. AI gets picked the same way. These are the top-ranked AI models for health. We are not competing with them. They are the teams, and oral health evidence is a talented rookie no scout has seen. So we publish one open AI agent built on public evidence, connect it to these models, and measure how much better each one gets at oral health. That gain is the uplift, and we publish it. Context matters, and so do relationships: between the mouth and the rest of the body, and between the people who treat each. To say correctly if a technical person asks: the ranking shown is for general health questions, and it lists AI models only. The uplift is measured on oral health questions, with each model on its own and then with the agent. The first test may use three leading models from different developers, not necessarily these three. An agent is a model connected to tools and data. The published connection is called an MCP server, MCP being the open standard that lets these models use it. We do not build or own the models. Figures: 31 entries from three AI developers; the top score is 65 percent, length-adjusted, as of the September 29, 2026 update.

## Slide 14 — answer

What a better answer looks like
The story, the number and the source
The human side
The story
A real person’s experience, shared with consent, or a public education video. It is what people remember.
The finance side
The number
Cost, visits and savings, each with one agreed definition, so reports, dashboards and the AI give the same figure.
The evidence
The source
The research or data behind it, one click away, so anyone can check it.
A story without a number is an anecdote. A number without a story is forgotten. We give both, with the source.
The technical name for “one agreed definition” is a metric definition, such as a Databricks metric view · Drill-down

**Speaker notes:** A better answer has three parts. The human side is the story: a real person's experience, shared with consent, or a public education video. The finance side is the number: cost, visits, savings. Each number has one agreed definition, so reports, dashboards and the AI all give the same figure. The evidence is the source, one click away. A story without a number is an anecdote, and a number without a story is forgotten. Exact terms if asked: the one agreed definition of each number is a metric definition; Databricks calls it a metric view. It defines a measure once, centrally, so dashboards and AI reuse the same calculation. Order of work: the first 180 days focus on medical-dental and access-to-care questions, starting from published material. Stories and numbers come after, because stories need consent and numbers need clear definitions and safeguards.

## Slide 15 — example

The problem
A doctor asks AI about a tooth
2 a.m., emergency room
A patient arrives with a swollen jaw. The doctor asks an AI tool what to do.
22%
Average score of 12 leading AI models on dental case questions.
This is where medical and dental now meet.
Linked dental, medical and emergency records, in one shared format, could make that answer better.
Source: GlobalDentBench, arXiv 2605.24636 · Health Transformation Lab · Drill-down

**Speaker notes:** Picture an emergency room at 2 a.m. A patient comes in with a swollen jaw. The doctor asks an AI tool what to do. That AI was tested on medicine, not on teeth. On a dental test, twelve leading AI models averaged 22 percent on case questions. This is where medical and dental meet now. Dental, medical and emergency records, linked in one shared format such as OMOP, could make that answer better, and the same linked records are what a fair test of it is built from. If asked: the scenario is an illustration; the 22 percent is from GlobalDentBench, a public dental test with questions from 88 countries.

## Slide 16 — medgemma

The open option: Google’s MedGemma
A model we could own and publish
What it is
Google’s open AI models for medical text and medical images. Free to download and adapt.
Why it fits
It reads medical images, and Google’s list does not include dental. A dental version would be new, and open to share.
What it takes
De-identified data, a privacy and legal review, and modest computing.
Today most health AI is rented. This would be an open model anyone can check.
Google says MedGemma is not yet clinical-grade, so this supports research and tools, not clinical decisions.
Source: Google Health AI Developer Foundations, MedGemma (page updated Jan 13, 2026) · Drill-down

**Speaker notes:** Use this if someone asks whether there could be an open oral health model. A project this size doesn't build a frontier model. But Google publishes MedGemma, a family of open medical AI models that anyone can download and adapt. It handles medical text and images such as CT, MRI and pathology slides. Dental imaging is not on Google's list, so a version tuned on dental data would be a real contribution. It would come after the 180-day first step, and only with de-identified or synthetic data and a privacy and legal review, because a tuned model can memorize what it was trained on. Google states MedGemma is not yet clinical-grade and needs validation for each use. Check Google's current terms of use before publishing a tuned version.

## Slide 17 — trajectory

Why now
Same science, a new trajectory
People reached and helped
Time
Built on public science
We are here
A small first step: 180 days, part-time
Public, measured wins build confidence
From frontier to mainstream: the major players take notice
Today's path: research that reaches experts. Trusted, steady, and it continues.
A sketch of the idea, not a forecast · Health Transformation Lab · Drill-down

**Speaker notes:** Here is the idea in one sketch. The dark line is the path oral health research is on today: trusted science, reaching the experts who look for it. It keeps going. The orange line starts from the same science and begins with one small step. Then it climbs. Each public, measured win builds confidence, and that gets the attention of the major players. That is how this moves from the frontier to the mainstream. If asked for numbers: the best AI scores on general medical questions are in the 60s out of 100, and on a dental test twelve leading AI models averaged 22 percent on case questions. This is a sketch of the idea, not a forecast.

## Slide 18 — journey

The thinking shift
Same question, two paths to an answer
Today: they go to the research
1
Find a portal or a report
2
Choose a data source
3
Request access
4
Learn the tool, run the analysis
A trusted answer, for those who finish the path
The open agent: the research goes to them
1
Ask in the AI tool they already use
2
It draws on published science
3
The answer comes with the story and the numbers
A trusted answer, in the moment they ask
Today's path stays. Agreements remain for sensitive data · Health Transformation Lab · Drill-down

**Speaker notes:** One question, two paths. Today, someone finds a data portal or a report, requests access, learns the tool and runs the analysis. That works for researchers, and it stays. On the right is what the open agent adds: they ask in the tool they already use, and the answer is built on published science. If asked: data use agreements stay in place for sensitive data.

## Slide 19 — doubleclick

The double-click
From a human story to the KPI to the data
1 · The story
In her own AI tool, a county health director watches a veteran's short video about a toothache that sent him to the ER.
2 · The KPI
One click shows the measure behind it: adult dental ER visits in her county.
3 · The data
Another click opens the public data behind the KPI, such as state emergency-room statistics.
4 · The graph
A social graph links stories, education videos, KPIs, definitions and datasets, so each one leads to the others.
She never had to learn a data portal.
Illustrative example · Drill-down

**Speaker notes:** Raw data does not move people. A story does, and a number backs it up. The agent gives her the story first, then lets her double-click to the KPI and to the public data behind it. The social graph is what makes that possible: stories, measures, definitions and datasets are all connected, like friends in a network. It happens in her tool, through an open API. The example is an illustration.

## Slide 20 — open-access

Public access through Hugging Face and MCP
Three paths in, each with safeguards
Path 1
Open
Anyone. Benchmarks, definitions, model cards and aggregate, de-identified measures under an open license.
Path 2
Registered
Sign in and accept terms of use. The models and agents behind PerioBench and OralHealthBench, called through MCP or an API, with usage limits and logging.
Path 3
Agreement
A signed data use agreement, reviewed and approved, for detailed or licensed data in a secure environment.
Safeguards on all three paths:
no personal health information leaves the platform; licensed and payer data stay under the agreements they came with; each model and agent is benchmarked and reviewed by privacy and legal before release.
Proposed design, for privacy and legal review · Drill-down

**Speaker notes:** Hugging Face is the hub where AI builders find models and data. MCP is the open standard that lets any AI assistant call outside tools. Opening up does not mean giving everything away. Three paths: open for benchmarks and aggregate material, registered for the agents, and a data use agreement for anything detailed. This is a proposed design; privacy and legal review decide the final rules, and each dataset's license limits what can be shared.

## Slide 21 — standard

Building on the standards
Embrace the standards, then extend them
Embrace
Map oral health data to the standard medicine already uses, so medical researchers can work with it on day one.
Extend
Help lead OMOP's dental extension, and work with standards bodies to get oral health into the standard healthcare benchmarks.
Connect
Knowing how health data connects in OMOP also builds the graph and search layers that give AI its knowledge.
These are shared standards. Oral health can hold a pivotal seat at the table.
Health Transformation Lab · Drill-down

**Speaker notes:** OMOP is the common data format for health research. Dentistry is the open seat: its dentistry workgroup began in 2022 and reports few dental datasets converted so far. The same goes for AI benchmarks: work with the bodies that own them to add oral health. If dental data speaks that format, medicine comes to oral health without translation, and that is how oral health becomes part of overall health in practice. The knowledge carries over: OMOP is a map of how health terms relate, such as which code is a kind of which condition. The same map is what a knowledge graph and an AI search index are built from, so the skill that maps dental data to OMOP is the skill that makes frontier models more knowledgeable about oral health. Keep this slide to 30 seconds.

## Slide 22 — proof

It has been done
Niche tools that became infrastructure
REDCap
Started:
2004, a data tool for Vanderbilt's own researchers.
Became:
free to nonprofits; over 8,500 institutions in 167 countries.
OHDSI
Started:
a narrow drug-safety research project.
Became:
a global open-science community: the OMOP data standard, shared vocabularies, open-source tools and network studies.
Healthtalk.org
Started:
2001, two Oxford doctors collecting patients' own stories.
Became:
research-grade story library; its method adopted in 14 countries.
The pattern: own the shared standard, give the tool away, let others bring the content.
Sources: Vanderbilt CTTC; OHDSI; healthtalk.org · Drill-down

**Speaker notes:** Pick one and tell it in two sentences. REDCap is the closest match: built for internal researchers, given away, and now the center of its field. Each of these started small, with an expert group, as this lab would.

## Slide 23 — pilot

The plan in phases
A phased start, sized for part-time work
Phase 1
First 180 days.
Build one open AI agent on published research, public guidelines and synthetic records with known answers. Test it on medical-dental and access-to-care questions, with and without it, and measure the uplift.
Phase 2
If phase 1 earns it.
Tune an open medical AI model, Google’s MedGemma, on de-identified oral health data. That gives oral health an open model anyone can check.
Phase 3
Later.
Publish it after privacy and legal review, open it to partners with safeguards, and report whether it helped people.
The ask covers phase 1 only:
a small team at 5 to 10 hours a week each for 180 days, $50,000, and a data-platform partner to approach: Databricks for Good, a candidate, not yet contacted.
Health Transformation Lab · Drill-down

**Speaker notes:** Each phase starts only if the one before it earned it. Phase 1 is deliberately small because it is part-time work alongside other priorities. The dates for phases 2 and 3 are set after phase 1 reports.

## Slide 24 — close

Health Transformation Lab · PerioBench and OralHealthBench
Oral health for all.
Millions, directly, in public, and verified.
Give us 180 days to measure it.

**Speaker notes:** Close on the ask. If a shark asks why this: no one we found scores these questions at scale, in public and for free; the medical-dental seam is where AI is weakest and the health gain is largest; and the pieces already exist: public benchmarks, open models, the OMOP standard, and a working pipeline on synthetic records with known answers.
