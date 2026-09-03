const CACHE = "docvault-shell-v5";
const SHARE_DB = "docvault-share";
const SHARE_STORE = "incoming";
const SHARE_KEY = "latest";

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

function openShareDb() {
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

async function stashSharedForm(request) {
  const formData = await request.formData();
  const raw = [...formData.getAll("files"), ...formData.getAll("file")];
  const payloads = [];
  for (const item of raw) {
    if (!item || typeof item === "string") continue;
    payloads.push({
      name: item.name || "shared",
      type: item.type || "application/octet-stream",
      lastModified: item.lastModified || Date.now(),
      buffer: await item.arrayBuffer(),
    });
  }
  if (!payloads.length) {
    const title = String(formData.get("title") || "").trim();
    const text = String(formData.get("text") || "").trim();
    const sharedUrl = String(formData.get("url") || "").trim();
    const body = [title, text, sharedUrl].filter(Boolean).join("\n");
    if (body) {
      payloads.push({
        name: `${title || "shared-note"}.txt`,
        type: "text/plain",
        lastModified: Date.now(),
        buffer: new TextEncoder().encode(body).buffer,
      });
    }
  }
  if (!payloads.length) return;
  const db = await openShareDb();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(SHARE_STORE, "readwrite");
    tx.objectStore(SHARE_STORE).put(payloads, SHARE_KEY);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

self.addEventListener("push", (event) => {
  let data = { title: "DocVault", body: "You have a reminder.", url: "/notifications" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch {
    if (event.data) data.body = event.data.text();
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "DocVault", {
      body: data.body || "You have a reminder.",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      data: { url: data.url || "/notifications" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/notifications";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate?.(url);
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method === "POST" && url.pathname === "/share-target") {
    event.respondWith(
      (async () => {
        try {
          await stashSharedForm(event.request);
        } catch (err) {
          console.error("share_target_failed", err);
        }
        return Response.redirect(new URL("/documents/upload?share=1", url.origin), 303);
      })(),
    );
    return;
  }
  if (event.request.method !== "GET" || url.pathname.startsWith("/api")) return;
  const accept = event.request.headers.get("accept") || "";
  const navigate =
    event.request.mode === "navigate" ||
    accept.includes("text/html") ||
    accept.includes("text/x-component") ||
    url.searchParams.has("_rsc");
  if (navigate) {
    event.respondWith(fetch(event.request));
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(event.request)),
  );
});
