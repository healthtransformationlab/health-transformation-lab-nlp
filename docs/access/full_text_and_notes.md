# Health Transformation Lab: AccessBench, does the answer get you care?: full text and notes
A personal idea, not affiliated with or endorsed by any organization. Built from `slides/` by `docs/build_decks.py`; edit the slides, then rebuild.

## Slide 1 — cover

AccessBench · exploratory · November 2026
The answer can be right.
Does it get you care?
AccessBench asks whether an AI answer helps someone actually get care: coverage, cost, appeals, travel and accommodations, not only whether the facts are sound.
The third benchmark, after
PerioBench
(finding gum disease in dental records) and
OralHealthBench
(accurate answers where medicine meets dentistry).
John Bowyer · personal project, not affiliated with any organization · synthetic questions, no patient data

**Speaker notes:** AccessBench is the third of the three benchmarks, and the most exploratory. PerioBench asks whether we can find gum disease in the dental record; OralHealthBench asks whether AI gives accurate answers where medicine meets dentistry. AccessBench asks the question people actually live with: after reading the answer, can I get the care? An answer can be medically correct and still useless if it ignores that the person is on Medicaid in one particular state, has a denial letter in hand, or has a one-year waiting period. This is a personal project, not any organization's plan, and every question is synthetic, written from public sources.

## Slide 2 — problem

The gap
Getting care is a pathway, not a fact
Coverage
Is it covered on my plan, in my state?
Adult Medicaid dental is optional for states, so the right answer depends on the state and the plan (CMS).
Denials
They said no. What now?
A written denial, the appeal deadline, the dentist's charting and narrative: the steps decide whether care happens.
The visit itself
Did I get what I needed?
A cleaning is not a periodontal evaluation with probing and charting (ADA/IHS coding guidance for D0180).
What AccessBench scores:
does the answer name the next concrete step for
this
person, and avoid the confident wrong turn ("Medicare covers deep cleanings", "just pay cash")?
Synthetic questions grounded in public sources · Health Transformation Lab · AccessBench · 2

**Speaker notes:** Most health AI benchmarks ask whether the facts are right. For getting care, the facts are only the start. Three things decide whether someone gets a gum check. Coverage: adult dental benefits are optional for state Medicaid programs, so a good answer says it depends on the state and the plan, and tells the person how to check. Denials: when a plan says no, what matters is getting the denial in writing, the appeal deadline, and the dentist's charting and narrative. And the visit itself: a polish is not a periodontal evaluation; the coding guidance separates the comprehensive periodontal evaluation, code D0180, from a routine cleaning. AccessBench scores whether the answer names the next concrete step for this person, and whether it avoids the confident wrong turn.

## Slide 3 — questions

The first questions
Ten hard asks about getting a gum check
Medicaid coverage by state:
New York, Florida (under-21), Medi-Cal, pregnancy coverage
Denials and appeals:
a deep cleaning denied for "no bone loss", prior authorization refused, x-rays rejected
Private plans:
a one-year waiting period for periodontics
Medicare and medical insurance:
the dental exclusion and its narrow exceptions (42 CFR 411.15(i)); diabetes does not move care onto medical benefits
The visit:
a cleaning versus a comprehensive periodontal evaluation (D0180), and what to ask the office to chart
Each ask is written from a
real public question
(forum threads, KFF, IHS coding guidance) and scored against
published
sources only. The questions are synthetic: no one's own words or details.
Synthetic questions grounded in public sources · Health Transformation Lab · AccessBench · 3

**Speaker notes:** These are the first ten scored questions, all about one thing: getting a periodontal screening. Each began as a real question people asked in public, on forums, or as a gap named in a KFF survey or Indian Health Service coding guidance, and was rewritten as a synthetic ask with no one's own words or details. They cover Medicaid coverage that differs by state, including pregnancy; denials and appeals; waiting periods on private plans; the Medicare dental exclusion and its narrow exceptions, and the common belief that diabetes moves gum care onto medical insurance; and whether the visit that was booked is the evaluation the person needs. Every rubric cites published statutes, CMS pages or guidelines.

## Slide 4 — scoring

How an answer is scored
Must say, must not say
Must include
4 key points per question
The steps that get this person care, such as: get the denial in writing, ask which procedure codes were billed, call the state's dental line.
Red flags
1 to 2 per question
The confident wrong turn, such as "all adult Medicaid covers gum exams" or "ignore the bill". Any red flag the answer says is recorded, with a harm grade (S0 to S2).
The judge
Key points, one by one
A second model checks each point, five per question as in GlobalDentBench (red flags fill any gap). Harder, date-sensitive questions are level L3.
The score
is the share of key points covered;
the access gate
passes only when the key points are met and no red flag is said. Each question names its evidence source, so a reviewer can check the rubric itself.
Synthetic questions grounded in public sources · Health Transformation Lab · AccessBench · 4

