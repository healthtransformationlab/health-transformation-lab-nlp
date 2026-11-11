# The competition's development set: how far the code graph leads to each fix

`devset_graph_reach.csv` repeats the counts of `../graph_coverage.csv` and `../statement_search.csv` on the
129 tasks of the competition's own development set (028 AI5, #669), so this project's 93 tasks can be set
beside them. One row per task.

**The tasks are the competition's.** They were read under its rules and are not redistributed here: the table holds
task ids, counts and ranks only. No statement, patch, test, graph or embedding of the competition's is in this
repository.

## How it was made

`python/scripts/67_devset_graph_reach.py`, on November 11, 2026, from:

- the competition's `tasks.jsonl`, graphs and embeddings (`gemma-4-developer-agent`, downloaded with the Kaggle API
  and never committed): fastapi 67, rich 48, requests 13, httpx 1 tasks;
- each file a reference patch changes, read once from GitHub at the task's base commit. The repositories are
  public; the snapshots are 21.5 GB and were not downloaded;
- EmbeddingGemma at the revision this project's own node vectors use (`task_graph.EMBED_REVISION`), on a CPU.

The rules are those of scripts 63 and 64, reused and not rewritten: an edited node is the innermost function, class
or method that holds a changed line; a node is named when the statement holds its identifier or a code span of it;
call distance follows `calls` edges in either direction; chance is a random ranking of each graph's nodes. The
competition's patches have plain `--- a/` headers, so the script adds the `diff --git` line those rules read.

## What it shows

| | This set | Development set |
|---|---|---|
| Tasks | 93 | 129 |
| The fix touches no module the graph covers | 31 | 5 |
| It changes no existing function, class or method | 11 | 10 |
| It edits a node the graph holds | 51 | 114 |
| Of those: the statement names an edited node | 20 | 29 |
| Of those: call edges lead to one from a named node | 2 | 23 |
| Of those: embedding search ranks one first (by chance) | 15 (0.6) | 6 (0.1) |
| Of those: embedding search, first ten (by chance) | 30 (5.4) | 34 (1.5) |
| Of those: a name, a call edge or the search's first ten | 42 | 66 |

The development graphs are larger (a median of 3,256 nodes in the 114 tasks, against 398 in this set's
51), so a random ranking finds less there.

## The competition's own embeddings

The provided embeddings have 256 dimensions, as this project's do, but they are not EmbeddingGemma document vectors:
on the 759 nodes of one requests graph (`requests_7505`), the cosine between the two vectors of the same node
averages 0.05 and never passes 0.21 (measured once while the table was made; not a column of it). So embedding search
is counted twice:

- `edited_node_best_rank_num`: this project's method. EmbeddingGemma embeds every node (document prompt) and the
  statement (query prompt), cut to 256 dimensions, and the nodes are ranked by cosine similarity.
- `provided_edited_node_best_rank_num`: the provided vectors, searched the way the competition's `search_similar_code`
  is documented to work, from a symbol and not from text. From each node the statement names, where the closest
  edited node comes among its nearest nodes. 0 means the statement names an edited node itself, so the search found
  nothing new.

By the provided vectors, a named node's ten nearest include an edited node in 6 tasks beyond the 29 whose statement
names one outright. Call edges already reach all of them: 0 are tasks that names and call edges miss. In 25 tasks the closest
edited node is further than ten, and in 54 the statement names no node to search from.

## Beside an earlier count, and the host's word on derived data

A participant published a model-free localization benchmark on the same 129 tasks on the competition's Paper Track
forum (topic 748395, October 11, 2026). It reports 117 tasks with a gold node in the graph, 28% of reports naming
the exact function, and the edit site within two hops of a named symbol in 47.9%. The counts here, made
separately with this project's rules, are 114 tasks, 25% (29 of 114) and 46% (52 of 114, by
any number of call edges). The two agree closely; what this table adds is the same counts for a second kind of
repository beside them.

On publishing tables like this one, the host answered on the same forum that derived labels keyed by task id may be
published (topics 749803 and 757562), with the task data itself left in the competition.

## Columns

| Column | Holds |
|---|---|
| `instance_id` | the competition's task id |
| `graph_node_count` | nodes in the task's graph |
| `changed_file_count`, `graphed_file_count` | files the reference patch changes, and how many of them are modules the graph covers |
| `is_fix_in_graph` | the patch changes at least one such module |
| `edited_node_count` | functions, classes and methods of the base commit that hold a changed line |
| `statement_node_count` | graph nodes the statement names |
| `statement_to_fix_edge_count` | fewest `calls` edges from a named node to an edited one (0: the statement names an edited node); empty when there is no path or no named node |
| `edited_node_best_rank_num` | where the best edited node comes when EmbeddingGemma ranks the graph's nodes against the statement (1 is first) |
| `provided_edited_node_best_rank_num` | the same from a named node under the provided vectors, as described above |

## What it does not say

- These are counts from files, not agent runs: no model made these searches.
- A node is named by a fixed rule, so a statement that describes a function without its name names nothing. The
  name and call-edge counts are lower bounds, in both sets.
- The search over the provided vectors is this project's reading of the documented tool, not the tool itself.
