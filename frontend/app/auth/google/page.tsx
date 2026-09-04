"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { AuthScreen } from "@/components/auth-screen";

export default function GoogleAuthPage() {
  const { googleLogin } = useAuth();
  const router = useRouter();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ticket = params.get("ticket");
    const next = params.get("next");
    if (!ticket) {
      router.replace("/login?error=google");
      return;
    }
    let alive = true;
    void googleLogin({ ticket })
      .then((user) => {
        if (!alive) return;
        const safe =
          next && next.startsWith("/") && !next.startsWith("//") && !next.includes("://") ? next : null;
        router.replace(user.onboarding_completed ? safe || "/home" : "/onboarding");
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "Google sign-in did not complete.");
        router.replace("/login?error=google");
      });
    return () => {
      alive = false;
    };
  }, [googleLogin, router]);

  return (
    <AuthScreen>
      <div className="w-full rounded-[28px] border border-white/10 bg-card/90 p-8 text-center">
        <p className="font-mono text-[11px] tracking-[0.28em] text-[var(--mint)]">PRIVATE AI</p>
        <p className="mt-4 text-sm text-muted-foreground">Finishing Google sign-in…</p>
      </div>
    </AuthScreen>
  );
}
