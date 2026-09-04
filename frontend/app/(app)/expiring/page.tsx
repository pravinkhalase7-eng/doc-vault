"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CalendarClock, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { fileKind } from "@/lib/file-kind";
import { cn } from "@/lib/utils";
import { expiryKind, expiryLabel, reminderFireAt } from "@/lib/expiry";
import { isUpcomingReminder, type ReminderRow } from "@/lib/reminders";

type Doc = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  expiry_date?: string | null;
  ai_classification?: string | null;
};

export default function ExpiringPage() {
  const [items, setItems] = useState<Doc[]>([]);
  const [reminders, setReminders] = useState<ReminderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    try {
      const [docs, rows] = await Promise.all([
        api<{ items: Doc[] }>("/documents?expiring_days=30&limit=200"),
        api<ReminderRow[]>("/reminders"),
      ]);
      setItems(docs.items || []);
      setReminders(rows || []);
    } catch {
      toast.error("Could not load expiring files");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const reminded = useMemo(() => {
    const ids = new Set<string>();
    for (const row of reminders) {
      if (row.document_id && isUpcomingReminder(row)) ids.add(row.document_id);
    }
    return ids;
  }, [reminders]);

  const expired = items.filter((doc) => expiryKind(doc.expiry_date) === "expired");
  const soon = items.filter((doc) => {
    const kind = expiryKind(doc.expiry_date);
    return kind === "today" || kind === "soon";
  });

  async function remind(doc: Doc) {
    if (!doc.expiry_date) return;
    if (reminded.has(doc.id)) {
      toast.message("Already on Appointments");
      return;
    }
    setBusyId(doc.id);
    try {
      const expiredDoc = expiryKind(doc.expiry_date) === "expired";
      await api("/reminders", {
        method: "POST",
        body: JSON.stringify({
          title: expiredDoc ? `Renew ${doc.title}` : `${doc.title} expires`,
          document_id: doc.id,
          fire_at: reminderFireAt(doc.expiry_date),
          offset_days: expiredDoc ? 0 : 7,
        }),
      });
      toast.success("Reminder added");
      const rows = await api<ReminderRow[]>("/reminders");
      setReminders(rows || []);
    } catch {
      toast.error("Could not add a reminder");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-3xl">Expiring soon</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Passports, insurance, licences, and anything else with a date we could read. Add a reminder and it shows up
          under Appointments.
        </p>
      </div>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border bg-card p-8 text-center">
          <CalendarClock className="mx-auto mb-3 size-8 text-muted-foreground" />
          <p className="font-medium">Nothing expiring in the next 30 days</p>
          <p className="mt-1 text-sm text-muted-foreground">
            When a file has a valid-till date, it will appear here.
          </p>
          <Link href="/documents" className="mt-4 inline-block text-sm text-primary">
            Browse files
          </Link>
        </div>
      ) : (
        <div className="space-y-6">
          {expired.length > 0 && (
            <Section title="Expired" count={expired.length}>
              {expired.map((doc) => (
                <ExpiryRow
                  key={doc.id}
                  doc={doc}
                  reminded={reminded.has(doc.id)}
                  busy={busyId === doc.id}
                  onRemind={() => void remind(doc)}
                />
              ))}
            </Section>
          )}
          {soon.length > 0 && (
            <Section title="Next 30 days" count={soon.length}>
              {soon.map((doc) => (
                <ExpiryRow
                  key={doc.id}
                  doc={doc}
                  reminded={reminded.has(doc.id)}
                  busy={busyId === doc.id}
                  onRemind={() => void remind(doc)}
                />
              ))}
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold tracking-tight text-muted-foreground">{title}</h2>
        <span className="font-mono text-[11px] text-muted-foreground">{count}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function ExpiryRow({
  doc,
  reminded,
  busy,
  onRemind,
}: {
  doc: Doc;
  reminded: boolean;
  busy: boolean;
  onRemind: () => void;
}) {
  const kind = fileKind(doc);
  const Icon = kind.icon;
  const expired = expiryKind(doc.expiry_date) === "expired";
  return (
    <div className="flex items-center gap-3 rounded-2xl border bg-card px-3 py-2.5">
      <Link href={`/documents/${doc.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <span
          className={cn(
            "flex size-11 shrink-0 items-center justify-center rounded-2xl",
            expired ? "bg-destructive/10 text-destructive" : kind.tone,
          )}
        >
          {expired ? <ShieldAlert className="size-4" /> : <Icon className="size-4" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{doc.title}</span>
          <span className={cn("block text-xs", expired ? "text-destructive" : "text-muted-foreground")}>
            {expiryLabel(doc.expiry_date)}
            {doc.ai_classification ? ` · ${doc.ai_classification}` : ""}
          </span>
        </span>
      </Link>
      <Button
        variant={reminded ? "ghost" : "outline"}
        size="sm"
        className="rounded-full"
        disabled={busy || reminded}
        onClick={onRemind}
      >
        {reminded ? "Reminded" : "Remind me"}
      </Button>
    </div>
  );
}
