"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function AdminPage() {
  const { user } = useAuth();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Record<string, unknown>>("/admin/overview")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (user?.role !== "ADMIN" && error) {
    return <p>Admin access is required.</p>;
  }
  return (
    <div className="space-y-4">
      <h1 className="text-3xl">Admin</h1>
      <p className="text-sm text-muted-foreground">Document contents are not shown here.</p>
      {data && (
        <pre className="overflow-auto rounded-2xl border bg-card p-5 text-sm">{JSON.stringify(data, null, 2)}</pre>
      )}
    </div>
  );
}
