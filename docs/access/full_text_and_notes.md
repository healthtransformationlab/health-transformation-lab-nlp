# Health Transformation Lab: AccessBench: Oral Health, does the answer get people to care?: full text and notes
A personal idea, not affiliated with or endorsed by any organization. Built from `slides/` by `docs/build_decks.py`; edit the slides, then rebuild.

## Slide 1 — cover

AccessBench: Oral Health · exploratory · November 2026
Millions ask AI how to get care.
Does the answer get them there?
AccessBench grades whether the AI people already use helps them actually get care, shares what each model misses with the companies behind it, and tracks whether the answers improve, round after round.
Oral health first. Coming soon:
AccessBench: Medical Care
and
AccessBench: Mental Health
.
John Bowyer · personal project, not affiliated with any organization · synthetic questions, no patient data

**Speaker notes:** People now ask AI the questions they used to bring to a benefits counselor or a dental office's front desk: is this covered, what do I do about this bill, where can I go that I can afford. AccessBench grades whether the answer actually gets them to care, shows the companies behind these tools what their AI missed, and re-measures every round so progress can be tracked. This deck is AccessBench: Oral Health, about dental care; AccessBench: Medical Care and AccessBench: Mental Health are coming soon, built the same way. This is a personal project, not any organization's plan, and every question is synthetic, written from public sources.

## Slide 2 — reach

