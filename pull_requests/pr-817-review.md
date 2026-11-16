# PR 817 review: record the new CI client secret and its expiry

Refs #813. Reviewed against AGENTS.md "Configuration and secrets".

- Register updated for a rotated credential: where it lives, expiry (2027-02-13, from the service principal secrets API), renew-by date 14 days before. No value.
- Says what happened (sign-in lost 17:09-17:39 UTC) and what is left: delete the October secret after a deploy.
- One YAML file; parses. No compute, publish or rule change: an agent may merge it when green.

Nothing blocking.
