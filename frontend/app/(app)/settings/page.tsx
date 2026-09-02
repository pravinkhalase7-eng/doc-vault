"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, ChevronRight, Clapperboard, Folders, HelpCircle, Lock, LogOut, MessageSquare, Moon, Phone, Shield, Sun, UserRound, Users } from "lucide-react";
import { toast } from "sonner";
import { useTheme } from "next-themes";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Switch } from "@/components/ui/switch";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function initials(name?: string) {
  const parts = (name || "DV").trim().split(/\s+/);
  return ((parts[0]?.[0] || "D") + (parts[1]?.[0] || "")).toUpperCase();
}

function Row({
  href,
  icon: Icon,
  tone,
  label,
  hint,
  onClick,
}: {
  href?: string;
  icon: typeof Shield;
  tone: string;
  label: string;
  hint?: string;
  onClick?: () => void;
}) {
  const inner = (
    <>
      <span className={`flex size-8 items-center justify-center rounded-lg text-white ${tone}`}>
        <Icon className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[15px]">{label}</span>
        {hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}
      </span>
      <ChevronRight className="size-4 text-muted-foreground" />
    </>
  );
  const className =
    "flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/60";
  if (href) {
    return (
      <Link href={href} className={className}>
        {inner}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={className}>
      {inner}
    </button>
  );
}

function PhoneCallForm() {
  const { user, load } = useAuth();
  const [phone, setPhone] = useState(user?.preferences?.phone_number || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setPhone(user?.preferences?.phone_number || "");
  }, [user?.preferences?.phone_number]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await api("/users/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ phone_number: phone.trim() }),
      });
      await load();
      toast.success(phone.trim() ? "Saved the number DocVault will call" : "Removed call number");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save that number");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="space-y-3 rounded-2xl bg-card px-4 py-4">
      <div className="flex items-center gap-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-white">
          <Phone className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px]">Phone calls</p>
          <p className="text-xs text-muted-foreground">DocVault calls this number for chat reminders</p>
        </div>
      </div>
      <Input
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        placeholder="98765 43210"
        value={phone}
        onChange={(event) => setPhone(event.target.value)}
        className="h-11 rounded-xl bg-background px-3"
      />
      <Button type="submit" className="w-full rounded-xl" disabled={saving}>
        {saving ? "Saving…" : "Save number"}
      </Button>
    </form>
  );
}

function Group({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-2xl bg-card">{children}</div>;
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();
  const router = useRouter();
  const dark = resolvedTheme === "dark";

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="px-1 text-3xl">Settings</h1>

      <div className="flex items-center gap-4 rounded-2xl bg-card px-4 py-4">
        <Avatar size="lg" className="size-16 bg-[color-mix(in_srgb,var(--mint)_40%,transparent)]">
          <AvatarFallback className="bg-transparent text-lg font-semibold">
            {initials(user?.full_name)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-semibold">{user?.full_name || "Your vault"}</p>
          <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {user?.preferences?.external_ai_enabled ? "Cloud AI on" : "Private AI"}
          </p>
        </div>
      </div>

      <Group>
        <Row href="/privacy" icon={Lock} tone="bg-primary" label="Privacy" hint="AI access and data controls" />
        <Row href="/family" icon={Users} tone="bg-amber-500" label="Family" hint="Invite members and share folders" />
        <Row href="/notifications" icon={Bell} tone="bg-primary" label="Notifications" />
        <Row href="/collections" icon={Folders} tone="bg-amber-500" label="Collections" />
      </Group>

      <PhoneCallForm />

      <Group>
        <Row href="/ai" icon={MessageSquare} tone="bg-primary" label="Chats" hint="Ask My Vault" />
        <Row href="/reels" icon={Clapperboard} tone="bg-primary" label="Reels" hint="Swipe through your files" />
        <Row href="/goals" icon={UserRound} tone="bg-primary" label="Life goals" />
      </Group>

      <div className="overflow-hidden rounded-2xl bg-card">
        <div className="flex items-center gap-3 px-4 py-3">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-white">
            {dark ? <Moon className="size-4" /> : <Sun className="size-4" />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[15px]">Dark mode</p>
            <p className="text-xs text-muted-foreground">Matches WhatsApp-style night theme</p>
          </div>
          <Switch checked={dark} onCheckedChange={(on) => setTheme(on ? "dark" : "light")} />
        </div>
      </div>

      <Group>
        <Row href="/privacy-policy" icon={Shield} tone="bg-primary" label="How AI uses your data" />
        <Row href="/privacy" icon={HelpCircle} tone="bg-muted-foreground" label="Help" />
      </Group>

      <button
        type="button"
        onClick={() => {
          logout();
          router.push("/login");
        }}
        className="flex w-full items-center justify-center gap-2 rounded-2xl bg-card px-4 py-3.5 text-[15px] font-medium text-destructive"
      >
        <LogOut className="size-4" />
        Sign out
      </button>
    </div>
  );
}
