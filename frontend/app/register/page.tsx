"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthScreen } from "@/components/auth-screen";

export default function RegisterPage() {
  const { register, login, guestLogin } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await register(fullName, email, password);
      const user = await login(email, password);
      toast.success("Vault created. You’re in.");
      router.push(user.onboarding_completed ? "/home" : "/onboarding");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create vault");
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
        <p className="font-mono text-[11px] tracking-[0.28em] text-[var(--mint)]">PRIVATE BY DESIGN</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Create your secure vault</h1>
        <div className="mt-8 space-y-4">
          <div>
            <Label htmlFor="fullName">Full name</Label>
            <Input
              id="fullName"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="mt-1.5 h-11 rounded-2xl"
              minLength={2}
              required
            />
          </div>
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
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 h-11 rounded-2xl"
              required
            />
            <p className="mt-1.5 text-xs text-muted-foreground">At least 10 characters.</p>
          </div>
          <Button type="submit" size="xl" className="w-full" disabled={loading}>
            {loading ? "Creating…" : "Create vault"}
          </Button>
          <Button
            type="button"
            variant="mint"
            size="xl"
            className="w-full"
            disabled={loading}
            onClick={async () => {
              setLoading(true);
              try {
                const user = await guestLogin();
                router.push(user.onboarding_completed ? "/home" : "/onboarding");
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Could not enter as guest");
              } finally {
                setLoading(false);
              }
            }}
          >
            Continue as guest
          </Button>
        </div>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have one? <Link href="/login">Sign in</Link>
        </p>
      </form>
    </AuthScreen>
  );
}
