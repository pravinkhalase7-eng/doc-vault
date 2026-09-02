import { FileText, Image as ImageIcon, type LucideIcon } from "lucide-react";

export function fileKind(doc: { mime_type?: string; original_filename?: string }): {
  label: string;
  icon: LucideIcon;
  tone: string;
} {
  const mime = (doc.mime_type || "").toLowerCase();
  const name = (doc.original_filename || "").toLowerCase();
  if (mime.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|tiff?|heic|heif|avif)$/.test(name)) {
    return { label: "Photo", icon: ImageIcon, tone: "bg-primary/10 text-primary" };
  }
  if (mime.includes("pdf") || name.endsWith(".pdf")) {
    return { label: "PDF", icon: FileText, tone: "bg-muted text-foreground" };
  }
  if (mime.includes("word") || mime.includes("msword") || /\.(docx?|odt|rtf)$/.test(name)) {
    return { label: "Word", icon: FileText, tone: "bg-muted text-foreground" };
  }
  if (mime.includes("sheet") || mime.includes("excel") || /\.(xlsx?|csv)$/.test(name)) {
    return { label: "Spreadsheet", icon: FileText, tone: "bg-muted text-foreground" };
  }
  return { label: "File", icon: FileText, tone: "bg-muted text-muted-foreground" };
}
