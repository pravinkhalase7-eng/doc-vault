const DB_NAME = "docvault-share";
const STORE = "incoming";
const KEY = "latest";

type StoredFile = {
  name: string;
  type: string;
  lastModified: number;
  buffer: ArrayBuffer;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function takeSharedFiles(): Promise<File[]> {
  if (typeof indexedDB === "undefined") return [];
  try {
    const db = await openDb();
    const stored = await new Promise<StoredFile[] | undefined>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      const store = tx.objectStore(STORE);
      const get = store.get(KEY);
      get.onsuccess = () => {
        store.delete(KEY);
        resolve(get.result as StoredFile[] | undefined);
      };
      get.onerror = () => reject(get.error);
    });
    if (!stored?.length) return [];
    return stored.map(
      (item) =>
        new File([item.buffer], item.name || "shared", {
          type: item.type || "application/octet-stream",
          lastModified: item.lastModified || Date.now(),
        }),
    );
  } catch {
    return [];
  }
}
