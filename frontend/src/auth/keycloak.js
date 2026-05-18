import Keycloak from 'keycloak-js';

const keycloakConfig = {
  url: import.meta.env.VITE_KEYCLOAK_URL || 'https://auth.teehr.local.app.garden',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'teehr',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'teehr-frontend',
};

const keycloak = new Keycloak(keycloakConfig);
let initPromise;

export const initKeycloak = async () => {
  if (!initPromise) {
    initPromise = keycloak.init({
      onLoad: 'check-sso',
      pkceMethod: 'S256',
      silentCheckSsoFallback: false,
    });
  }
  return initPromise;
};

export const getKeycloak = () => keycloak;

export const login = (options = {}) => keycloak.login(options);

export const signup = (redirectUri) =>
  keycloak.login({
    action: 'register',
    ...(redirectUri ? { redirectUri } : {}),
  });

export const logout = () => keycloak.logout({ redirectUri: window.location.origin });

export const ensureFreshToken = async () => {
  if (!keycloak.authenticated && !keycloak.token) {
    return null;
  }

  try {
    await keycloak.updateToken(30);
    return keycloak.token || null;
  } catch {
    // If refresh fails but a token is still present, keep using it.
    return keycloak.token || null;
  }
};

export const parseRoles = () => {
  if (!keycloak.tokenParsed) {
    return [];
  }
  return keycloak.tokenParsed.realm_access?.roles || [];
};
