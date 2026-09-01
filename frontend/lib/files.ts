import { toast } from "sonner";
import { api, apiBlob } from "@/lib/api";

export async function downloadDocument(id: string, filename: string) {
  const blob = await apiBlob(`/documents/${id}/download`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "document";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function shareDocument(id: string, title: string, filename: string) {
  const blob = await apiBlob(`/documents/${id}/download`);
  const file = new File([blob], filename || title || "document", {
    type: blob.type || "application/octet-stream",
  });
  if (typeof navigator.canShare === "function" && navigator.canShare({ files: [file] })) {
    await navigator.share({ files: [file], title });
    return;
  }
  const created = await api<{ token: string }>("/sharing/links", {
    method: "POST",
    body: JSON.stringify({ document_id: id, download_allowed: true, expires_hours: 72 }),
  });
  const url = `${window.location.origin}/share/${created.token}`;
  if (typeof navigator.share === "function") {
    await navigator.share({ title, url });
    return;
  }
  await navigator.clipboard.writeText(url);
  toast.success("Share link copied");
}

export function isShareCancel(err: unknown) {
  return err instanceof Error && err.name === "AbortError";
}
