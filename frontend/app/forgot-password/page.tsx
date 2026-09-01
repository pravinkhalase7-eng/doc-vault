"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  return (
    <form
      className="mx-auto mt-24 max-w-md space-y-4 rounded-3xl border bg-card p-8"
      onSubmit={async (e) => {
        e.preventDefault();
        await api("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
        toast.success("If that email exists, a reset link is on its way.");
      }}
    >
      <h1 className="text-3xl">Reset password</h1>
      <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      <Button type="submit" className="w-full rounded-full">Send link</Button>
    </form>
  );
}
