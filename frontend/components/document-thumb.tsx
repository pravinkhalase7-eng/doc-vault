"use client";

import { useEffect, useState } from "react";
import { fileKind } from "@/lib/file-kind";
import { cachedBlobUrl, loadBlobUrl } from "@/lib/preview-cache";
import { cn } from "@/lib/utils";

export function DocumentThumb({
  id,
  title,
  mimeType,
  filename,
  className,
}: {
  id: string;
  title?: string;
  mimeType?: string;
  filename?: string;
  className?: string;
}) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  const kind = fileKind({ mime_type: mimeType, original_filename: filename });
  const Icon = kind.icon;

  useEffect(() => {
    const paths = [`/documents/${id}/thumbnail`, `/documents/${id}/reel-image`];
    const cached = paths.map(cachedBlobUrl).find(Boolean) || "";
    setUrl(cached);
    setFailed(false);
    if (cached) return;
    let alive = true;
    (async () => {
      for (const path of paths) {
        try {
          const next = await loadBlobUrl(path);
          if (alive) {
            setUrl(next);
            return;
          }
        } catch {
          continue;
        }
      }
      if (alive) setFailed(true);
    })();
    return () => {
      alive = false;
    };
  }, [id]);

  if (url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
        alt={title || ""}
        className={cn("object-cover", className)}
        onError={() => {
          setFailed(true);
          setUrl("");
        }}
      />
    );
  }

  return (
    <span className={cn("flex items-center justify-center", kind.tone, className)}>
      <Icon className="size-6 text-current opacity-80" />
    </span>
  );
}