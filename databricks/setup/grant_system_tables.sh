#!/usr/bin/env bash
# lets a target's jobs read the system tables the pipeline doctor needs (spec 027, issue #504): grants the
# target's admin group dental_omop_nlp_<target>_admin (you and the target's service principal, made by
# create_service_principal.sh) USE_CATALOG on system and USE_SCHEMA and SELECT on system.lakeflow, nothing more.
# a bundle can't hold these grants: bundle grants cover only resources the bundle creates, and the system
# catalog is Databricks'. adding a privilege the group already has changes nothing, so it is safe to run again.
# run once per target, logged in as a metastore admin (on Free Edition, the workspace's owner):
#   databricks auth login --host https://<workspace>
#   databricks/setup/grant_system_tables.sh dev
#   databricks/setup/grant_system_tables.sh dev --print-config   # names only, no workspace calls
# guide: docs/deployment.md
set -euo pipefail
target="${1:?target: dev, uat or prod}"
shift
print_only=""
while [ $# -gt 0 ]; do
  case "$1" in
    --print-config) print_only=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
root="$(cd "$(dirname "$0")/../.." && pwd)"
python3 - "$root/databricks.yml" "$target" <<'EOF'
import sys, yaml
if sys.argv[2] not in yaml.safe_load(open(sys.argv[1]))["targets"]:
    sys.exit(f"no target {sys.argv[2]!r} in databricks.yml")
EOF
group="dental_omop_nlp_${target}_admin"
catalog="system"
schema="system.lakeflow"   # job_run_timeline and jobs: the doctor reads nothing else in system
if [ -n "$print_only" ]; then echo "$group $catalog $schema"; exit 0; fi

databricks grants update catalog system \
  --json "{\"changes\": [{\"principal\": \"$group\", \"add\": [\"USE_CATALOG\"]}]}" > /dev/null
databricks grants update schema system.lakeflow \
  --json "{\"changes\": [{\"principal\": \"$group\", \"add\": [\"USE_SCHEMA\", \"SELECT\"]}]}" > /dev/null
echo "granted $group: USE_CATALOG on $catalog; USE_SCHEMA and SELECT on $schema"
databricks grants get-effective schema "$schema" --principal "$group" -o json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('effective on $schema:', sorted({p['privilege'] for a in d.get('privilege_assignments', []) for p in a.get('privileges', [])}))"
