# Keycloak Email Verification with Gmail SMTP

This repo can bootstrap Keycloak SMTP settings from Kubernetes secrets via keycloak-config-cli.

## Why Gmail needs special setup

Google does not allow normal account passwords for SMTP in this use case.
Use a Google App Password instead.

## 1) Prepare Gmail account

1. Enable 2-Step Verification on the Gmail account.
2. Create an App Password in Google Account Security.
3. Copy the 16-character app password (no spaces).

Recommended: use a dedicated mailbox for platform emails, for example `teehr-notify@...`.

## 2) Set SMTP keys in secrets

Update `keycloak-secrets` in:
- `secrets/secrets.local.yaml`
- `secrets/secrets.remote.yaml`

For local development, use the private overlay pattern so sensitive values are not committed:

1. Copy `secrets/secrets.local.private.yaml.example` to `secrets/secrets.local.private.yaml`.
2. Put real sensitive values in `secrets/secrets.local.private.yaml`.
3. Keep placeholders in `secrets/secrets.local.yaml`.

The secrets deploy action now includes an optional varfile:
- `secrets.${environment.name}.private.yaml` (optional)

That means Garden merges the private values automatically, and you can continue using normal commands like `garden deploy`.

Required secret keys:
- `smtp-from`: sender address shown to users
- `smtp-username`: Gmail address
- `smtp-password`: Gmail app password

Optional but recommended:
- `smtp-from-display-name`
- `smtp-reply-to`
- `smtp-reply-to-display-name`

## 3) Bootstrap wiring in this repo

Already wired:
- Non-sensitive SMTP settings (`host`, `port`, display names, TLS flags) are rendered into the `keycloak-realm-bootstrap` ConfigMap.
- SMTP credentials and addresses come from `keycloak-secrets` into bootstrap job env.
- Realm import sets `verifyEmail: true` and configures `smtpServer` from env vars.

Files:
- `keycloak-bootstrap/manifests/bootstrap-job.yaml`
- `keycloak-bootstrap/manifests/realm-configmap.yaml.tpl`

## 4) Deploy changes

Run:

```bash
garden deploy --env local --force secrets keycloak-realm-config keycloak-bootstrap
```

## 5) Validate in Keycloak

1. Register a new user in the frontend flow.
2. Confirm user receives verification email.
3. Verify login behavior requires verified email.

Optional admin test in Keycloak UI:
- Realm Settings -> Email -> Test connection.

## Notes for production

- Gmail send limits are low for production-scale traffic.
- For long-term production use, prefer SES, SendGrid, or Mailgun.
- Keep app password only in secrets, never in ConfigMaps or committed plaintext.
