apiVersion: v1
kind: ConfigMap
metadata:
  name: keycloak-realm-bootstrap
  labels:
    app: keycloak-bootstrap
data:
  teehr-realm.json: |
    {
      "realm": "teehr",
      "enabled": true,
      "loginTheme": "teehr",
      "registrationAllowed": true,
      "loginWithEmailAllowed": true,
      "duplicateEmailsAllowed": false,
      "resetPasswordAllowed": true,
      "verifyEmail": true,
      "smtpServer": {
        "host": "$(env:SMTP_HOST)",
        "port": "$(env:SMTP_PORT)",
        "from": "$(env:SMTP_FROM)",
        "fromDisplayName": "$(env:SMTP_FROM_DISPLAY_NAME)",
        "replyTo": "$(env:SMTP_REPLY_TO)",
        "replyToDisplayName": "$(env:SMTP_REPLY_TO_DISPLAY_NAME)",
        "auth": "true",
        "user": "$(env:SMTP_USERNAME)",
        "password": "$(env:SMTP_PASSWORD)",
        "starttls": "$(env:SMTP_STARTTLS)",
        "ssl": "$(env:SMTP_SSL)"
      },
      "roles": {
        "realm": [
          { "name": "admin" },
          { "name": "basic-user" },
          { "name": "jupyter-user" },
          { "name": "iceberg-user" }
        ]
      },
      "groups": [
        {
          "name": "basic-user",
          "realmRoles": ["basic-user"]
        },
        {
          "name": "jupyter-user",
          "realmRoles": ["jupyter-user"]
        },
        {
          "name": "jupyter-admin",
          "realmRoles": ["jupyter-user"]
        },
        {
          "name": "iceberg-user",
          "realmRoles": ["iceberg-user"]
        },
        {
          "name": "key-management-admin",
          "realmRoles": ["admin"]
        },
        {
          "name": "prefect-admin",
          "realmRoles": ["admin"]
        },
        {
          "name": "webapi-admin",
          "realmRoles": ["admin"],
          "clientRoles": {
            "realm-management": [
              "manage-users",
              "query-users",
              "view-users",
              "query-groups",
              "view-realm"
            ]
          }
        }
      ],
      "defaultGroups": [
        "/basic-user"
      ],
      "clients": [
        {
          "clientId": "teehr-frontend",
          "enabled": true,
          "protocol": "openid-connect",
          "publicClient": true,
          "redirectUris": [
            "https://dashboards.${var.hostname}/*",
            "https://api.${var.hostname}/docs/oauth2-redirect"
          ],
          "webOrigins": [
            "https://dashboards.${var.hostname}",
            "https://api.${var.hostname}"
          ],
          "attributes": {
            "pkce.code.challenge.method": "S256"
          }
        },
        {
          "clientId": "teehr-api",
          "enabled": true,
          "protocol": "openid-connect",
          "publicClient": false,
          "serviceAccountsEnabled": true,
          "secret": "$(env:TEEHR_API_CLIENT_SECRET)"
        },
        {
          "clientId": "jupyterhub",
          "enabled": true,
          "protocol": "openid-connect",
          "publicClient": false,
          "secret": "$(env:JUPYTERHUB_CLIENT_SECRET)",
          "attributes": {
            "post.logout.redirect.uris": "https://hub.${var.hostname}"
          },
          "protocolMappers": [
            {
              "name": "groups",
              "protocol": "openid-connect",
              "protocolMapper": "oidc-group-membership-mapper",
              "consentRequired": false,
              "config": {
                "full.path": "false",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
                "claim.name": "groups"
              }
            }
          ],
          "redirectUris": [
            "https://hub.${var.hostname}/hub/oauth_callback"
          ],
          "webOrigins": [
            "https://hub.${var.hostname}"
          ]
        },
        {
          "clientId": "prefect-oauth2-proxy",
          "enabled": true,
          "protocol": "openid-connect",
          "publicClient": false,
          "secret": "$(env:PREFECT_OAUTH2_CLIENT_SECRET)",
          "attributes": {
            "post.logout.redirect.uris": "https://prefect.${var.hostname}/*"
          },
          "protocolMappers": [
            {
              "name": "groups",
              "protocol": "openid-connect",
              "protocolMapper": "oidc-group-membership-mapper",
              "consentRequired": false,
              "config": {
                "full.path": "false",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
                "claim.name": "groups"
              }
            }
          ],
          "redirectUris": [
            "https://prefect.${var.hostname}/oauth2/callback"
          ],
          "webOrigins": [
            "https://prefect.${var.hostname}"
          ]
        }
      ]
    }
