"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, FileText, HeartPulse, Image as ImageIcon, ShieldAlert, Trash2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { FolderGlyph } from "@/components/folder-glyph";
import { fileKind } from "@/lib/file-kind";
import { cn } from "@/lib/utils";
import { isUpcomingReminder, type ReminderRow } from "@/lib/reminders";
import { expiryLabel } from "@/lib/expiry";

type FolderStat = { id: string; name: string; file_count: number; child_count: number };
type RecentFile = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  size_bytes?: number;
  created_at?: string;
};

type Health = {
  score: number;
  notes: string[];
  expiring_soon: number;
  expired?: number;
  unverified?: number;
  total?: number;
};
type ExpiringFile = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  expiry_date?: string | null;
};

type Dashboard = {
  storage: {
    used_bytes: number;
    quota_bytes: number;
    available_bytes: number;
    used_percent: number;
    file_count: number;
  };
  documents: {
    total: number;
    ready: number;
    processing: number;
    failed: number;
    images: number;
    pdfs: number;
    other: number;
    unfiled: number;
  };
  activity: { downloads: number; shares: number };
  recent: RecentFile[];
  collections: { total: number; folders: FolderStat[] };
  health?: Health;
  expiring?: { soon: number; expired: number; items: ExpiringFile[] };
  trash_count?: number;
};

function formatBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatPercent(used: number, percent: number) {
  if (used <= 0) return "0%";
  if (percent < 1) return "<1%";
  if (percent < 10) return `${percent.toFixed(1)}%`;
  return `${Math.round(percent)}%`;
}

