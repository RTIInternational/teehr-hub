ARG KEYCLOAK_VERSION=26.6.1

FROM quay.io/keycloak/keycloak:${KEYCLOAK_VERSION} as builder

ENV KC_DB=postgres
ENV KC_HEALTH_ENABLED=true

COPY themes/teehr /opt/keycloak/themes/teehr

RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:${KEYCLOAK_VERSION}

COPY --from=builder /opt/keycloak/ /opt/keycloak/
