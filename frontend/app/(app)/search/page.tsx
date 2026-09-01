"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Array<{ id: string; title: string }>>([]);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl">Search</h1>
      <Input
        value={q}
        onChange={async (e) => {
          setQ(e.target.value);
          const data = await api<{ items: typeof items }>("/search", {
            method: "POST",
            body: JSON.stringify({ q: e.target.value }),
          });
          setItems(data.items);
        }}
        placeholder="Filename, tags, person, expiry, OCR…"
      />
      {items.map((doc) => (
        <Link key={doc.id} href={`/documents/${doc.id}`} className="block rounded-2xl border bg-card p-4">
          {doc.title}
        </Link>
      ))}
    </div>
  );
}
