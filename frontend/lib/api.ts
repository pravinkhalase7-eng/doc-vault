export const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function getTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: localStorage.getItem("dv_access"),
    refresh: localStorage.getItem("dv_refresh"),
  };
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("dv_access", access);
  localStorage.setItem("dv_refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("dv_access");
  localStorage.removeItem("dv_refresh");
}

async function refreshTokens(): Promise<boolean> {
  const { refresh } = getTokens();
  if (!refresh) return false;
  const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return false;
  }
  const json = await res.json();
  setTokens(json.data.access_token, json.data.refresh_token);
  return true;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const { access } = getTokens();
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`${API_URL}/api/v1${path}`, { ...options, headers });
  if (res.status === 401 && retry) {
    const ok = await refreshTokens();
    if (ok) return api<T>(path, options, false);
  }
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.success === false) {
    throw new ApiError(
      json.error?.code || "ERROR",
      apiErrorMessage(json),
      res.status,
    );
  }
  return json.data as T;
}

export async function apiForm<T>(path: string, body: FormData, retry = true): Promise<T> {
  return api<T>(path, { method: "POST", body }, retry);
}

export async function apiBlob(path: string, retry = true): Promise<Blob> {
  const { access } = getTokens();
  const headers = new Headers();
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`${API_URL}/api/v1${path}`, { headers });
  if (res.status === 401 && retry) {
    const ok = await refreshTokens();
    if (ok) return apiBlob(path, false);
  }
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new ApiError(
      json.error?.code || "ERROR",
      apiErrorMessage(json),
      res.status,
    );
  }
  return res.blob();
}

function apiErrorMessage(json: {
  error?: { message?: string };
  detail?: unknown;
}): string {
  if (json.error?.message) return json.error.message;
  if (typeof json.detail === "string") return json.detail;
  if (Array.isArray(json.detail)) {
    return json.detail
      .map((item: { loc?: unknown[]; msg?: string }) => {
        const loc = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== "body").join(".")
          : "";
        const msg = item.msg || "Invalid request";
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join("; ");
  }
  return "Request failed";
}
