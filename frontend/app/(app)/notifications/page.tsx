"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { isUpcomingReminder, type ReminderRow } from "@/lib/reminders";

export default function NotificationsPage() {
  const [items, setItems] = useState<Array<{ id: string; title: string; body: string; created_at: string }>>([]);
  const [reminders, setReminders] = useState<ReminderRow[]>([]);
  useEffect(() => {
    api<typeof items>("/notifications").then(setItems);
    api<ReminderRow[]>("/reminders").then(setReminders);
  }, []);
  const upcoming = reminders.filter(isUpcomingReminder);
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
          <div className="flex items-center justify-between">
            <h2 className="text-sm text-muted-foreground">Upcoming</h2>
            <Link href="/appointments" className="text-sm text-primary">
              Manage
            </Link>
          </div>
          {upcoming.map((row) => (
            <Link key={row.id} href="/appointments" className="block rounded-2xl border bg-card p-5">
              <h2 className="text-lg">{row.title}</h2>
              <p className="text-sm text-muted-foreground">{row.when_label || row.fire_at}</p>
            </Link>
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
