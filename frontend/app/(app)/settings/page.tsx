"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, CalendarClock, Camera, ChevronRight, Clapperboard, Copy, Download, Folders, HelpCircle, Hourglass, Lock, LogOut, Mail, MessageSquare, Moon, Phone, Share2, Shield, Sun, Trash2, UserRound, Users } from "lucide-react";
import { toast } from "sonner";
import { useTheme } from "next-themes";
import { api } from "@/lib/api";
import { downloadVault } from "@/lib/files";
import { useAuth } from "@/lib/auth";
import { disablePush, enablePush, pushSupported } from "@/lib/push";
import { Switch } from "@/components/ui/switch";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

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

function PushAlertsForm() {
  const { user, load } = useAuth();
  const [saving, setSaving] = useState(false);
  const [secure, setSecure] = useState(false);
  const [supported, setSupported] = useState(false);
  const [installed, setInstalled] = useState(false);
  const enabled = Boolean(user?.preferences?.notification_push);

  useEffect(() => {
    setSecure(window.isSecureContext);
    setSupported(pushSupported());
    setInstalled(window.matchMedia("(display-mode: standalone)").matches);
  }, []);

  async function toggle(on: boolean) {
    setSaving(true);
    try {
      if (on) {
        await enablePush();
        toast.success("Reminder alerts are on");
      } else {
        await disablePush();
        toast.success("Reminder alerts are off");
      }
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not update alerts");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2 rounded-2xl bg-card px-4 py-4">
      <div className="flex items-center gap-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-white">
          <Bell className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px]">Reminder alerts</p>
          <p className="text-xs text-muted-foreground">
            {supported
              ? installed
                ? "Lock-screen alert when a reminder is due"
                : "On iPhone, Add to Home screen first, then turn this on. Android can use it after installing from Chrome."
              : secure
                ? "This browser does not support web push"
                : "Lock-screen push needs HTTPS. You’ll still get the alert in the Notifications tab."}
          </p>
        </div>
        <Switch checked={enabled && supported} disabled={saving || !supported} onCheckedChange={toggle} />
      </div>
    </div>
  );
}

function ShareIntoVaultHint() {
  const [secure, setSecure] = useState(false);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    setSecure(window.isSecureContext);
    setInstalled(window.matchMedia("(display-mode: standalone)").matches);
  }, []);

  const hint = !secure
    ? "Android Share needs HTTPS plus Add to Home screen. iPhone cannot list a PWA in Share — in Photos tap Share → Save to Files, then in DocVault use Add files and pick it."
    : installed
      ? "Android: Photos → Share → DocVault. iPhone still cannot list this app in Share; Save to Files, then Add files in DocVault."
      : "Android: Add to Home screen in Chrome, then Share can list DocVault. iPhone cannot add a PWA to Share; Save to Files, then Add files here.";

  return (
    <div className="flex items-start gap-3 rounded-2xl bg-card px-4 py-4">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-white">
        <Share2 className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[15px]">Share into vault</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
    </div>
  );
}

type IngestInfo = {
  address: string;
  domain: string;
  receiving: boolean;
  hint: string;
  shared_inbox?: string;
  shared_inbox_enabled?: boolean;
  login_email?: string;
};

