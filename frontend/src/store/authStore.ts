import { create } from "zustand";
import { api, setAuthToken } from "@/api/client";

interface User {
  id: string;
  email: string;
  full_name: string | null;
}

interface AuthState {
  user: User | null;
  isAuthenticating: boolean;
  isInitialized: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  checkSession: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticating: false,
  isInitialized: false,
  error: null,

  checkSession: async () => {
    try {
      const user = await api.get<User>("/auth/me");
      set({ user, isInitialized: true });
    } catch {
      setAuthToken(null);
      set({ user: null, isInitialized: true });
    }
  },

  login: async (email, password) => {
    set({ isAuthenticating: true, error: null });
    try {
      const form = new URLSearchParams();
      form.set("username", email);
      form.set("password", password);
      const token = await api.postForm<{ access_token: string }>("/auth/login", form);
      setAuthToken(token.access_token);
      const user = await api.get<User>("/auth/me");
      set({ user, isAuthenticating: false });
    } catch (e) {
      set({ isAuthenticating: false, error: e instanceof Error ? e.message : "Login failed." });
      throw e;
    }
  },

  register: async (email, password, fullName) => {
    set({ isAuthenticating: true, error: null });
    try {
      await api.post("/auth/register", { email, password, full_name: fullName });
      const form = new URLSearchParams();
      form.set("username", email);
      form.set("password", password);
      const token = await api.postForm<{ access_token: string }>("/auth/login", form);
      setAuthToken(token.access_token);
      const user = await api.get<User>("/auth/me");
      set({ user, isAuthenticating: false });
    } catch (e) {
      set({ isAuthenticating: false, error: e instanceof Error ? e.message : "Registration failed." });
      throw e;
    }
  },

  logout: () => {
    setAuthToken(null);
    set({ user: null });
  },
}));
