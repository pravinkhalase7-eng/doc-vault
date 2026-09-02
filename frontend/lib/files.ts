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

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.left = "-9999px";
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand("copy");
    field.remove();
    return copied;
  }
}

export async function shareDocument(id: string, title: string, filename: string) {
  if (window.isSecureContext && typeof navigator.canShare === "function") {
    try {
      const blob = await apiBlob(`/documents/${id}/download`);
      const file = new File([blob], filename || title || "document", {
        type: blob.type || "application/octet-stream",
      });
      if (navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title });
        return;
      }
    } catch (err) {
      if (isShareCancel(err)) return;
    }
  }

  const created = await api<{ token: string }>("/sharing/links", {
    method: "POST",
    body: JSON.stringify({ document_id: id, download_allowed: true, expires_hours: 72 }),
  });
  const url = `${window.location.origin}/share/${created.token}`;
  if (window.isSecureContext && typeof navigator.share === "function") {
    try {
      await navigator.share({ title, url });
      return;
    } catch (err) {
      if (isShareCancel(err)) return;
    }
  }
  if (await copyText(url)) {
    toast.success("Share link copied");
    return;
  }
  toast.message("Share link", { description: url });
}

export function isShareCancel(err: unknown) {
  return err instanceof Error && err.name === "AbortError";
}
