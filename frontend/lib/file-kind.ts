import { FileText, Image as ImageIcon, type LucideIcon } from "lucide-react";

export type StoredKind = "photo" | "pdf" | "other";

export function fileKind(doc: { mime_type?: string; original_filename?: string }): {
  label: string;
  icon: LucideIcon;
  tone: string;
  group: StoredKind;
} {
  const mime = (doc.mime_type || "").toLowerCase();
  const name = (doc.original_filename || "").toLowerCase();
  if (mime.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|tiff?|heic|heif|avif)$/.test(name)) {
    return { label: "Photo", icon: ImageIcon, tone: "bg-primary/10 text-primary", group: "photo" };
  }
  if (mime.includes("pdf") || name.endsWith(".pdf")) {
    return { label: "PDF", icon: FileText, tone: "bg-muted text-foreground", group: "pdf" };
  }
  if (mime.includes("word") || mime.includes("msword") || /\.(docx?|odt|rtf)$/.test(name)) {
    return { label: "Word", icon: FileText, tone: "bg-muted text-foreground", group: "other" };
  }
  if (mime.includes("sheet") || mime.includes("excel") || /\.(xlsx?|csv)$/.test(name)) {
    return { label: "Spreadsheet", icon: FileText, tone: "bg-muted text-foreground", group: "other" };
  }
  return { label: "File", icon: FileText, tone: "bg-muted text-muted-foreground", group: "other" };
}

export function storedKind(doc: { mime_type?: string; original_filename?: string }): StoredKind {
  return fileKind(doc).group;
}
