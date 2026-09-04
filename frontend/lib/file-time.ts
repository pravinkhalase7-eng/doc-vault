function parseTime(iso?: string | null): Date | null {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatFileTime(iso?: string | null): string {
  const date = parseTime(iso);
  if (!date) return "";
  return date.toLocaleString([], {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function fileTimestamps(created?: string | null, updated?: string | null): string {
  const uploaded = formatFileTime(created);
  const createdAt = parseTime(created);
  const updatedAt = parseTime(updated);
  const edited =
    createdAt && updatedAt && Math.abs(updatedAt.getTime() - createdAt.getTime()) >= 60_000
      ? formatFileTime(updated)
      : "";
  if (uploaded && edited) return `Added ${uploaded} · Edited ${edited}`;
  if (uploaded) return `Added ${uploaded}`;
  if (edited) return `Edited ${edited}`;
  return "";
}