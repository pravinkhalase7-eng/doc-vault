"use client";

import { Suspense } from "react";
import { VaultChat } from "@/components/vault-chat";

export default function AiPage() {
  return (
    <Suspense fallback={<div className="h-dvh bg-background" />}>
      <VaultChat />
    </Suspense>
  );
}
