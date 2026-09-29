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
    const client = oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_READONLY,
      callback: (res) => {
        if (res.error || !res.access_token) {
          reject(
            new Error(
              res.error === "access_denied"
                ? "Drive access was cancelled"
                : "Could not open Google Drive. Allow Drive access, or download the folder and drop the files here.",
            ),
          );
          return;
        }
        resolve(res.access_token);
      },
    });
    client.requestAccessToken();
  });
}
