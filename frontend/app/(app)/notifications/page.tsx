"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function NotificationsPage() {
  const [items, setItems] = useState<Array<{ id: string; title: string; body: string; created_at: string }>>([]);
  useEffect(() => {
    api<typeof items>("/notifications").then(setItems);
  }, []);
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl">Notifications</h1>
      {items.length === 0 && <p className="text-muted-foreground">You’re all caught up.</p>}
      {items.map((n) => (
        <div key={n.id} className="rounded-2xl border bg-card p-5">
          <h2 className="text-lg">{n.title}</h2>
          <p className="text-sm text-muted-foreground">{n.body}</p>
        </div>
      ))}
    </div>
  );
}
