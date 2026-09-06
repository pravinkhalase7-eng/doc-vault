"use client";

import { Suspense } from "react";
import { AstroChat } from "@/components/astro-chat";

export default function AstroPage() {
  return (
    <Suspense fallback={<div className="h-dvh bg-background" />}>
      <AstroChat />
    </Suspense>
  );
}
