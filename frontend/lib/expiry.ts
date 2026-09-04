export type ExpiryKind = "expired" | "today" | "soon" | "later";

export function daysUntilExpiry(iso?: string | null, now = new Date()): number | null {
  if (!iso) return null;
  const expiry = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(expiry.getTime())) return null;
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((expiry.getTime() - start.getTime()) / 86_400_000);
}

export function expiryKind(iso?: string | null, now = new Date()): ExpiryKind | null {
  const days = daysUntilExpiry(iso, now);
  if (days === null) return null;
  if (days < 0) return "expired";
  if (days === 0) return "today";
  if (days <= 30) return "soon";
  return "later";
}

export function expiryLabel(iso?: string | null, now = new Date()): string {
  const days = daysUntilExpiry(iso, now);
  if (days === null) return "";
  if (days < 0) {
    const ago = Math.abs(days);
    return ago === 1 ? "Expired yesterday" : `Expired ${ago} days ago`;
  }
  if (days === 0) return "Expires today";
  if (days === 1) return "Expires tomorrow";
  if (days <= 30) return `Expires in ${days} days`;
  const date = new Date(`${iso!.slice(0, 10)}T00:00:00`);
  return `Expires ${date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}`;
}

export function reminderFireAt(iso: string, now = new Date()): string {
  const expiry = new Date(`${iso.slice(0, 10)}T09:00:00`);
  const sevenBefore = new Date(expiry);
  sevenBefore.setDate(sevenBefore.getDate() - 7);
  if (sevenBefore.getTime() > now.getTime() + 60_000) return sevenBefore.toISOString();
  return new Date(now.getTime() + 60 * 60 * 1000).toISOString();
}

export function trashDaysLeft(trashedAt?: string | null, now = new Date()): number {
  if (!trashedAt) return 30;
  const start = Date.parse(trashedAt);
  if (Number.isNaN(start)) return 30;
  return Math.max(0, Math.ceil(30 - (now.getTime() - start) / 86_400_000));
}
