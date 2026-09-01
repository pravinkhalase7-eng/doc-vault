const likesKey = (userId?: string) => `dv_reel_likes_${userId || "guest"}`;
const savesKey = (userId?: string) => `dv_reel_saves_${userId || "guest"}`;

function readIds(key: string): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(key);
    const list = raw ? (JSON.parse(raw) as string[]) : [];
    return new Set(Array.isArray(list) ? list : []);
  } catch {
    return new Set();
  }
}

function writeIds(key: string, ids: Set<string>) {
  localStorage.setItem(key, JSON.stringify([...ids]));
}

export function loadReelLikes(userId?: string) {
  return readIds(likesKey(userId));
}

export function loadReelSaves(userId?: string) {
  return readIds(savesKey(userId));
}

export function toggleReelLike(id: string, userId?: string) {
  const ids = readIds(likesKey(userId));
  if (ids.has(id)) ids.delete(id);
  else ids.add(id);
  writeIds(likesKey(userId), ids);
  return ids;
}

export function toggleReelSave(id: string, userId?: string) {
  const ids = readIds(savesKey(userId));
  if (ids.has(id)) ids.delete(id);
  else ids.add(id);
  writeIds(savesKey(userId), ids);
  return ids;
}