The scale
People already ask AI how to get and pay for care
ChatGPT alone
40 million a day
people asking it health questions, worldwide (OpenAI's own figure, January 2026, as reported by Axios)
Insurance questions
1.6 to 1.9 million a week
health-insurance messages to ChatGPT: coverage, bills, appeals (same OpenAI report)
Everyday use
10.3% of US adults
use generative AI at least daily (JAMA Network Open, 2026; a 50-state survey, spring 2025)
These are the questions people used to bring to a benefits counselor, a dental office's front desk or a legal-aid line:
is it covered, what do I do about this bill, where can I go that I can afford.
Cited sources in docs/claims.yaml · AccessBench: Oral Health · 2

**Speaker notes:** People are not waiting for AI to be approved for health questions. OpenAI reported in January 2026 that more than 40 million people a day ask ChatGPT about health, worldwide, and that it gets between 1.6 and 1.9 million health-insurance messages a week. That is OpenAI's own figure, as reported by Axios and Medical Economics, not an independent count. And a 50-state survey of more than 20,000 US adults in spring 2025, published in JAMA Network Open in 2026, found 10.3 percent use generative AI at least daily; that survey drew from an internet panel, not a probability sample. The point is the kind of question: coverage, bills, appeals and where to go. Those used to go to a benefits counselor, a front desk or a legal-aid line.

## Slide 3 — problem

The problem
The answers are often incomplete, and sometimes wrong
Dental advice from chatbots
65% to 79% accurate
pooled accuracy on dental-emergency advice across 10 studies, by chatbot (Dental Traumatology meta-analysis, 2026)
Real dental cases
1 in 3
answers from 12 frontier models to dental case questions rated unsafe by the study's AI judge (GlobalDentBench, 2026)
Getting care is harder still
It depends
on the state, the plan, the person's age and a deadline: adult Medicaid dental is optional for states; Medicare excludes routine dental care
One fact changes the answer. A 19-year-old on Medicaid is covered by the under-21 rule (EPSDT) for medically necessary dental care; at 23 they are not. An answer that misses it sends someone to pay over a thousand dollars cash, or to give up.
Cited sources in docs/claims.yaml · AccessBench: Oral Health · 3

**Speaker notes:** Accuracy studies of chatbots on dental questions find real gaps. A 2026 meta-analysis in Dental Traumatology pooled 10 studies of advice on dental injuries: accuracy was 65 percent for ChatGPT 3.5, 79 percent for ChatGPT 4 and 70 percent for Gemini, so roughly one answer in five to one in three was inaccurate, and the authors warn that even limited inaccuracies can delay care. GlobalDentBench, a 2026 preprint, found that 1 in 3 of those answers was rated unsafe by the study's AI judge on case questions from real dental reports, across 12 frontier models. Getting care is harder than clinical facts, because the right answer depends on the state, the plan, the person's age and a deadline. Adult Medicaid dental is optional for states, and Medicare excludes routine dental care. One fact can flip the answer: a 19-year-old on Medicaid is covered by the under-21 rule called EPSDT; a 23-year-old is not. Nobody was measuring whether AI gets these right. That is the gap AccessBench fills.

## Slide 4 — approach

How AccessBench addresses it
After reading the answer, could you take the next step?
Real situations
Written from public questions
Medicaid coverage and denials, Medicare's dental exclusion, waiting periods, discount plans and medical credit cards, rides, VA dental, wheelchair access, a child on CHIP. The people are invented; the rules are real.
Graded for action
Not for sounding right
Did it make the points this person needs? Give a usable next step: what to do first, whom to call, when, and a fallback? Avoid the confident wrong turn, such as "a denial means you owe"?
Graded for safety
Harm and privacy apart
Any harmful advice is graded, never offset by points earned elsewhere. Answers must not repeat a person's name, phone or ID back.
Every answer key was reviewed by five other AI models (ChatGPT, Gemini, Copilot, Perplexity, Grok) and revised; seeded
control answers
check that the AI judge can tell a harmful answer from a good one.
Synthetic questions grounded in public sources · AccessBench: Oral Health · 4

**Speaker notes:** AccessBench asks one question of every answer: after reading it, could this person take the next step? The questions are written from real public questions, on Medicaid coverage and denials, Medicare's dental exclusion, waiting periods, discount plans and medical credit cards, rides, VA dental, wheelchair access and a child on CHIP. The people are invented; the rules are real. Each answer is graded for action, not for sounding right: did it make the points this person needs, did it give a usable next step, did it avoid the confident wrong turn. Harm and privacy are graded separately, so a harmful answer can't make up for it with points elsewhere. Five other AI models reviewed the questions and answer keys, and the keys were revised from their reviews. And seeded control answers, written to known grades, check that the AI judge can tell harmful advice from good advice.

## Slide 5 — goal

The goal
Better answers where people already ask
1. Measure
Grade the AI people use
ChatGPT, Claude, Gemini and others, on the same questions and the same grading, with each model's version and date recorded.
2. Share
Show each company what its AI missed
The questions, the answer keys and the steps each model left out, so the companies behind these tools can fix them.
3. Re-measure
Track progress every round
Run the same questions again and report, model by model, whether answers give more of the steps people need, with less harm.
Success is measured, not claimed:
the share of needed steps each model gives, round after round
. Better answers in the tools millions already use reach more people than any one clinic or website can.
Personal project, not affiliated with any organization · AccessBench: Oral Health · 5

**Speaker notes:** This is what AccessBench is for. People already get their health information from a handful of AI tools, so the fastest way to improve what they hear is to improve those tools. The loop has three steps. Measure: grade the AI people actually use, ChatGPT, Claude, Gemini and others, on the same questions with the same grading, recording each model's version and the date. Share: publish what each model missed and give the companies behind these tools the questions, the answer keys and the failures, so they can fix them. Re-measure: run the same questions again every round and report, model by model, whether answers give more of the steps people need, with less harm. Success is measured, not claimed: the share of needed steps each model gives, round after round. Better answers in tools that millions already use reach more people than any one clinic or website can.

## Slide 6 — findings

What we found
Half the steps people need were missing
Of the steps a person needed to get care, how many did each AI give? (22 questions; four free, open AI models.)
gpt-oss-120b
OpenAI's free, open model
77.7%
Clear next step in 21 of 22 answers · 1 answer could lead to harm
Gemma 3 12B
Google's small open model
72.7%
Clear next step in 20 of 22 answers · 3 answers could lead to harm, 1 of them seriously
Llama 3.3 70B
Meta's open model
32.5%
Clear next step in 18 of 22 answers · 5 answers could lead to harm
Llama 4 Maverick
Meta's newer open model
29.1%
Clear next step in 16 of 22 answers · 7 answers could lead to harm
Overall, the answers gave
187 of the 352
steps people needed. The top model wrote such long answers that most were cut off at our length limit, so part of its score may come from listing everything.
Run 608662392694095, synthetic questions, preliminary (one AI judge) · AccessBench: Oral Health · 6

**Speaker notes:** This is the first run on the revised questions, on four free, open AI models hosted on Databricks: OpenAI's gpt-oss-120b, Google's Gemma 3 12B and two of Meta's Llama models. Each bar answers one question: of the steps a person needed to get care, what share did the AI give? gpt-oss-120b gave 77.7 percent and Gemma 72.7 percent; the two Llama models gave about a third, 32.5 and 29.1 percent. Under each bar: how many answers gave a clear next step, meaning what to do first, whom to call, when, and a fallback; and how many answers could lead to harm, such as a delay in care or an avoidable bill, or seriously, such as skipping needed care or a large cost. Overall the answers gave 187 of the 352 steps people needed, about half. One caution: every answer was capped at 1,500 tokens, about 1,100 words, and gpt-oss-120b hit that limit on 18 of 22 questions, so its answers were cut off and part of its score may come from listing everything. The grades come from one AI judge not yet checked by an independent person, so they are preliminary. ChatGPT, Claude and Gemini are not in this run yet.

## Slide 7 — missed

What every model missed
The steps that matter most were the ones left out
Pain and swelling
0 of 4 said: get urgent care now
A person in pain, waiting on a gum-treatment decision, and a parent with a child's broken tooth: no model said swelling or fever needs care today.
One fact changes the answer
0 of 4 caught it at 23
At 19, 2 of 4 models named the under-21 Medicaid rule. At 23, when it no longer applies, none said so, and one said it still did.
The programs people don't know
0 of 4 named them
The VA's dental insurance program for veterans without VA dental; the difference between Medicaid and a separate CHIP program for a child.
These are not trivia. Each missing step is the difference between getting care this week and an emergency visit, a cash bill or giving up.
Run 608662392694095, synthetic questions, preliminary (one AI judge) · AccessBench: Oral Health · 7

**Speaker notes:** Where the models fell short is the point of AccessBench. Two questions involved pain: a person whose office won't treat a painful wisdom tooth until gum treatment is approved, and a parent whose child has a broken tooth. No model said that swelling, fever or trouble swallowing needs urgent care today. The Florida pair shows how one fact changes the answer: at 19, two of the four models named the under-21 Medicaid rule, EPSDT, that covers medically necessary dental care; at 23, when it no longer applies, none of the four said so, and one said it still did. And no model named the VA Dental Insurance Program for a veteran without VA dental, or told a parent to find out whether their child is in Medicaid or a separate CHIP program, which decides the dental rules. Each missing step is the difference between getting care this week and an emergency visit, a cash bill or giving up. The judge itself passed 6 of 10 seeded control answers: it caught both clearly harmful answers and credited both good ones, but it counts incomplete answers as some harm, which still needs a decision.

## Slide 8 — next

What comes next
Grade the AI people actually use
1. The major models
ChatGPT, Claude, Gemini
The same questions and grading, with each model's version and date recorded: the first round to track from.
2. A second reviewer
Someone who does this work
A Medicaid, dental-billing or legal-aid expert grades the same answers, so the results don't rest on one person and one AI judge.
3. Coming soon
AccessBench: Medical Care and AccessBench: Mental Health
The same method for hospital bills and financial assistance, crisis lines and finding low-cost treatment.
The north star: more people completing a periodontal screening by 2030, the owner's own stretch goal, not any organization's target. Detail:
benchmarks/access_bench/
.
Personal project, not affiliated with any organization · AccessBench: Oral Health · 8

**Speaker notes:** Three steps next. First, grade the AI people actually use: ChatGPT, Claude and Gemini, on the same questions with the same grading, recording each model's exact version. Second, a second reviewer who does this work, from Medicaid, dental billing or legal aid, grades the same answers, so the results stop resting on one person and one AI judge. Third, AccessBench: Medical Care and AccessBench: Mental Health, coming soon, take the same method to hospital bills and financial assistance, crisis lines and finding low-cost treatment. The north star is more people completing a periodontal screening by 2030; that is a personal stretch goal, not any organization's target.

## Slide 9 — method

Appendix: how it works
Questions, grading and the run
Questions
22 in three groups
Gum-care coverage and appeals, dental discounts and vouchers, and access questions with invented personal details. Each names its jurisdiction, its sources and a date to recheck them.
Grading
An AI judge, point by point
For each point: met, partial, missing or contradicted, with the words that earned it. Plus next step, harm (none, some, serious), resources by fit, and the privacy check.
The run
One Databricks job
Each model answers each question; the judge grades; results land in two gold tables with cost and tokens. A spending cap stops a run before it overspends.
Every person in every question is invented; real patient data never enters AccessBench. Results are preliminary until an independent reviewer has graded answers.
Synthetic questions grounded in public sources · AccessBench: Oral Health · 9

**Speaker notes:** For those who want the method. There are 22 questions in three groups: getting gum care covered and appealing denials, dental discounts and vouchers, and access questions that include invented personal details to test privacy. Each question names its jurisdiction, its sources and a date to recheck them, because these rules change. An AI judge grades each answer point by point: met, partial, missing or contradicted, quoting the words that earned it; it also checks for a usable next step, grades harm as none, some or serious, rates resources by how well they fit, and the privacy check looks for repeated identifiers. One Databricks job sends every question to every model, has the judge grade the answers, and writes the results with cost and tokens to two gold tables; a spending cap stops a run before it overspends. Every person is invented, and results stay preliminary until an independent reviewer has graded answers.
