import React, { useState, useEffect, useMemo } from 'react';
import { AuthContext } from './AuthContext';
import {
  initKeycloak,
  getKeycloak,
  parseRoles,
  ensureFreshToken,
  login,
  logout,
  signup,
} from './keycloak';

export const AuthProvider = ({ children }: React.PropsWithChildren) => {
  const [ready, setReady] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [roles, setRoles] = useState<string[]>([]);

  useEffect(() => {
    let mounted = true;

    const boot = async () => {
      try {
        const isAuthenticated = await initKeycloak();
        if (!mounted) {
          return;
        }

        const kc = getKeycloak();

        setAuthenticated(Boolean(isAuthenticated));
        setUsername(kc.tokenParsed?.preferred_username || null);
        setRoles(parseRoles());

        kc.onAuthSuccess = () => {
          setAuthenticated(true);
          setUsername(kc.tokenParsed?.preferred_username || null);
          setRoles(parseRoles());
        };
        kc.onAuthLogout = () => {
          setAuthenticated(false);
          setUsername(null);
          setRoles([]);
        };
        kc.onTokenExpired = async () => {
          const token = await ensureFreshToken();
          if (!token) {
            setAuthenticated(false);
            setUsername(null);
            setRoles([]);
          }
        };
      } catch (error) {
        console.error('Failed to initialize Keycloak:', error);
      } finally {
        if (mounted) {
          setReady(true);
        }
      }
    };

    boot();

    return () => {
      mounted = false;
    };
  }, []);

  const value = useMemo(
    () => ({
      ready,
      authenticated,
      username,
      roles,
      login,
      signup,
      logout,
    }),
    [authenticated, ready, roles, username]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
