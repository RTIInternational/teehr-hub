import { createContext } from 'react';

type AuthContextValue = {
  ready: boolean;
  authenticated: boolean;
  username: string | null;
  roles: string[];
  login: (options: object) => Promise<void>;
  signup: (redirectUri: string) => Promise<void>;
  logout: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
