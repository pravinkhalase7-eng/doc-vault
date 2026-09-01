"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

function ResetInner() {
  const token = useSearchParams().get("token") || "";
  const [password, setPassword] = useState("");
  return (
    <form
      className="mx-auto mt-24 max-w-md space-y-4 rounded-3xl border bg-card p-8"
      onSubmit={async (e) => {
        e.preventDefault();
        await api("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, password }) });
        toast.success("Password updated.");
      }}
    >
      <h1 className="text-3xl">New password</h1>
      <Input type="password" minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} required />
      <Button type="submit" className="w-full rounded-full">Update password</Button>
    </form>
  );
}

export default function ResetPage() {
  return (
    <Suspense>
      <ResetInner />
    </Suspense>
  );
}
