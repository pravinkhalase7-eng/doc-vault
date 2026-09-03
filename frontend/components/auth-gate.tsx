"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading, load } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const [booted, setBooted] = useState(false);

  useEffect(() => {
    let alive = true;
    const timer = window.setTimeout(() => {
      if (alive) setBooted(true);
    }, 8000);
    void load().finally(() => {
      if (!alive) return;
      window.clearTimeout(timer);
      setBooted(true);
    });
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [load]);

  useEffect(() => {
    if (!booted) return;
    if (!user) {
      const next = `${window.location.pathname}${window.location.search}`;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
      return;
    }
    if (!user.onboarding_completed && path !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [booted, user, router, path]);

  if (!booted) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Opening your vault…
      </div>
    );
  }
  if (!user) return null;
  return <>{children}</>;
}
