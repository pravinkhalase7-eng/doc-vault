"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";

export default function GoalsPage() {
  const [goals, setGoals] = useState<string[]>([]);
  const [checklist, setChecklist] = useState<{ item: string; present: boolean; document_id?: string }[] | null>(null);

  useEffect(() => {
    api<{ goals: string[] }>("/ai/goals").then((d) => setGoals(d.goals));
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-3xl">What do you want to accomplish?</h1>
      <div className="flex flex-wrap gap-2">
        {goals.map((g) => (
          <button
            key={g}
            className="rounded-full border px-4 py-2 text-sm"
            onClick={async () => {
              const data = await api<{ items: typeof checklist }>(`/ai/goals/${g}/checklist`, { method: "POST" });
              setChecklist(data.items || []);
            }}
          >
            {g.replaceAll("_", " ")}
          </button>
        ))}
      </div>
      {checklist && (
        <div className="rounded-2xl border bg-card p-6">
          {checklist.map((item) => (
            <p key={item.item}>
              {item.present ? "✓" : "⚠️"} {item.item}{" "}
              {item.document_id && <Link href={`/documents/${item.document_id}`}>Open evidence</Link>}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
