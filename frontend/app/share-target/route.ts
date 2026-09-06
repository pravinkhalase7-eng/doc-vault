import { NextResponse } from "next/server";

/**
 * Fallback when the service worker is not controlling this client.
 * The SW normally stashes shared multipart into IndexedDB; here we parse the
 * POST body and return a tiny HTML page that writes the same IndexedDB key
 * then redirects to upload — matching sw.js stashSharedForm behavior.
 */
export async function GET(request: Request) {
  return NextResponse.redirect(new URL("/documents/upload", request.url), 303);
}

function bytesToBase64(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64");
}

type StashPayload = {
  name: string;
  type: string;
  lastModified: number;
  bufferBase64: string;
};

async function payloadsFromForm(formData: FormData): Promise<StashPayload[]> {
  const raw = [...formData.getAll("files"), ...formData.getAll("file")];
  const payloads: StashPayload[] = [];
  for (const item of raw) {
    if (!item || typeof item === "string") continue;
    const file = item as File;
    const buf = new Uint8Array(await file.arrayBuffer());
    payloads.push({
      name: file.name || "shared",
      type: file.type || "application/octet-stream",
      lastModified: file.lastModified || Date.now(),
      bufferBase64: bytesToBase64(buf),
    });
  }
  if (!payloads.length) {
    const title = String(formData.get("title") || "").trim();
    const text = String(formData.get("text") || "").trim();
    const sharedUrl = String(formData.get("url") || "").trim();
    const body = [title, text, sharedUrl].filter(Boolean).join("\n");
    if (body) {
      const encoded = new TextEncoder().encode(body);
      payloads.push({
        name: `${title || "shared-note"}.txt`,
        type: "text/plain",
        lastModified: Date.now(),
        bufferBase64: bytesToBase64(encoded),
      });
    }
  }
  return payloads;
}

export async function POST(request: Request) {
  const uploadUrl = new URL("/documents/upload?share=1", request.url).toString();
  let payloads: StashPayload[] = [];
  try {
    const formData = await request.formData();
    payloads = await payloadsFromForm(formData);
  } catch {
    return NextResponse.redirect(uploadUrl, 303);
  }

  if (!payloads.length) {
    return NextResponse.redirect(uploadUrl, 303);
  }

  // Keep payload in a script JSON literal; client reconstructs ArrayBuffers for IndexedDB.
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Saving shared files…</title>
</head>
<body>
  <p>Saving shared files…</p>
  <script>
    const SHARE_DB = "docvault-share";
    const SHARE_STORE = "incoming";
    const SHARE_KEY = "latest";
    const REDIRECT = ${JSON.stringify(uploadUrl)};
    const encoded = ${JSON.stringify(payloads)};

    function b64ToBuffer(b64) {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return bytes.buffer;
    }

    function openDb() {
      return new Promise((resolve, reject) => {
        const req = indexedDB.open(SHARE_DB, 1);
        req.onupgradeneeded = () => {
          if (!req.result.objectStoreNames.contains(SHARE_STORE)) {
            req.result.createObjectStore(SHARE_STORE);
          }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    }

    (async () => {
      try {
        const payloads = encoded.map((item) => ({
          name: item.name,
          type: item.type,
          lastModified: item.lastModified,
          buffer: b64ToBuffer(item.bufferBase64),
        }));
        const db = await openDb();
        await new Promise((resolve, reject) => {
          const tx = db.transaction(SHARE_STORE, "readwrite");
          tx.objectStore(SHARE_STORE).put(payloads, SHARE_KEY);
          tx.oncomplete = resolve;
          tx.onerror = () => reject(tx.error);
        });
      } catch (err) {
        console.error("share_target_fallback_failed", err);
      }
      location.replace(REDIRECT);
    })();
  </script>
</body>
</html>`;

  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}
