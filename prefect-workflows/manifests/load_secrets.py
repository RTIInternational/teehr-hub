# Note, this script needs to be manually copied from
# load_secrets.py to load-secrets.yaml
from prefect.blocks.system import Secret
import os
print("Running load secrets...")
api_usgs_pat = os.getenv("API_USGS_PAT")
Secret(value=api_usgs_pat).save(name="api-usgs-pat", overwrite=True)
print(f"✅ Successfully loaded api-usgs-pat into Prefect Secret block.")