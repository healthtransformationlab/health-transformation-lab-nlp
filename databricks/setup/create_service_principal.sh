#!/usr/bin/env bash
# creates the identity a bundle target is deployed and run as: the service principal
# dental_omop_nlp_<target>_sp and the admin group dental_omop_nlp_<target>_admin (you and the principal).
# both are account level (unity catalog sees only account principals) and assigned to this workspace;
# works on Free Edition, which has no account console, through the workspace's account SCIM proxy.
# it gives the group CREATE CATALOG on the metastore: the deploy creates the catalog, schemas and volume
# (databricks/resources/unity_catalog.yml) and grants the group ALL PRIVILEGES on the catalog.
# the OAuth secret is not made here: the script prints the command, and the secret goes straight into
# GitHub (gh secret set), never into a file. run once per target, logged in as a workspace admin:
#   databricks auth login --host https://<workspace>
#   databricks/setup/create_service_principal.sh uat [--judge-endpoint <serving endpoint>]
#   databricks/setup/create_service_principal.sh uat --print-config   # names only, no workspace calls
# guide: docs/deployment.md
set -euo pipefail
target="${1:?target: dev, uat or prod}"
shift
endpoint="" print_only=""
while [ $# -gt 0 ]; do
  case "$1" in
    --judge-endpoint) endpoint="${2:?endpoint name}"; shift 2 ;;
    --print-config) print_only=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
root="$(cd "$(dirname "$0")/../.." && pwd)"
# catalog and secret scope as the bundle resolves them for the target (default, then target override)
read -r catalog scope < <(python3 - "$root/databricks.yml" "$target" <<'EOF'
import sys, yaml
b = yaml.safe_load(open(sys.argv[1]))
if sys.argv[2] not in b["targets"]:
    sys.exit(f"no target {sys.argv[2]!r} in databricks.yml")
v = {k: x.get("default") for k, x in b["variables"].items()}
v.update(b["targets"][sys.argv[2]].get("variables", {}))
print(v["catalog"], v["hf_secret_scope"])
EOF
)
sp="dental_omop_nlp_${target}_sp"
group="dental_omop_nlp_${target}_admin"
if [ -n "$print_only" ]; then echo "$sp $group $catalog $scope"; exit 0; fi
json_field() { python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }

me=$(databricks current-user me -o json | json_field id)
sp_json=$(databricks api post /api/2.0/account/scim/v2/ServicePrincipals --json "{\"displayName\": \"$sp\", \"active\": true}")
sp_id=$(echo "$sp_json" | json_field id)
sp_app=$(echo "$sp_json" | json_field applicationId)
group_id=$(databricks api post /api/2.0/account/scim/v2/Groups \
             --json "{\"displayName\": \"$group\", \"members\": [{\"value\": \"$me\"}, {\"value\": \"$sp_id\"}]}" | json_field id)
for id in "$group_id" "$sp_id"; do
  databricks api put "/api/2.0/preview/permissionassignments/principals/$id" --json '{"permissions": ["USER"]}' > /dev/null
done
# printed before the grants: a failed grant stops the script, and these ids are what the next steps need
echo "created $sp (id $sp_id, application id $sp_app) and $group with you and the principal"
# without workspace-access every API call fails; without databricks-sql-access validate can't look up the warehouse
databricks service-principals patch "$sp_id" --json '{"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
  "Operations": [{"op": "add", "path": "entitlements", "value": [{"value": "workspace-access"}, {"value": "databricks-sql-access"}]}]}' > /dev/null
# the secret scope the MedGemma (hf_token) and Lakebase (lakebase_url) notebooks read
databricks secrets create-scope "$scope" 2> /dev/null || true
databricks secrets put-acl "$scope" "$sp_app" READ
# the deploy creates catalog $catalog (and its schemas and volume), so the group needs CREATE CATALOG;
# don't create the catalog here, or the deploy fails on "already exists"
metastore=$(databricks metastores current -o json | json_field metastore_id)
databricks grants update metastore "$metastore" --json "{\"changes\": [{\"principal\": \"$group\", \"add\": [\"CREATE_CATALOG\"]}]}" > /dev/null
if [ -n "$endpoint" ]; then   # the LLM judge's serving endpoint (bundle variable judge_endpoint)
  ep_id=$(databricks serving-endpoints get "$endpoint" -o json | json_field id)
  databricks serving-endpoints update-permissions "$ep_id" \
    --json "{\"access_control_list\": [{\"service_principal_name\": \"$sp_app\", \"permission_level\": \"CAN_QUERY\"}]}" > /dev/null
fi
cat <<EOF
done: secret scope $scope, group $group with CREATE CATALOG (the deploy creates $catalog).
next (docs/deployment.md):
  1. OAuth secret, 90 days; shown once, put it straight into GitHub:
       databricks service-principal-secrets-proxy create $sp_id --lifetime 7776000s
  2. GitHub environment $target:
       gh api -X PUT repos/<owner>/health-transformation-lab-nlp/environments/$target
       gh variable set DATABRICKS_HOST      -R <owner>/health-transformation-lab-nlp -e $target -b <workspace url>
       gh variable set DATABRICKS_CLIENT_ID -R <owner>/health-transformation-lab-nlp -e $target -b $sp_app
       gh variable set SERVICE_PRINCIPAL    -R <owner>/health-transformation-lab-nlp -e $target -b $sp_app
       gh secret set   DATABRICKS_CLIENT_SECRET -R <owner>/health-transformation-lab-nlp -e $target
  3. Actions > auth_check > Run workflow (environment $target): it should print $sp_app.
EOF
