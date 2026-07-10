import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { auth, UserProfile } from "./api";
import { trackSignup } from "./analytics";

export interface RegisterResult {
  pending: boolean;            // true = precisa validar o código de email antes de completar
  email?: string;
  linkedCoach?: string | null;
}

interface AuthState {
  user: UserProfile | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string, role?: "player" | "coach", ref?: string | null) => Promise<RegisterResult>;
  verifyEmail: (email: string, code: string) => Promise<string | null>;
  logout: () => void;
  refreshUser: () => Promise<void>;
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

  const register = async (username: string, email: string, password: string, role: "player" | "coach" = "player", ref?: string | null): Promise<RegisterResult> => {
    const res = await auth.register(username, email, password, role, ref);
    // Verificação de email ligada: não veio token, a conta fica pendente do código.
    if (res.pending_verification) {
      return { pending: true, email: res.email, linkedCoach: res.linked_coach ?? null };
    }
    sessionStorage.setItem("ll_token", res.token!);
    const profile = await auth.me();
    setUser(profile);
    trackSignup("email");   // conversão de cadastro (sem 2FA de email)
    return { pending: false, linkedCoach: res.linked_coach ?? null };
  };

  const verifyEmail = async (email: string, code: string): Promise<string | null> => {
    const res = await auth.verifyEmail(email, code);
    sessionStorage.setItem("ll_token", res.token!);
    trackSignup("email");   // conversão de cadastro (fim do fluxo com 2FA de email)
    const profile = await auth.me();
    setUser(profile);
    return res.linked_coach ?? null;
  };

  const logout = () => {
    sessionStorage.removeItem("ll_token");
    setUser(null);
  };

  const refreshUser = async () => {
    const profile = await auth.me();
    setUser(profile);
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, verifyEmail, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
