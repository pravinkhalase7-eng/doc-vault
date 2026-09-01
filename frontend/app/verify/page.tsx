"use client";

import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Suspense } from "react";

function VerifyInner() {
  const token = useSearchParams().get("token") || "";
  return (
    <div className="mx-auto mt-24 max-w-md rounded-3xl border bg-card p-8 text-center">
      <h1 className="text-3xl">Verify email</h1>
      <Button
        className="mt-6 rounded-full"
        onClick={async () => {
          await api("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) });
          toast.success("Email verified. You can sign in.");
        }}
      >
        Confirm
      </Button>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
