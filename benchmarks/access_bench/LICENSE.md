# AccessBench licence

Personal learning project, not affiliated with any employer or organization (see [DISCLAIMER](../../DISCLAIMER.md)).

## What this licence covers

The AccessBench **questions** (`items/*.jsonl`), their **answer keys** (the `must_include` points, `red_flags` and
`resources` in those files), the **control answers** (`controls/*.jsonl`), the seeds (`seeds/`) and the authoring
prompts (`prompts/`) are licensed under the **Creative Commons Attribution 4.0 International licence (CC BY 4.0)**:
https://creativecommons.org/licenses/by/4.0/

You may copy, adapt and redistribute them, for any purpose, if you credit "AccessBench, Health Transformation Lab"
with a link to this repository and say whether you changed them. The code that loads and scores them is under the
repository's Apache 2.0 licence ([`LICENSE`](../../LICENSE)). CC BY 4.0 is this repository's default for published
data unless a source's own licence says otherwise (AGENTS.md, "Publishing datasets").

## Why we may license it: where the content comes from

| Source | How it is used | Why that is allowed |
|---|---|---|
| Our own writing | Every question, answer key and control answer is written by the project, in its own words | We hold the copyright and grant it under CC BY 4.0 |
| Public Reddit threads (9 questions, `source_thread_url`) | A real person's situation prompted the question; the question is rewritten in our words, with no post text, username or detail that identifies the poster, and the thread is linked as provenance | Copyright protects a post's wording, not the situation it describes; nothing of the post is reproduced, so Reddit's and the posters' rights in their text are not used. The link only points to the public thread |
| US federal sources (CMS, eCFR, HRSA, NIDCR, CFPB, IRS, IHS, VA) | Facts, rules and resource names behind the answer keys, cited in `evidence_source` and `evidence_urls` | Works of the US federal government are in the public domain (17 U.S.C. 105); facts such as a deadline or an interest rate aren't copyrightable in any case |
| Other public pages (ADA, KFF, PMC articles, state Medicaid pages) | Cited for a fact or a resource name; never copied | Citing a fact and linking a page needs no licence; no text is reproduced |
| Planted personal details (`planted_phi`) | Invented names, phone numbers and IDs, used to test whether an answer repeats them | Invented; no real person's data (synthetic only) |

## What it does not cover

- The linked pages themselves: each keeps its own terms.
- Answers written by AI models in our runs (`data/access_bench/runs/`): those follow each model provider's terms.
- Trademarks and program names (Medicaid, VADIP and others) are used only to name the program.

## Please keep AccessBench out of training data

Every row carries `canary_text`, a fixed string with a GUID. If you build a training corpus, drop any file that holds
it; a model that can repeat the GUID has likely seen these questions, and its AccessBench score shouldn't be trusted
([docs/access_bench_validity.md](../../docs/access_bench_validity.md)).
