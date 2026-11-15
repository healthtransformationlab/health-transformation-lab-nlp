# PR 814 review: copy the proven Application Insights connection string into Databricks

Closes #813. Reviewed against `.claude/review-rubric.md` and AGENTS.md "Configuration and secrets".

- **Secrets:** the value moves between two secret stores inside one job. It is checked by shape only, passed to the
  API on stdin through `jq --arg`, never echoed, logged or written to disk; the OAuth token is masked. Only the key's
  update time is printed.
- **One declaration per setting:** the key name and scope are the ones `databricks.yml` and the register already use.
- **Register:** updated in the same PR (who writes the key, how to rotate).
- **Check before work:** a missing or malformed value fails before sign-in is used, naming the setting.
- **Environments:** dev only, said in the PR.
- **Pending, not blocking the merge:** the run needs WRITE for `dental-omop-ci` on the scope, which the owner grants;
  until then the write step fails with a permission error and changes nothing.
- **Rules:** no compute, publish, deletion or rule change: an agent may merge it when green.

Nothing blocking.
