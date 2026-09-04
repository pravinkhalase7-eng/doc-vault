"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowLeft,
  ChevronRight,
  FolderPlus,
  MoreVertical,
  Pencil,
  Plus,
  Search,
  Share2,
  Trash2,
  Upload,
  Users,
} from "lucide-react";
import { FileActions } from "@/components/file-actions";
import { DocumentThumb } from "@/components/document-thumb";
import { FolderGlyph } from "@/components/folder-glyph";
import { moveDocumentToCollection } from "@/components/move-collection-sheet";
import { api } from "@/lib/api";
import { fileKind } from "@/lib/file-kind";
import { fileTimestamps } from "@/lib/file-time";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Collection = {
  id: string;
  name: string;
  parent_id?: string | null;
  document_ids: string[];
  is_default?: boolean;
  shared?: boolean;
  shared_with_family?: boolean;
  can_edit?: boolean;
  owner_name?: string | null;
};

type Doc = {
  id: string;
  title: string;
  original_filename: string;
  mime_type?: string;
  created_at?: string;
  updated_at?: string;
};

function displayName(col: Collection) {
  return col.name?.trim() || "Untitled";
}

function liveCount(col: Collection, docs: Doc[]) {
  return col.document_ids.filter((id) => docs.some((doc) => doc.id === id)).length;
}

function canEdit(col: Collection) {
  return col.can_edit !== false && !col.shared;
}

function countLabel(files: number, folders: number) {
  const parts = [];
  if (files) parts.push(`${files} file${files === 1 ? "" : "s"}`);
  if (folders) parts.push(`${folders} folder${folders === 1 ? "" : "s"}`);
  return parts.join(" · ") || "Empty";
}

export default function CollectionsPage() {
  return (
    <Suspense fallback={<p className="mx-auto max-w-2xl text-sm text-muted-foreground">Loading…</p>}>
      <CollectionsBrowser />
    </Suspense>
  );
}

