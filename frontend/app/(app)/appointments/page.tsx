"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { CalendarClock } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
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

import { isUpcomingReminder, type ReminderRow } from "@/lib/reminders";

export default function AppointmentsPage() {
  const [rows, setRows] = useState<ReminderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<ReminderRow | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api<ReminderRow[]>("/reminders");
      setRows(data || []);
    } catch {
      toast.error("Could not load appointments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const upcoming = useMemo(
    () =>
      rows
        .filter(isUpcomingReminder)
        .slice()
        .sort((a, b) => Date.parse(a.fire_at || "") - Date.parse(b.fire_at || "")),
    [rows],
  );

  async function confirmCancel() {
    if (!pending) return;
    setBusyId(pending.id);
    try {
      await api(`/reminders/${pending.id}`, { method: "DELETE" });
      setRows((current) =>
        current.map((item) => (item.id === pending.id ? { ...item, cancelled: true } : item)),
      );
      toast.success("Cancelled");
    } catch {
      toast.error("Could not cancel");
    } finally {
      setBusyId(null);
      setPending(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-3xl">Appointments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          All upcoming visits and reminders. Cancel any you no longer want.
        </p>
      </div>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : upcoming.length === 0 ? (
        <div className="rounded-2xl border bg-card p-8 text-center">
          <CalendarClock className="mx-auto mb-3 size-8 text-muted-foreground" />
          <p className="font-medium">Nothing upcoming</p>
          <p className="mt-1 text-sm text-muted-foreground">
            In Ask My Vault, say “doctor appointment tomorrow at 10am”.
          </p>
          <Link href="/ai" className="mt-4 inline-block text-sm text-primary">
            Open chat
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {upcoming.map((row) => (
            <div key={row.id} className="flex items-start gap-3 rounded-2xl border bg-card p-5">
              <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--accent-foreground)]">
                <CalendarClock className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{row.title}</p>
                <p className="text-sm text-muted-foreground">{row.when_label || row.fire_at}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {row.kind === "appointment" ? "Appointment" : "Reminder"}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="rounded-full"
                disabled={busyId === row.id}
                onClick={() => setPending(row)}
              >
                Cancel
              </Button>
            </div>
          ))}
        </div>
      )}

      <AlertDialog open={Boolean(pending)} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel {pending?.title || "this"}?</AlertDialogTitle>
            <AlertDialogDescription>
              DocVault will not call or notify you for this
              {pending?.kind === "appointment" ? " appointment" : " reminder"}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={Boolean(busyId)}
              onClick={() => void confirmCancel()}
            >
              Cancel it
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