function EmailIngestForm() {
  const [info, setInfo] = useState<IngestInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [rotateOpen, setRotateOpen] = useState(false);
  const [rotating, setRotating] = useState(false);

  async function loadIngest() {
    try {
      const data = await api<IngestInfo>("/users/me/ingest");
      setInfo(data);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load your ingest address");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadIngest();
  }, []);

  async function copyText(value: string, ok: string) {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(ok);
    } catch {
      toast.message(ok, { description: value });
    }
  }

  async function rotate() {
    if (rotating) return;
    setRotating(true);
    try {
      const data = await api<IngestInfo>("/users/me/ingest/rotate", { method: "POST" });
      setInfo(data);
      setRotateOpen(false);
      toast.success("Old private address no longer works. Copy the new one.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not rotate the address");
    } finally {
      setRotating(false);
    }
  }

  const shared = info?.shared_inbox || "support@doxstation.com";
  const loginEmail = info?.login_email;

  return (
    <div className="space-y-3 rounded-2xl bg-card px-4 py-4">
      <div className="flex items-center gap-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-white">
          <Mail className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[15px]">Email into vault</p>
          <p className="text-xs text-muted-foreground">
            Send a PDF from {loginEmail || "your DocVault email"} to {shared}. Put the collection in the subject —
            Insurance, Bills — or it goes to Default.
          </p>
        </div>
      </div>
      <div className="flex gap-2">
        <Input readOnly value={loading ? "Loading…" : shared} className="h-11 rounded-xl bg-background px-3 font-mono text-xs" />
        <Button
          type="button"
          variant="outline"
          className="h-11 shrink-0 rounded-xl px-3"
          onClick={() => void copyText(shared, "Copied support inbox")}
          disabled={loading}
        >
          <Copy className="size-4" />
        </Button>
      </div>
      {info && !info.shared_inbox_enabled ? (
        <p className="text-xs text-muted-foreground">
          The server is not polling this mailbox yet. Add Hostinger IMAP settings (IMAP_HOST, IMAP_USERNAME,
          IMAP_PASSWORD) so mail to {shared} is picked up.
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">{info?.hint}</p>
      )}
      <p className="text-xs text-muted-foreground">Private backup address (anyone with it can add files):</p>
      <div className="flex gap-2">
        <Input
          readOnly
          value={loading ? "Loading…" : info?.address || ""}
          className="h-11 rounded-xl bg-background px-3 font-mono text-xs"
        />
        <Button
          type="button"
          variant="outline"
          className="h-11 shrink-0 rounded-xl px-3"
          onClick={() => info?.address && void copyText(info.address, "Copied private address")}
          disabled={!info?.address}
        >
          <Copy className="size-4" />
        </Button>
      </div>
      <Button type="button" variant="outline" className="w-full rounded-xl" onClick={() => setRotateOpen(true)} disabled={!info}>
        Rotate private address
      </Button>
      <AlertDialog open={rotateOpen} onOpenChange={setRotateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rotate the private address?</AlertDialogTitle>
            <AlertDialogDescription>
              Only the backup dv… address changes. Sending to {shared} from your login email still works.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction disabled={rotating} onClick={() => void rotate()}>
              {rotating ? "Rotating…" : "Rotate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
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
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function exportVault() {
    if (exporting) return;
    setExporting(true);
    try {
      await downloadVault();
      toast.success("Vault zip is downloading");
      setExportOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not download your vault");
    } finally {
      setExporting(false);
    }
  }

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
        <Row href="/appointments" icon={CalendarClock} tone="bg-emerald-600" label="Appointments" hint="Upcoming visits and reminders" />
        <Row href="/expiring" icon={Hourglass} tone="bg-orange-500" label="Expiring soon" hint="Passports, insurance, licences" />
        <Row href="/trash" icon={Trash2} tone="bg-muted-foreground" label="Trash" hint="Restore files for 30 days" />
        <Row href="/collections" icon={Folders} tone="bg-amber-500" label="Collections" />
        <Row href="/documents/scan" icon={Camera} tone="bg-primary" label="Scan a page" hint="Shoot, crop, save as PDF" />
        <Row
          icon={Download}
          tone="bg-emerald-600"
          label="Download my vault"
          hint="Zip of every file, grouped by collection"
          onClick={() => setExportOpen(true)}
        />
      </Group>

      <PhoneCallForm />

      <EmailIngestForm />

      <PushAlertsForm />

      <ShareIntoVaultHint />

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

      <AlertDialog open={exportOpen} onOpenChange={setExportOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Download your vault?</AlertDialogTitle>
            <AlertDialogDescription>
              This saves a zip of every file still in your vault (not trash), grouped by collection. Keep it somewhere private.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction disabled={exporting} onClick={() => void exportVault()}>
              {exporting ? "Preparing…" : "Download zip"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