function formatAdded(iso?: string) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function StorageRing({ used, percent }: { used: number; percent: number }) {
  const visual = used > 0 ? Math.max(percent, 4) : 0;
  const r = 54;
  const c = 2 * Math.PI * r;
  const dash = (Math.min(100, visual) / 100) * c;
  return (
    <div className="relative size-36 shrink-0">
      <svg viewBox="0 0 140 140" className="size-36 -rotate-90">
        <circle cx="70" cy="70" r={r} fill="none" stroke="currentColor" className="text-muted" strokeWidth="12" />
        <circle
          cx="70"
          cy="70"
          r={r}
          fill="none"
          stroke="currentColor"
          className="text-primary"
          strokeWidth="12"
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center px-3 text-center">
        <p className="text-lg font-bold tracking-tight">{formatBytes(used)}</p>
        <p className="text-[11px] text-muted-foreground">{formatPercent(used, percent)} used</p>
      </div>
    </div>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [upcoming, setUpcoming] = useState<ReminderRow[]>([]);
  const hour = new Date().getHours();
  const hello = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const folders = dash?.collections.folders || [];
  const docs = dash?.documents;
  const recent = dash?.recent || [];

  useEffect(() => {
    api<Dashboard>("/dashboard").then(setDash).catch(() => setDash(null));
    api<ReminderRow[]>("/reminders")
      .then((rows) => setUpcoming((rows || []).filter(isUpcomingReminder).slice(0, 4)))
      .catch(() => setUpcoming([]));
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">{hello}</p>
          <h1 className="text-3xl">{user?.full_name?.split(" ")[0]}</h1>
        </div>
        <Link
          href="/ai"
          className="rounded-full bg-primary px-4 py-2 text-sm text-primary-foreground shadow-sm"
        >
          Ask My Vault
        </Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="overflow-hidden rounded-2xl lg:col-span-5">
          <CardContent className="flex items-center gap-5 p-6">
            <StorageRing used={dash?.storage.used_bytes ?? 0} percent={dash?.storage.used_percent ?? 0} />
            <div className="min-w-0 space-y-2">
              <p className="text-sm text-muted-foreground">Storage</p>
              <p className="text-2xl font-semibold tracking-tight">
                {formatBytes(dash?.storage.available_bytes ?? 104_857_600)} free
              </p>
              <p className="text-sm text-muted-foreground">
                {formatBytes(dash?.storage.used_bytes ?? 0)} of {formatBytes(dash?.storage.quota_bytes ?? 104_857_600)}
              </p>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{
                    width: `${dash?.storage.used_bytes ? Math.max(4, Math.min(100, dash.storage.used_percent)) : 0}%`,
                  }}
                />
              </div>
              <p className="font-mono text-[11px] text-muted-foreground">100 MB per account</p>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-3 gap-4 lg:col-span-7">
          <StatTile label="Files" value={docs?.total ?? 0} hint="In your vault" href="/documents" />
          <StatTile
            label="Photos"
            value={docs?.images ?? 0}
            hint={docs?.pdfs ? `${docs.pdfs} PDFs` : "Images saved"}
            href="/documents"
          />
          <StatTile
            label="Unfiled"
            value={docs?.unfiled ?? 0}
            hint={docs?.unfiled ? "Not in a collection" : "All filed"}
            href="/collections"
          />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="rounded-2xl">
          <CardContent className="flex items-start gap-4 p-5">
            <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <HeartPulse className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-muted-foreground">Vault health</p>
              <p className="mt-0.5 text-3xl font-bold tracking-tight">{dash?.health?.score ?? "—"}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {dash?.health?.notes?.[0] || "Upload a file to start tracking health."}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-2xl">
          <CardContent className="space-y-3 p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Dates</p>
                <h2 className="text-lg font-semibold">Expiring soon</h2>
              </div>
              <Link href="/expiring" className="text-sm text-primary">
                See all
              </Link>
            </div>
            {(dash?.expiring?.items || []).length === 0 ? (
              <p className="py-2 text-sm text-muted-foreground">No passports or policies due in the next 30 days.</p>
            ) : (
              <div className="divide-y divide-border/70">
                {(dash?.expiring?.items || []).map((file) => (
                  <Link key={file.id} href={`/documents/${file.id}`} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
                      <ShieldAlert className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{file.title}</span>
                      <span className="block text-xs text-muted-foreground">{expiryLabel(file.expiry_date)}</span>
                    </span>
                    <ChevronRight className="size-4 text-muted-foreground" />
                  </Link>
                ))}
              </div>
            )}
            {(dash?.expiring?.expired || 0) + (dash?.expiring?.soon || 0) > 0 && (
              <p className="text-xs text-muted-foreground">
                {dash?.expiring?.expired ? `${dash.expiring.expired} expired` : null}
                {dash?.expiring?.expired && dash?.expiring?.soon ? " · " : null}
                {dash?.expiring?.soon ? `${dash.expiring.soon} in the next 30 days` : null}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {(dash?.trash_count || 0) > 0 && (
        <Link href="/trash" className="flex items-center gap-3 rounded-2xl border bg-card px-4 py-3">
          <span className="flex size-9 items-center justify-center rounded-xl bg-muted text-muted-foreground">
            <Trash2 className="size-4" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-medium">Trash</span>
            <span className="block text-xs text-muted-foreground">
              {dash?.trash_count} file{(dash?.trash_count || 0) === 1 ? "" : "s"} you can still restore
            </span>
          </span>
          <ChevronRight className="size-4 text-muted-foreground" />
        </Link>
      )}

      {upcoming.length > 0 && (
        <Card className="rounded-2xl">
          <CardContent className="space-y-3 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Schedule</p>
                <h2 className="text-lg font-semibold">Upcoming</h2>
              </div>
              <Link href="/appointments" className="text-sm text-primary">
                See all
              </Link>
            </div>
            <div className="divide-y divide-border/70">
              {upcoming.map((row) => (
                <Link key={row.id} href="/appointments" className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{row.title}</span>
                    <span className="block text-xs text-muted-foreground">{row.when_label || row.fire_at}</span>
                  </span>
                  <ChevronRight className="size-4 text-muted-foreground" />
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="rounded-2xl">
          <CardContent className="space-y-1 p-5">
            <div className="mb-3 flex items-center justify-between px-1">
              <div>
                <p className="text-sm text-muted-foreground">Folders</p>
                <h2 className="text-lg font-semibold">Collections</h2>
              </div>
              <Link href="/collections" className="text-sm text-primary">
                View all
              </Link>
            </div>
            {folders.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Collections you create will appear here.
              </p>
            ) : (
              <div className="divide-y divide-border/70">
                {folders.slice(0, 6).map((folder) => (
                  <Link
                    key={folder.id}
                    href={`/collections?folder=${folder.id}`}
                    className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <FolderGlyph size="sm" />
                    <span className="min-w-0 flex-1 truncate text-[15px] font-medium">{folder.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {folder.file_count
                        ? `${folder.file_count} file${folder.file_count === 1 ? "" : "s"}`
                        : "Empty"}
                    </span>
                    <ChevronRight className="size-4 text-muted-foreground" />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardContent className="space-y-1 p-5">
            <div className="mb-3 px-1">
              <p className="text-sm text-muted-foreground">Library</p>
              <h2 className="text-lg font-semibold">What’s stored</h2>
            </div>
            <div className="divide-y divide-border/70">
              <TypeRow icon={ImageIcon} tone="bg-primary/10 text-primary" label="Photos" value={docs?.images ?? 0} />
              <TypeRow icon={FileText} tone="bg-muted text-foreground" label="PDFs" value={docs?.pdfs ?? 0} />
              <TypeRow icon={FileText} tone="bg-muted text-muted-foreground" label="Other" value={docs?.other ?? 0} />
            </div>
            <p className="px-1 pt-3 text-xs text-muted-foreground">
              {(dash?.activity?.downloads || 0) + (dash?.activity?.shares || 0) > 0
                ? `${dash?.activity?.downloads || 0} downloads · ${dash?.activity?.shares || 0} shares`
                : `${docs?.total ?? 0} files taking ${formatBytes(dash?.storage.used_bytes ?? 0)}`}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="space-y-4 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Activity</p>
              <h2 className="text-lg font-semibold">Recently added</h2>
            </div>
            <Link href="/documents" className="text-sm text-primary">
              All files
            </Link>
          </div>
          {recent.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Save a file from AI and it will show up here.</p>
          ) : (
            <div className="divide-y divide-border/70">
              {recent.map((file) => {
                const kind = fileKind(file);
                const Icon = kind.icon;
                return (
                  <Link
                    key={file.id}
                    href={`/documents/${file.id}`}
                    className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <span
                      className={cn(
                        "flex size-10 shrink-0 items-center justify-center rounded-xl",
                        kind.tone,
                      )}
                    >
                      <Icon className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{file.title}</span>
                      <span className="block text-xs text-muted-foreground">
                        {formatBytes(file.size_bytes || 0)}
                        {file.created_at ? ` · ${formatAdded(file.created_at)}` : ""}
                      </span>
                    </span>
                  </Link>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatTile({
  label,
  value,
  hint,
  href,
}: {
  label: string;
  value: number;
  hint: string;
  href?: string;
}) {
  const inner = (
    <Card className="h-full rounded-2xl">
      <CardContent className="p-5">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 text-3xl font-bold tracking-tight">{value}</p>
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

function TypeRow({
  icon: Icon,
  tone,
  label,
  value,
}: {
  icon: typeof FileText;
  tone: string;
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-3 py-2.5">
      <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-xl", tone)}>
        <Icon className="size-4" />
      </span>
      <span className="min-w-0 flex-1 text-[15px] font-medium">{label}</span>
      <span className="text-xs text-muted-foreground">{value === 0 ? "None" : value}</span>
    </div>
  );
}
