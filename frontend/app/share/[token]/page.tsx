"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Download } from "lucide-react";

type Shared = {
  title: string | null;
  original_filename: string | null;
  mime_type: string | null;
  download_allowed: boolean;
};

function ShareView() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<Shared | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`/api/v1/sharing/links/${token}`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok || json.success === false) {
          throw new Error(json.error?.message || "This link is not available");
        }
        setData(json.data);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "This link is not available"));
  }, [token]);

  if (error) {
    return <p className="p-8 text-center text-sm text-muted-foreground">{error}</p>;
  }
  if (!data) {
    return <p className="p-8 text-center text-sm text-muted-foreground">Opening shared file…</p>;
  }

  const fileUrl = `/api/v1/sharing/links/${token}/file`;
  const isImage = Boolean(data.mime_type?.startsWith("image/"));

  return (
    <div className="flex h-dvh min-h-0 flex-col bg-black">
      <div className="flex items-center gap-2 border-b border-white/10 bg-background px-4 py-3">
        <h1 className="min-w-0 flex-1 truncate text-base font-medium">{data.title || "Shared file"}</h1>
        {data.download_allowed && (
          <a
            href={`${fileUrl}?download=1`}
            download={data.original_filename || undefined}
            className="inline-flex size-7 items-center justify-center rounded-full hover:bg-muted"
          >
            <Download className="size-4" />
            <span className="sr-only">Download</span>
          </a>
        )}
      </div>
      <div className="min-h-0 flex-1">
        {isImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={fileUrl} alt={data.title || "Shared file"} className="h-full w-full object-contain" />
        ) : (
          <iframe title={data.title || "Shared file"} className="h-full w-full border-0 bg-neutral-900" src={fileUrl} />
        )}
      </div>
    </div>
  );
}

export default function SharePage() {
  return (
    <Suspense fallback={<p className="p-8 text-center text-sm text-muted-foreground">Opening shared file…</p>}>
      <ShareView />
    </Suspense>
  );
}
