import { create } from "zustand";
import { api, clearTokens, setTokens } from "./api";

function hasSession() {
  if (typeof window === "undefined") return false;
  return Boolean(localStorage.getItem("dv_access") || localStorage.getItem("dv_refresh"));
}

export type Preferences = {
  language: string;
  theme: string;
  ai_privacy_mode: string;
  external_ai_enabled: boolean;
  allow_highly_sensitive_external: boolean;
  daily_briefing_enabled: boolean;
  weekly_report_enabled: boolean;
  reminder_offsets_days: number[];
  naming_style: string;
  preferred_categories: string[];
  notification_email: boolean;
  notification_in_app: boolean;
  timezone: string;
  phone_number?: string | null;
};

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  onboarding_completed: boolean;
  totp_enabled: boolean;
  preferences?: Preferences;
  health?: { score: number; notes: string[]; expiring_soon: number; total?: number };
};

type AuthState = {
  user: User | null;
  loading: boolean;
  load: () => Promise<void>;
  login: (email: string, password: string, totp?: string) => Promise<User>;
  register: (fullName: string, email: string, password: string) => Promise<void>;
  guestLogin: () => Promise<User>;
  logout: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: true,
  load: async () => {
    if (!hasSession()) {
      set({ user: null, loading: false });
      return;
    }
    try {
      const user = await api<User>("/users/me");
      set({ user, loading: false });
    } catch {
      clearTokens();
      set({ user: null, loading: false });
    }
  },
  login: async (email, password, totp) => {
    const data = await api<{ access_token: string; refresh_token: string; user: User }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password, totp_code: totp }) },
    );
    setTokens(data.access_token, data.refresh_token);
    const me = await api<User>("/users/me");
    set({ user: me, loading: false });
    return me;
  },
  guestLogin: async () => {
    const data = await api<{ access_token: string; refresh_token: string; user: User }>(
      "/auth/guest",
      { method: "POST", body: JSON.stringify({}) },
    );
    setTokens(data.access_token, data.refresh_token);
    const me = await api<User>("/users/me");
    set({ user: me, loading: false });
    return me;
  },
  register: async (fullName, email, password) => {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ full_name: fullName, email, password }),
    });
  },
  logout: () => {
    clearTokens();
    set({ user: null });
  },
}));
