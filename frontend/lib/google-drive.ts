const GSI_SRC = "https://accounts.google.com/gsi/client";
const DRIVE_READONLY = "https://www.googleapis.com/auth/drive.readonly";

function loadGsi(): Promise<void> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Google Drive access is only available in the browser"));
  }
  if (window.google?.accounts?.oauth2) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    const onReady = () => {
      if (window.google?.accounts?.oauth2) resolve();
      else reject(new Error("Google Drive access is not available"));
    };
    if (existing) {
      if (window.google?.accounts?.oauth2) {
        resolve();
        return;
      }
      existing.addEventListener("load", onReady, { once: true });
      existing.addEventListener("error", () => reject(new Error("Could not load Google")), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = GSI_SRC;
    script.async = true;
    script.onload = onReady;
    script.onerror = () => reject(new Error("Could not load Google"));
    document.body.appendChild(script);
  });
}

export async function requestDriveReadonlyToken(clientId: string): Promise<string> {
  await loadGsi();
  return new Promise((resolve, reject) => {
    const oauth2 = window.google?.accounts?.oauth2;
    if (!oauth2) {
      reject(new Error("Google Drive access is not available"));
      return;
    }
    let settled = false;
    const finish = (error?: Error, token?: string) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      if (token) resolve(token);
      else reject(error || new Error("Could not open Google Drive"));
    };
    const timer = window.setTimeout(() => {
      finish(new Error("Google Drive access timed out. Allow the popup, then click Import again."));
    }, 120000);
    const client = oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_READONLY,
      callback: (res) => {
        if (res.error || !res.access_token) {
          finish(
            new Error(
              res.error === "access_denied"
                ? "Drive access was cancelled. Click Import again and allow Google Drive."
                : "Could not open Google Drive. Allow Drive access, or download the folder and drop the files here.",
            ),
          );
          return;
        }
        finish(undefined, res.access_token);
      },
      error_callback: (err: { type?: string } | unknown) => {
        const kind = err && typeof err === "object" && "type" in err ? String((err as { type?: string }).type) : "";
        finish(
          new Error(
            kind === "popup_closed"
              ? "Google sign-in closed before Drive access was allowed. Click Import again."
              : "Allow the Google popup, then click Import again.",
          ),
        );
      },
    });
    client.requestAccessToken({ prompt: "consent" });
  });
}
