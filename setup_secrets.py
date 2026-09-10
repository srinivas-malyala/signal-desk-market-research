"""Create/update legacy app secrets with an explicitly selected profile.

Lakebase URL secrets are retained only for prototype compatibility. Phase 4
migrates both apps to an attached Autoscaling Lakebase resource.
"""
import argparse
import getpass

from databricks.sdk import WorkspaceClient

parser = argparse.ArgumentParser()
parser.add_argument("--profile", required=True, help="Databricks CLI profile selected by the user")
args = parser.parse_args()

client = WorkspaceClient(profile=args.profile)
for scope in ("massive", "database"):
    try:
        client.secrets.create_scope(scope=scope)
    except Exception as error:
        if "already exists" not in str(error).lower():
            raise

client.secrets.put_secret(scope="massive", key="api-key", string_value=getpass.getpass("Massive API key: "))
client.secrets.put_secret(scope="database", key="lakebase-url", string_value=getpass.getpass("Lakebase Postgres URL: "))
print("Stored massive/api-key and database/lakebase-url. Grant both App service principals READ access to these scopes.")