function CollectionsBrowser() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const viewId = searchParams.get("folder");
  const [items, setItems] = useState<Collection[]>([]);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [createParentId, setCreateParentId] = useState<string | null>(null);
  const [renameCol, setRenameCol] = useState<Collection | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    const [cols, documentPage] = await Promise.all([
      api<Collection[]>("/collections"),
      api<{ items: Doc[] }>("/documents?limit=200"),
    ]);
    setItems(cols);
    setDocs(documentPage.items);
    setLoading(false);
  }

  function openFolder(id: string | null) {
    const url = id ? `/collections?folder=${encodeURIComponent(id)}` : "/collections";
    router.replace(url, { scroll: false });
  }

  useEffect(() => {
    load().catch((err) => {
      setLoading(false);
      toast.error(err instanceof Error ? err.message : "Could not load collections");
    });
  }, []);

  useEffect(() => {
    if (loading || !viewId || items.length === 0) return;
    if (!items.some((col) => col.id === viewId)) openFolder(null);
  }, [loading, viewId, items]);

  const childrenOf = (id: string | null) => items.filter((col) => (col.parent_id || null) === id);
  const byId = useMemo(() => Object.fromEntries(items.map((col) => [col.id, col])), [items]);
  const current = viewId ? byId[viewId] || null : null;
  const crumbs = useMemo(() => {
    if (!current) return [];
    const chain: Collection[] = [];
    let node: Collection | undefined = current;
    while (node) {
      chain.unshift(node);
      node = node.parent_id ? byId[node.parent_id] : undefined;
    }
    return chain;
  }, [byId, current]);
  const shown = current ? childrenOf(current.id) : childrenOf(null).filter((col) => !col.shared);
  const sharedRoots = current ? [] : items.filter((col) => col.shared && !col.parent_id);
  const filesInView = current
    ? (current.document_ids.map((id) => docs.find((doc) => doc.id === id)).filter(Boolean) as Doc[])
    : [];
  const deleting = items.find((col) => col.id === deleteId) || null;
  const createParent = items.find((col) => col.id === createParentId) || null;

  function startCreate(parentId: string | null) {
    setCreateParentId(parentId);
    setCreateOpen(true);
  }

  async function toggleFamilyShare(col: Collection) {
    try {
      if (col.shared_with_family) {
        await api(`/family/collections/${col.id}`, { method: "DELETE" });
        toast.success("Folder is private again");
      } else {
        await api("/family/collections", {
          method: "POST",
          body: JSON.stringify({ collection_id: col.id }),
        });
        toast.success("Shared with family");
      }
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update sharing");
    }
  }

  async function renameCollection(name: string) {
    if (!renameCol) return;
    await api(`/collections/${renameCol.id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    setRenameCol(null);
    toast.success("Folder renamed");
    await load();
  }

  async function removeCollection() {
    if (!deleting) return;
    try {
      await api(`/collections/${deleting.id}`, { method: "DELETE" });
      toast.success("Folder deleted");
      setDeleteId(null);
      const nextId = viewId === deleting.id ? deleting.parent_id || null : viewId;
      await load();
      if (nextId !== viewId) openFolder(nextId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete");
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      {current ? (
        <FolderHeader
          col={current}
          crumbs={crumbs}
          fileCount={liveCount(current, docs)}
          folderCount={shown.length}
          onBack={openFolder}
          onUpload={`/documents/upload?collection=${current.id}`}
          onAddFolder={() => startCreate(current.id)}
          onRename={() => setRenameCol(current)}
          onDelete={current.is_default || !canEdit(current) ? undefined : () => setDeleteId(current.id)}
          onShareFamily={canEdit(current) && !current.is_default ? () => toggleFamilyShare(current) : undefined}
        />
      ) : (
        <div className="flex items-end justify-between gap-3">
          <div>
            <h1 className="text-3xl">Folders</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Open a folder to see what’s inside.{" "}
              <Link href="/family" className="text-primary">
                Invite family
              </Link>{" "}
              to share folders with them.
            </p>
          </div>
          <Button className="rounded-full" onClick={() => startCreate(null)}>
            <FolderPlus className="size-4" />
            New
          </Button>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <EmptyVault onCreate={() => startCreate(null)} />
      ) : current ? (
        <FolderContents
          col={current}
          folders={shown}
          files={filesInView}
          docs={docs}
          childrenOf={childrenOf}
          onOpen={openFolder}
          onChanged={() => load()}
        />
      ) : (
        <div className="space-y-8">
          <FolderGrid
            folders={shown}
            docs={docs}
            childrenOf={childrenOf}
            onOpen={openFolder}
            onAddFolder={startCreate}
            onRename={setRenameCol}
            onDelete={setDeleteId}
            onShareFamily={toggleFamilyShare}
          />
          {sharedRoots.length > 0 && (
            <div className="space-y-3">
              <h2 className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Users className="size-4" />
                Shared with family
              </h2>
              <FolderGrid
                folders={sharedRoots}
                docs={docs}
                childrenOf={childrenOf}
                onOpen={openFolder}
                onAddFolder={startCreate}
                onRename={setRenameCol}
                onDelete={setDeleteId}
              />
            </div>
          )}
        </div>
      )}

      <NameDialog
        open={createOpen}
        title={createParent ? `Folder in ${displayName(createParent)}` : "New folder"}
        confirm="Create"
        onOpenChange={setCreateOpen}
        onSubmit={async (name) => {
          const created = await api<Collection>("/collections", {
            method: "POST",
            body: JSON.stringify({ name, parent_id: createParentId }),
          });
          setCreateOpen(false);
          toast.success("Folder created");
          await load();
          openFolder(created.id);
        }}
      />

      <NameDialog
        open={Boolean(renameCol)}
        title="Rename folder"
        confirm="Save"
        initial={renameCol ? displayName(renameCol) : ""}
        onOpenChange={(open) => !open && setRenameCol(null)}
        onSubmit={renameCollection}
      />

      <AlertDialog open={Boolean(deleteId)} onOpenChange={(openDialog) => !openDialog && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting ? displayName(deleting) : "folder"}?</AlertDialogTitle>
            <AlertDialogDescription>Files stay in your vault. Nested folders move up one level.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={removeCollection}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function FolderHeader({
  col,
  crumbs,
  fileCount,
  folderCount,
  onBack,
  onUpload,
  onAddFolder,
  onRename,
  onDelete,
  onShareFamily,
}: {
  col: Collection;
  crumbs: Collection[];
  fileCount: number;
  folderCount: number;
  onBack: (id: string | null) => void;
  onUpload: string;
  onAddFolder: () => void;
  onRename: () => void;
  onDelete?: () => void;
  onShareFamily?: () => void;
}) {
  const editable = canEdit(col);
  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => onBack(col.parent_id || null)}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        {col.parent_id ? displayName(crumbs[crumbs.length - 2] || col) : "Folders"}
      </button>
      <div className="flex items-center gap-3">
        <FolderGlyph size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-2xl">{displayName(col)}</h1>
            {col.is_default && (
              <span className="shrink-0 text-[11px] font-medium text-muted-foreground">Default</span>
            )}
            {(col.shared || col.shared_with_family) && (
              <span className="shrink-0 text-[11px] font-medium text-muted-foreground">Family</span>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {col.shared && col.owner_name ? `Shared by ${col.owner_name} · ` : ""}
            {countLabel(fileCount, folderCount)}
          </p>
        </div>
        {(editable || onShareFamily || onDelete) && (
          <FolderMenu
            col={col}
            compact
            onOpen={() => undefined}
            onAddFolder={onAddFolder}
            onRename={onRename}
            onDelete={onDelete}
            onShareFamily={onShareFamily}
          />
        )}
      </div>
      {editable && (
        <div className="flex gap-2">
          <Link
            href={onUpload}
            className="inline-flex h-9 flex-1 items-center justify-center gap-1.5 rounded-full bg-primary text-sm text-primary-foreground"
          >
            <Upload className="size-3.5" />
            Upload
          </Link>
          <Button variant="outline" className="h-9 flex-1 rounded-full" onClick={onAddFolder}>
            <Plus className="size-3.5" />
            New folder
          </Button>
        </div>
      )}
    </div>
  );
}

function FolderGrid({
  folders,
  docs,
  childrenOf,
  onOpen,
  onAddFolder,
  onRename,
  onDelete,
  onShareFamily,
}: {
  folders: Collection[];
  docs: Doc[];
  childrenOf: (id: string | null) => Collection[];
  onOpen: (id: string) => void;
  onAddFolder: (parentId: string | null) => void;
  onRename: (col: Collection) => void;
  onDelete: (id: string) => void;
  onShareFamily?: (col: Collection) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {folders.map((col) => {
        const files = liveCount(col, docs);
        const nested = childrenOf(col.id).length;
        const editable = canEdit(col);
        return (
          <div key={col.id} className="group relative rounded-2xl border bg-card">
            <button
              type="button"
              onClick={() => onOpen(col.id)}
              className="flex w-full flex-col items-start gap-3 p-4 pr-10 text-left"
            >
              <FolderGlyph />
              <span className="min-w-0">
                <span className="block truncate font-medium">{displayName(col)}</span>
                <span className="block text-xs text-muted-foreground">
                  {col.shared && col.owner_name ? `${col.owner_name} · ` : ""}
                  {countLabel(files, nested)}
                </span>
              </span>
            </button>
            <div className="absolute top-2.5 right-2">
              <FolderMenu
                col={col}
                onOpen={() => onOpen(col.id)}
                onAddFolder={() => onAddFolder(col.id)}
                onRename={() => onRename(col)}
                onDelete={col.is_default || !editable ? undefined : () => onDelete(col.id)}
                onShareFamily={editable && !col.is_default && onShareFamily ? () => onShareFamily(col) : undefined}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FolderContents({
  col,
  folders,
  files,
  docs,
  childrenOf,
  onOpen,
  onChanged,
}: {
  col: Collection;
  folders: Collection[];
  files: Doc[];
  docs: Doc[];
  childrenOf: (id: string | null) => Collection[];
  onOpen: (id: string) => void;
  onChanged: () => Promise<void>;
}) {
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const available = docs.filter((doc) => !col.document_ids.includes(doc.id));
  const matches = available.filter((doc) =>
    `${doc.title} ${doc.original_filename}`.toLowerCase().includes(query.toLowerCase()),
  );
  const empty = folders.length === 0 && files.length === 0 && !adding;
  const editable = canEdit(col);

  async function addDoc(id: string) {
    try {
      await moveDocumentToCollection(id, col.id);
      setAdding(false);
      setQuery("");
      await onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add file");
    }
  }

  async function removeDoc(id: string) {
    try {
      await api(`/collections/${col.id}/documents/${id}`, { method: "DELETE" });
      await onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove");
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border bg-card">
      {empty ? (
        <div className="px-4 py-10 text-center">
          <p className="font-medium">Nothing in this folder yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {editable ? "Upload a file or move one in from another folder." : "This folder was shared with your family."}
          </p>
          {editable && (
            <button type="button" className="mt-4 text-sm text-primary" onClick={() => setAdding(true)}>
              Move a file in
            </button>
          )}
        </div>
      ) : (
        <>
          {folders.length > 0 && (
            <ul>
              {folders.map((folder) => (
                <li key={folder.id} className="border-b last:border-b-0">
                  <button
                    type="button"
                    onClick={() => onOpen(folder.id)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/50"
                  >
                    <FolderGlyph size="sm" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15px] font-medium">{displayName(folder)}</span>
                      <span className="block text-xs text-muted-foreground">
                        {countLabel(liveCount(folder, docs), childrenOf(folder.id).length)}
                      </span>
                    </span>
                    <ChevronRight className="size-4 text-muted-foreground" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {files.length > 0 && (
            <div className={cn("grid grid-cols-2 gap-3 p-3 sm:grid-cols-3", folders.length > 0 && "border-t")}>
              {files.map((doc) => {
                const kind = fileKind(doc);
                const when = fileTimestamps(doc.created_at, doc.updated_at);
                return (
                  <div key={doc.id} className="overflow-hidden rounded-2xl bg-muted/40">
                    <Link href={`/documents/${doc.id}`} className="block">
                      <span className="relative block aspect-[3/4] overflow-hidden bg-muted">
                        <DocumentThumb
                          id={doc.id}
                          title={doc.title}
                          mimeType={doc.mime_type}
                          filename={doc.original_filename}
                          className="size-full"
                        />
                      </span>
                      <span className="block space-y-0.5 px-2.5 pt-2.5">
                        <span className="block truncate text-sm font-medium">{doc.title}</span>
                        <span className="block text-[11px] leading-snug text-muted-foreground">
                          {kind.label}
                          {when ? ` · ${when}` : ""}
                        </span>
                      </span>
                    </Link>
                    <div className="flex items-center justify-between px-1 pb-1">
                      <FileActions
                        id={doc.id}
                        title={doc.title}
                        filename={doc.original_filename}
                        currentCollectionId={col.id}
                        onMoved={onChanged}
                      />
                      {!col.is_default && editable && (
                        <button
                          type="button"
                          className="px-2 text-[11px] text-muted-foreground hover:text-foreground"
                          onClick={() => removeDoc(doc.id)}
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
      {adding && editable ? (
        <div className="space-y-2 border-t p-3">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              autoFocus
              className="h-10 rounded-2xl pl-9"
              placeholder="Find a file to move here…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          {matches.slice(0, 8).map((doc) => (
            <button
              key={doc.id}
              type="button"
              className="flex w-full items-center justify-between rounded-xl px-2 py-2 text-left text-sm hover:bg-muted"
              onClick={() => addDoc(doc.id)}
            >
              {doc.title}
              <span className="text-xs text-primary">Move in</span>
            </button>
          ))}
          {matches.length === 0 && <p className="px-2 text-sm text-muted-foreground">No matching files.</p>}
          <button type="button" className="px-2 text-xs text-muted-foreground" onClick={() => setAdding(false)}>
            Cancel
          </button>
        </div>
      ) : (
        !empty && editable && (
          <div className="border-t px-4 py-3">
            <button type="button" className="text-sm text-primary" onClick={() => setAdding(true)}>
              Move a file in
            </button>
          </div>
        )
      )}
    </div>
  );
}

function FolderMenu({
  col,
  onOpen,
  onAddFolder,
  onRename,
  onDelete,
  onShareFamily,
  compact,
}: {
  col: Collection;
  onOpen: () => void;
  onAddFolder: () => void;
  onRename: () => void;
  onDelete?: () => void;
  onShareFamily?: () => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const editable = canEdit(col);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`${displayName(col)} options`}
        className="flex size-8 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <MoreVertical className="size-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-44">
        {!compact && <DropdownMenuItem onClick={onOpen}>Open</DropdownMenuItem>}
        {editable && !compact && (
          <DropdownMenuItem onClick={() => router.push(`/documents/upload?collection=${col.id}`)}>
            <Upload className="size-4" />
            Upload here
          </DropdownMenuItem>
        )}
        {editable && !compact && (
          <DropdownMenuItem onClick={onAddFolder}>
            <Plus className="size-4" />
            New folder inside
          </DropdownMenuItem>
        )}
        {editable && (
          <DropdownMenuItem onClick={onRename}>
            <Pencil className="size-4" />
            Rename
          </DropdownMenuItem>
        )}
        {onShareFamily && (
          <DropdownMenuItem onClick={onShareFamily}>
            <Share2 className="size-4" />
            {col.shared_with_family ? "Stop sharing with family" : "Share with family"}
          </DropdownMenuItem>
        )}
        {onDelete && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={onDelete}>
              <Trash2 className="size-4" />
              Delete
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function EmptyVault({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="rounded-2xl border bg-card px-6 py-12 text-center">
      <div className="mx-auto mb-3 flex justify-center">
        <FolderGlyph />
      </div>
      <p className="font-medium">No folders yet</p>
      <p className="mt-1 text-sm text-muted-foreground">Create a folder for IDs, bills, or anything you want grouped.</p>
      <Button className="mt-5 rounded-full" onClick={onCreate}>
        <FolderPlus className="size-4" />
        New folder
      </Button>
    </div>
  );
}

function NameDialog({
  open,
  title,
  confirm,
  initial = "",
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  title: string;
  confirm: string;
  initial?: string;
  onOpenChange: (open: boolean) => void;
  onSubmit: (name: string) => Promise<void>;
}) {
  const [name, setName] = useState(initial);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setName(initial);
      setBusy(false);
    }
  }, [open, initial]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      await onSubmit(name.trim());
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save folder");
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div>
            <Label htmlFor="folder-name">Name</Label>
            <Input
              id="folder-name"
              className="mt-1.5 h-11 rounded-2xl"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Vehicle papers"
              required
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" className="rounded-full" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" className="rounded-full" disabled={busy || !name.trim()}>
              {confirm}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
