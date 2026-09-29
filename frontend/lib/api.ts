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

export async function apiFormWithProgress<T>(
  path: string,
  body: FormData,
  onProgress: (percent: number) => void,
  retry = true,
): Promise<T> {
  const { access } = getTokens();
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/v1${path}`);
    if (access) xhr.setRequestHeader("Authorization", `Bearer ${access}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      void (async () => {
        if (xhr.status === 401 && retry) {
          const ok = await refreshTokens();
          if (ok) {
            try {
              resolve(await apiFormWithProgress<T>(path, body, onProgress, false));
            } catch (err) {
              reject(err);
            }
            return;
          }
        }
        let json: { success?: boolean; data?: T; error?: { code?: string; message?: string } } = {};
        try {
          json = JSON.parse(xhr.responseText || "{}");
        } catch {
          json = {};
        }
        if (xhr.status < 200 || xhr.status >= 300 || json.success === false) {
          reject(
            new ApiError(
              json.error?.code || "ERROR",
              apiErrorMessage(json),
              xhr.status,
            ),
          );
          return;
        }
        resolve(json.data as T);
      })();
    };
    xhr.onerror = () => reject(new ApiError("ERROR", "Upload failed", 0));
    xhr.send(body);
  });
}

export async function apiNdjson(
  path: string,
  body: unknown,
  onEvent: (event: Record<string, unknown>) => void,
  retry = true,
): Promise<Record<string, unknown>> {
  const { access } = getTokens();
  const headers = new Headers({ "Content-Type": "application/json", Accept: "application/x-ndjson" });
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (res.status === 401 && retry) {
    const ok = await refreshTokens();
    if (ok) return apiNdjson(path, body, onEvent, false);
  }
  const contentType = res.headers.get("content-type") || "";
  if (!res.ok || !contentType.includes("ndjson")) {
    const json = await res.json().catch(() => ({}));
    throw new ApiError(
      json.error?.code || "ERROR",
      apiErrorMessage(json),
      res.status,
    );
  }
  if (!res.body) throw new ApiError("ERROR", "Upload failed", res.status);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneEvent: Record<string, unknown> | null = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const parsed = parseNdjsonLine(line, onEvent);
      if (parsed?.type === "done") doneEvent = parsed;
    }
  }
  if (buffer.trim()) {
    const parsed = parseNdjsonLine(buffer, onEvent);
    if (parsed?.type === "done") doneEvent = parsed;
  }
  if (!doneEvent) throw new ApiError("ERROR", "Upload failed", 500);
  return doneEvent;
}

function parseNdjsonLine(
  line: string,
  onEvent: (event: Record<string, unknown>) => void,
): Record<string, unknown> | null {
  const raw = line.trim();
  if (!raw) return null;
  const event = JSON.parse(raw) as Record<string, unknown>;
  if (event.type === "error") {
    throw new ApiError(String(event.code || "ERROR"), String(event.message || "Request failed"), 400);
  }
  onEvent(event);
  return event;
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

export async function apiBlobPost(path: string, body: unknown, retry = true): Promise<Blob> {
  const { access } = getTokens();
  const headers = new Headers({ "Content-Type": "application/json" });
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (res.status === 401 && retry) {
    const ok = await refreshTokens();
    if (ok) return apiBlobPost(path, body, false);
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
