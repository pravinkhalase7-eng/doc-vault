"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { GUEST_EMAIL, GUEST_PASSWORD } from "@/lib/guest";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthScreen } from "@/components/auth-screen";

export default function LoginPage() {
  const { login, guestLogin } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState(GUEST_EMAIL);
  const [password, setPassword] = useState(GUEST_PASSWORD);
  const [loading, setLoading] = useState(false);

  function afterLogin(user: { onboarding_completed: boolean }) {
    router.push(user.onboarding_completed ? "/home" : "/onboarding");
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const user = await login(email, password);
      afterLogin(user);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not sign in");
    } finally {
      setLoading(false);
    }
  }

  async function onGuest() {
    setLoading(true);
    try {
      const user = await guestLogin();
      afterLogin(user);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not enter as guest");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthScreen>
      <form
        onSubmit={onSubmit}
        className="w-full rounded-[28px] border border-white/10 bg-card/90 p-8 shadow-[0_24px_80px_rgba(0,0,0,0.35)] backdrop-blur"
      >
        <p className="font-mono text-[11px] tracking-[0.28em] text-[var(--mint)]">PRIVATE AI</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Welcome back</h1>
        <p className="mt-1 text-sm text-muted-foreground">Guest credentials are prefilled so you can enter immediately.</p>
        <div className="mt-8 space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 h-11 rounded-2xl"
              required
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 h-11 rounded-2xl"
              required
            />
          </div>
          <Button type="submit" size="xl" className="w-full" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </Button>
          <Button
            type="button"
            variant="mint"
            size="xl"
            className="w-full"
            disabled={loading}
            onClick={onGuest}
          >
            Continue as guest
          </Button>
        </div>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link href="/forgot-password">Forgot password</Link>
          {" · "}
          <Link href="/register">Create a vault</Link>
        </p>
      </form>
    </AuthScreen>
  );
}
