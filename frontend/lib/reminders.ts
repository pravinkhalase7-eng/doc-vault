export type ReminderRow = {
  id: string;
  title: string;
  fire_at: string;
  sent_at: string | null;
  cancelled?: boolean;
  kind?: string;
  when_label?: string;
};

export function isUpcomingReminder(row: ReminderRow) {
  if (row.sent_at || row.cancelled) return false;
  const at = Date.parse(row.fire_at);
  return Number.isNaN(at) || at >= Date.now() - 60_000;
}