**Speaker notes:** Each question carries its own rubric. Four things a good answer must include: the concrete steps that lead to care for this person. And one or two red flags: the confident wrong turns, such as claiming every adult Medicaid program covers gum exams, or telling someone to ignore a bill. A red flag is recorded with a harm grade, and the access gate fails it even if the key points are there, because a wrong pathway can cost someone the visit or a large bill. A second model acts as judge and checks the key points one at a time, using the key-point grader of the grader dashboards (spec 019), five key points per question as in GlobalDentBench, the red flags filling any gap; the score is the share of key points covered. Each question names its evidence, so the rubric itself can be reviewed by someone who knows the programs.

## Slide 5 — privacy

A second gate
Help them, without repeating their details
The asks
5 questions with planted details
Real-sounding access questions (no insurance, no car, VA care, a wheelchair, CHIP) that include invented names, phone numbers and IDs.
Gate 1: the pathway
Same rubric as before
Key points met, red flags avoided.
Gate 2: no leak
None of the planted details come back
Checked with the same leak check PerioBench uses for de-identification.
Every planted detail is invented: names from a synthetic pool, example phone numbers, Social Security numbers starting with 9, which are never issued.
Real patient data never enters AccessBench.
Synthetic questions grounded in public sources · Health Transformation Lab · AccessBench · 5

**Speaker notes:** People asking for help often tell the AI who they are: a name, a phone number, a member ID. AccessBench has a second small set of five questions that do exactly that, across five kinds of access problem: no insurance, no car, VA care, a wheelchair, and a child on CHIP. An answer has to pass two gates: help with the pathway, and not repeat any of the details back. The leak check is the same one PerioBench uses for de-identification. Every planted detail is invented; the Social Security numbers start with 9, which are never issued. Real patient data is never allowed in AccessBench.

## Slide 6 — databricks

Built to run
One job scores every model the same way
Databricks job "Access LLM batch"
sends each question to each answering model, then to the judge
Two gold tables:
dim_access_question
(one row per question) and
fact_access_answer
(one row per answer, with its verdicts, tokens and cost)
Simulated by default:
no model is called and nothing is billed; simulated rows are labelled simulated
Live mode
uses pay-per-token endpoints and stops when its spending limit is reached
No live scores yet.
The job, the tables and the rubrics are built and tested; the first live run waits for the owner's go-ahead on which models and what budget.
Synthetic questions grounded in public sources · Health Transformation Lab · AccessBench · 6

**Speaker notes:** The plumbing is built. A Databricks job called Access LLM batch sends each question to each answering model and then to the judge, and writes the results into two gold tables: one row per question, and one row per answer with its verdicts, tokens and cost. By default it runs in simulated mode: no model is called, nothing is billed, and the rows say simulated. Live mode uses pay-per-token endpoints and stops when it reaches its spending limit. There are no live scores yet, and this deck shows none. The first live run waits for a decision on which models to compare and how much to spend.

## Slide 7 — next

What comes next
From ten questions to a benchmark
1. A first live run
A few models, a small budget
The ten screening questions and the five privacy questions, through the batch job, with the cost recorded.
2. Expert review
Check the rubrics
People who work Medicaid, appeals and dental billing review each key point and red flag before any score is published.
3. Grow the set
Beyond the gum check
Travel, safety-net clinics, VA dental, children's coverage and accommodations, written the same way from public questions.
The north star:
more people completing a periodontal screening by 2030. It is the owner's own stretch goal, not any organization's target. Detail:
benchmarks/access_bench/
.
Synthetic questions grounded in public sources · Health Transformation Lab · AccessBench · 7

**Speaker notes:** Three steps from here. First, a small live run: a few models on the fifteen questions, through the batch job, with the cost recorded, so there is a first real score. Second, expert review: people who work with Medicaid, appeals and dental billing check every key point and red flag before any score is published, because a benchmark is only as good as its answer key. Third, grow the set beyond the gum check, to travel, safety-net clinics, VA dental, children's coverage and accommodations, using the same method. The north star is more people completing a periodontal screening by 2030; that is a personal stretch goal, not any organization's target. Everything is in the benchmarks/access_bench folder of the repository.
