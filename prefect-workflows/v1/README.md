# v1 Prefect flows

Flows for the v1 warehouse (ADR-0019 in teehr-cloud-core), apart from the legacy flows: their
own image (`Dockerfile`: teehr-core's warehouse writer and builders, Prefect; no legacy
`teehr`, Spark or JVM), deployer job and deployments (`prefect-local.yaml`,
`prefect-remote.yaml`), on the shared `kubernetes-pool`. They act as `prefect-polaris`, whose
`teehr-platform-write` role writes `public`.

- `flows/derived.py`: build a derived dataset (percentiles, climatology, naive scale) of an
  observed timeseries. Register the dataset first:
  `teehr datasets create usgs_streamflow_percentiles -p public --kind percentiles --observed usgs_streamflow`.
- `flows/evaluations.py`: run a project's evaluations (default: all of `platform`, the specs in
  `evaluations/platform/`) through the control plane, one at a time, waiting for each.
  Deployed as `run-platform-evaluations` (daily, starts paused). Runs act as their caller, so
  the flow uses a personal token of the platform's automation user (see below).
- `tests/smoke_derived.py`: the flow against a throwaway local catalog, in the image.
- `tests/smoke_evaluations.py`: the run-evaluations flow against a fake control plane.

## The automation user's token

`run-platform-evaluations` calls the control plane as a dedicated Keycloak user,
`teehr-platform-automation`, a write member of `platform`, through a personal token (ADR-0018
in teehr-cloud-core). Runs show that user as their creator. The token is limited to
`platform` and expires after a year: repeat steps 3-5 before then (step 3 re-approves as the
same user; revoke the old token afterwards with `teehr tokens revoke`).

**1. Create the user** in the Keycloak admin console, realm `teehr`
(`https://auth.<hostname>/admin/teehr/console/`; remote: `auth.teehr.rtiamanzi.org`):

- Users → Add user: username `teehr-platform-automation`; email optional (a team mailbox
  allows password resets); **Email verified** on, so its first sign-in isn't held up; Create.
- Credentials → Set password, **Temporary** off. Keep the password in the team's password
  manager: renewing the token needs it.
- No roles or groups: its access comes from its `platform` membership.

**2. Add it to `platform`** as yourself (a `control-plane-admin` manages system projects'
members). This gives it the `platform` write role in Keycloak and Polaris:

```
teehr projects members add teehr-platform-automation -p platform --role write
teehr projects members list -p platform
```

**3. Make its token**, after step 2 (so the token carries the role), into a config directory
of its own (so the CLI doesn't use your saved token). **Whoever approves in the browser is who
the token is for**, and a browser already signed in to Keycloak as you approves as you
without asking. So first sign out of Keycloak
(`https://auth.<hostname>/realms/teehr/protocol/openid-connect/logout`) or use a fresh private
window (close any other private windows first: they share one session). When you open the
approval link, Keycloak should ask you to sign in; sign in as `teehr-platform-automation` and
finish any required action it asks for. `--api` is the URL your own
CLI uses (in `~/.config/teehr/credentials.json`); on KinD,
`https://control-plane.teehr.local.app.garden` and add `--insecure` (self-signed certificate):

```
mkdir -p ~/teehr-automation-token
TEEHR_CONFIG_DIR=~/teehr-automation-token teehr --api <control-plane API URL> auth login --name prefect-run-platform-evaluations -p platform --days 365 --no-browser
TEEHR_CONFIG_DIR=~/teehr-automation-token teehr auth status
```

`auth status` should name `teehr-platform-automation`. If it names you, the token is yours:
revoke it (`teehr tokens list`, then `teehr tokens revoke <id>`, as yourself), sign out of
Keycloak and start step 3 again. The token (`tpat_...`) is in
`~/teehr-automation-token/credentials.json`. Once approved, sign the bot out of Keycloak in
that window (or close the private window), so your browser doesn't stay signed in as it; the
token doesn't depend on that session.

**4. Store it** in the `prefect-control-plane-token` secret, then delete
`~/teehr-automation-token` (not `teehr auth logout`: that revokes the token). Remote: in `REMOTE_SECRETS`; KinD: in
`teehr-cloud-core/secrets/secrets.local.private.yaml`. Under `secrets:`:

```yaml
  prefect-control-plane-token:
    data:
      token: tpat_...
```

**5. Redeploy** the secrets and the flows (`prefect-v1-workflow-deploy`, with force): the
deployer passes the token to the deployment. Without it, the flow fails at once and names the
secret. Run `run-platform-evaluations` once by hand from the Prefect UI before turning on its
schedule.

The image's teehr-core commit is `teehrCoreVersion` in `project.garden.yml` (a var change
needs `garden deploy prefect-v1-workflow-deploy --force`).
