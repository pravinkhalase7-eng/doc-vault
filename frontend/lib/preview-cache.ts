import { apiBlob } from "@/lib/api";

type Entry = { url?: string; promise?: Promise<string> };

const cache = new Map<string, Entry>();
const MAX = 48;

function prune() {
  if (cache.size <= MAX) return;
  const keys = [...cache.keys()];
  const extra = keys.slice(0, cache.size - MAX);
  for (const key of extra) {
    const hit = cache.get(key);
    if (hit?.url) URL.revokeObjectURL(hit.url);
    cache.delete(key);
  }
}

export function cachedBlobUrl(path: string): string {
  return cache.get(path)?.url || "";
}

export function loadBlobUrl(path: string): Promise<string> {
  const hit = cache.get(path);
  if (hit?.url) return Promise.resolve(hit.url);
  if (hit?.promise) return hit.promise;
  const promise = apiBlob(path)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      cache.set(path, { url });
      prune();
      return url;
    })
    .catch((err) => {
      cache.delete(path);
      throw err;
    });
  cache.set(path, { promise });
  return promise;
}

export function prefetchBlobs(paths: string[]) {
  for (const path of paths) {
    void loadBlobUrl(path).catch(() => undefined);
  }
}

export function prefetchReelDocs(
  docs: Array<{ id: string; mime_type?: string; original_filename?: string }>,
) {
  for (const doc of docs) {
    const video = (doc.mime_type || "").startsWith("video/") || /\.(mp4|mov|webm|m4v)$/i.test(doc.original_filename || "");
    prefetchBlobs([
      `/documents/${doc.id}/thumbnail`,
      video ? `/documents/${doc.id}/preview` : `/documents/${doc.id}/reel-image`,
    ]);
  }
}
