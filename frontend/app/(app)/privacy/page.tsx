"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";

type Center = {
  private_ai: boolean;
  cloud_ai: boolean;
  privacy_mode: string;
  documents_processed: number;
  external_ai_requests: number;
  highly_sensitive_external: number;
  ai_access_today: number;
};

export default function PrivacyPage() {
  const { user, load } = useAuth();
  const [center, setCenter] = useState<Center | null>(null);
  const [activity, setActivity] = useState<Array<Record<string, unknown>>>([]);

  async function refresh() {
    setCenter(await api<Center>("/privacy/center"));
    setActivity(await api("/privacy/activity"));
  }
  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <p className="text-sm text-muted-foreground">Private AI</p>
        <h1 className="text-3xl">Privacy Center</h1>
      </div>
      {center && (
        <div className="grid gap-4 md:grid-cols-3">
          <Stat label="Private AI" value="ON" />
          <Stat label="Cloud AI" value={center.cloud_ai ? "ON" : "OFF"} />
          <Stat label="Documents processed" value={String(center.documents_processed)} />
          <Stat label="External AI requests" value={String(center.external_ai_requests)} />
          <Stat label="Highly sensitive sent externally" value={String(center.highly_sensitive_external)} />
          <Stat label="AI access today" value={String(center.ai_access_today)} />
        </div>
      )}
      <div className="rounded-2xl border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl">Cloud AI (Gemini)</h2>
            <p className="text-sm text-muted-foreground">
              Off by default. Originals are never sent. Highly sensitive types stay local.
            </p>
          </div>
          <Switch
            checked={Boolean(user?.preferences?.external_ai_enabled)}
            onCheckedChange={async (checked) => {
              await api("/users/me/preferences", {
                method: "PATCH",
                body: JSON.stringify({
                  external_ai_enabled: checked,
                  ai_privacy_mode: checked ? "CLOUD" : "PRIVATE",
                }),
              });
              await load();
              refresh();
            }}
          />
        </div>
      </div>
      <div className="flex gap-3">
        <Link href="/privacy" className="rounded-full border px-4 py-2 text-sm">
          View AI Activity
        </Link>
        <Button
          variant="outline"
          className="rounded-full"
          onClick={async () => {
            await api("/privacy/ai-data", { method: "DELETE" });
            toast.success("AI data deleted. Original documents were kept.");
            refresh();
          }}
        >
          Delete AI Data
        </Button>
      </div>
      <div className="space-y-2">
        {activity.map((row) => (
          <div key={String(row.id)} className="rounded-2xl border bg-card p-4 text-sm">
            <p>
              {String(row.operation)} · External AI: {row.external_ai ? "Yes" : "No"} · Model: {String(row.model)}
            </p>
            <p className="text-muted-foreground">Documents accessed: {String(row.documents_accessed)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl">{value}</p>
    </div>
  );
}
