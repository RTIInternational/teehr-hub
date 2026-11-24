# Note, this script needs to be manually copied from
# load_secrets.py to load-secrets.yaml
from prefect.blocks.system import Secret
import os
print("Running load secrets...")
api_usgs_pat = os.getenv("API_USGS_PAT")
Secret(value=api_usgs_pat).save(name="api-usgs-pat", overwrite=True)
print(f"✅ Successfully loaded api-usgs-pat into Prefect Secret block.")
# The v1 flows' client secret (teehr-platform-automation, ADR-0020 in teehr-cloud-core).
automation_secret = os.getenv("PLATFORM_AUTOMATION_CLIENT_SECRET")
if automation_secret:
    Secret(value=automation_secret).save(name="teehr-platform-automation-secret", overwrite=True)
    print("✅ Successfully loaded teehr-platform-automation-secret into Prefect Secret block.")
