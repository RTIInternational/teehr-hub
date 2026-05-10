#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-https://api.teehr.local.app.garden}"
KC_BASE="${KC_BASE:-https://auth.teehr.local.app.garden}"
USERNAME="${AUTH_TEST_USERNAME:-admin}"
PASSWORD="${AUTH_TEST_PASSWORD:-password}"
CLIENT_ID="${AUTH_TEST_CLIENT_ID:-teehr-frontend}"

pass() {
  echo "PASS: $1"
}

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

echo "Running auth smoke test"
echo "API_BASE=${API_BASE}"
echo "KC_BASE=${KC_BASE}"

OPENAPI_JSON="$(mktemp)"
TOKEN_JSON="$(mktemp)"
ME_JWT_JSON="$(mktemp)"
LIST_JWT_JSON="$(mktemp)"
CREATE_JSON="$(mktemp)"
ME_APIKEY_JSON="$(mktemp)"
DENY_JSON="$(mktemp)"
trap 'rm -f "$OPENAPI_JSON" "$TOKEN_JSON" "$ME_JWT_JSON" "$LIST_JWT_JSON" "$CREATE_JSON" "$ME_APIKEY_JSON" "$DENY_JSON"' EXIT

curl -ksS "${API_BASE}/openapi.json" > "$OPENAPI_JSON"
grep -q '"BearerAuth"' "$OPENAPI_JSON" || fail "OpenAPI missing BearerAuth scheme"
grep -q '"ApiKeyAuth"' "$OPENAPI_JSON" || fail "OpenAPI missing ApiKeyAuth scheme"
pass "OpenAPI includes BearerAuth and ApiKeyAuth"

curl -ksS -X POST "${KC_BASE}/realms/teehr/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password' \
  -d "client_id=${CLIENT_ID}" \
  -d "username=${USERNAME}" \
  -d "password=${PASSWORD}" > "$TOKEN_JSON"

TOKEN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("access_token", ""))' "$TOKEN_JSON")"
[[ -n "$TOKEN" ]] || fail "Failed to obtain Keycloak access token"
pass "Obtained admin access token"

ME_STATUS="$(curl -ksS -o "$ME_JWT_JSON" -w '%{http_code}' "${API_BASE}/auth/me" -H "Authorization: Bearer ${TOKEN}")"
[[ "$ME_STATUS" == "200" ]] || fail "/auth/me with JWT failed (status ${ME_STATUS})"
JWT_TYPE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("auth_type", ""))' "$ME_JWT_JSON")"
[[ "$JWT_TYPE" == "jwt" ]] || fail "/auth/me with JWT returned auth_type=${JWT_TYPE}"
pass "JWT auth works for /auth/me"

LIST_STATUS="$(curl -ksS -o "$LIST_JWT_JSON" -w '%{http_code}' "${API_BASE}/auth/api-keys" -H "Authorization: Bearer ${TOKEN}")"
[[ "$LIST_STATUS" == "200" ]] || fail "Admin JWT cannot list keys (status ${LIST_STATUS})"
pass "Admin JWT can list API keys"

KEY_NAME="smoke-test-$(date +%s)"
CREATE_STATUS="$(curl -ksS -o "$CREATE_JSON" -w '%{http_code}' -X POST "${API_BASE}/auth/api-keys" -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' -d "{\"name\":\"${KEY_NAME}\",\"scopes\":[\"read:test\"]}")"
[[ "$CREATE_STATUS" == "201" ]] || fail "Admin JWT cannot create key (status ${CREATE_STATUS})"

KEY_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("id", ""))' "$CREATE_JSON")"
API_KEY="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("api_key", ""))' "$CREATE_JSON")"
[[ -n "$KEY_ID" && -n "$API_KEY" ]] || fail "Key create response missing id or api_key"
pass "Created API key"

ME_APIKEY_STATUS="$(curl -ksS -o "$ME_APIKEY_JSON" -w '%{http_code}' "${API_BASE}/auth/me" -H "x-api-key: ${API_KEY}")"
[[ "$ME_APIKEY_STATUS" == "200" ]] || fail "/auth/me with API key failed (status ${ME_APIKEY_STATUS})"
APIKEY_TYPE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("auth_type", ""))' "$ME_APIKEY_JSON")"
[[ "$APIKEY_TYPE" == "api_key" ]] || fail "/auth/me with API key returned auth_type=${APIKEY_TYPE}"
pass "API key auth works for /auth/me"

DENY_STATUS="$(curl -ksS -o "$DENY_JSON" -w '%{http_code}' "${API_BASE}/auth/api-keys" -H "x-api-key: ${API_KEY}")"
[[ "$DENY_STATUS" == "403" ]] || fail "API key unexpectedly allowed on admin route (status ${DENY_STATUS})"
pass "API key is denied on admin-only key route"

REVOKE_STATUS="$(curl -ksS -o /dev/null -w '%{http_code}' -X DELETE "${API_BASE}/auth/api-keys/${KEY_ID}" -H "Authorization: Bearer ${TOKEN}")"
[[ "$REVOKE_STATUS" == "204" ]] || fail "Failed to revoke created key (status ${REVOKE_STATUS})"
pass "Created key revoked"

echo "All auth smoke tests passed."
