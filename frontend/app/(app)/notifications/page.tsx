"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Reminder = {
  id: string;
  title: string;
  when_label?: string;
  fire_at: string;
  sent_at: string | null;
  cancelled?: boolean;
  channel?: string;
  kind?: string;
};

export default function NotificationsPage() {
  const [items, setItems] = useState<Array<{ id: string; title: string; body: string; created_at: string }>>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  useEffect(() => {
    api<typeof items>("/notifications").then(setItems);
    api<Reminder[]>("/reminders").then(setReminders);
  }, []);
  const upcoming = reminders.filter((row) => {
    if (row.sent_at || row.cancelled) return false;
    const at = Date.parse(row.fire_at);
    return Number.isNaN(at) || at >= Date.now() - 60_000;
  });
  const seen = new Set<string>();
  const uniqueItems = items.filter((n) => {
    const key = `${n.title}|${n.body}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl">Notifications</h1>
      {upcoming.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm text-muted-foreground">Upcoming calls</h2>
          {upcoming.map((row) => (
            <div key={row.id} className="rounded-2xl border bg-card p-5">
              <h2 className="text-lg">{row.title}</h2>
              <p className="text-sm text-muted-foreground">{row.when_label || row.fire_at}</p>
            </div>
          ))}
        </div>
      )}
      {items.length === 0 && upcoming.length === 0 && <p className="text-muted-foreground">You’re all caught up.</p>}
      {uniqueItems.map((n) => (
        <div key={n.id} className="rounded-2xl border bg-card p-5">
          <h2 className="text-lg">{n.title}</h2>
          <p className="text-sm text-muted-foreground">{n.body}</p>
        </div>
      ))}
    </div>
  );
}
