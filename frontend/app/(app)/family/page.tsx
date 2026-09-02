"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Users } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Member = {
  id: string;
  email: string;
  full_name?: string | null;
  role: string;
  status: "joined" | "pending";
  is_owner?: boolean;
};

type SharedFolder = { id: string; name: string };

type JoinedFamily = {
  id: string;
  name: string;
  owner_name?: string | null;
};

type FamilySnapshot = {
  family: { id: string; name: string; is_owner: boolean };
  members: Member[];
  collections: SharedFolder[];
  joined_families: JoinedFamily[];
};

export default function FamilyPage() {
  const [data, setData] = useState<FamilySnapshot | null>(null);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);

  async function load() {
    const snapshot = await api<FamilySnapshot>("/family");
    setData(snapshot);
    setLoading(false);
  }

  useEffect(() => {
    load().catch((err) => {
      setLoading(false);
      toast.error(err instanceof Error ? err.message : "Could not load family");
    });
  }, []);

  async function invite(event: FormEvent) {
    event.preventDefault();
    const value = email.trim();
    if (!value) return;
    setInviting(true);
    try {
      await api("/family/members", { method: "POST", body: JSON.stringify({ email: value }) });
      setEmail("");
      toast.success("Invite sent");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not invite");
    } finally {
      setInviting(false);
    }
  }

  async function removeMember(id: string) {
    try {
      await api(`/family/members/${id}`, { method: "DELETE" });
      toast.success("Removed from family");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove");
    }
  }

  async function leave(familyId: string) {
    try {
      await api(`/family/${familyId}/leave`, { method: "POST" });
      toast.success("Left family");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not leave");
    }
  }

  async function unshare(collectionId: string) {
    try {
      await api(`/family/collections/${collectionId}`, { method: "DELETE" });
      toast.success("Folder is private again");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not unshare");
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-5">
      <div>
        <h1 className="text-3xl">Family</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Invite people you trust, then share folders with them from Collections.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <form onSubmit={invite} className="space-y-3 rounded-2xl bg-card p-4">
            <Label htmlFor="family-email">Invite by email</Label>
            <div className="flex gap-2">
              <Input
                id="family-email"
                type="email"
                required
                placeholder="alex@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="h-11 rounded-full"
              />
              <Button type="submit" disabled={inviting} className="h-11 rounded-full px-4">
                Invite
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">They need a DocVault account on that email to open shared folders.</p>
          </form>

          <section className="overflow-hidden rounded-2xl bg-card">
            <div className="flex items-center gap-2 px-4 py-3">
              <Users className="size-4 text-muted-foreground" />
              <h2 className="text-[15px] font-medium">Members</h2>
            </div>
            <ul>
              {(data?.members || []).map((member) => (
                <li key={member.id} className="flex items-center gap-3 border-t px-4 py-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px]">{member.full_name || member.email}</span>
                    <span className="block text-xs text-muted-foreground">
                      {member.full_name ? member.email : member.status === "pending" ? "Invite pending" : "Joined"}
                      {member.is_owner ? " · Owner" : ""}
                    </span>
                  </span>
                  {!member.is_owner && (
                    <button type="button" className="text-xs text-destructive" onClick={() => removeMember(member.id)}>
                      Remove
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="overflow-hidden rounded-2xl bg-card">
            <div className="px-4 py-3">
              <h2 className="text-[15px] font-medium">Folders shared with family</h2>
            </div>
            {(data?.collections || []).length === 0 ? (
              <p className="border-t px-4 py-6 text-sm text-muted-foreground">
                Open a folder in{" "}
                <Link href="/collections" className="text-primary">
                  Collections
                </Link>{" "}
                and choose Share with family.
              </p>
            ) : (
              <ul>
                {(data?.collections || []).map((col) => (
                  <li key={col.id} className="flex items-center gap-3 border-t px-4 py-3">
                    <Link href={`/collections?folder=${col.id}`} className="min-w-0 flex-1 truncate text-[15px]">
                      {col.name}
                    </Link>
                    <button type="button" className="text-xs text-muted-foreground" onClick={() => unshare(col.id)}>
                      Stop sharing
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {(data?.joined_families || []).length > 0 && (
            <section className="overflow-hidden rounded-2xl bg-card">
              <div className="px-4 py-3">
                <h2 className="text-[15px] font-medium">Families you joined</h2>
              </div>
              <ul>
                {data?.joined_families.map((family) => (
                  <li key={family.id} className="flex items-center gap-3 border-t px-4 py-3">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15px]">{family.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        Shared by {family.owner_name || "a family member"}
                      </span>
                    </span>
                    <button type="button" className="text-xs text-destructive" onClick={() => leave(family.id)}>
                      Leave
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
