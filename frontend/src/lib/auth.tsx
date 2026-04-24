import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { auth, UserProfile } from "./api";

interface AuthState {
  user: UserProfile | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = sessionStorage.getItem("ll_token");
    if (!t) {
      setIsLoading(false);
      return;
    }
    auth
      .me()
      .then(setUser)
      .catch(() => sessionStorage.removeItem("ll_token"))
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await auth.login(email, password);
    sessionStorage.setItem("ll_token", res.token);
    const profile = await auth.me();
    setUser(profile);
  };

  const register = async (username: string, email: string, password: string) => {
    const res = await auth.register(username, email, password);
    sessionStorage.setItem("ll_token", res.token);
    const profile = await auth.me();
    setUser(profile);
  };

  const logout = () => {
    sessionStorage.removeItem("ll_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
