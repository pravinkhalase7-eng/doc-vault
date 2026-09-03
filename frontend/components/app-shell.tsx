"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import {
  Clapperboard,
  Folders,
  Home,
  MessageSquare,
  Settings,
  Shield,
  Upload,
  UserRound,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { HeaderActions } from "@/components/header-actions";

const nav = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/collections", label: "Collections", icon: Folders },
  { href: "/reels", label: "Reels", icon: Clapperboard },
  { href: "/ai", label: "AI", icon: MessageSquare },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { user, logout } = useAuth();
  const isFileViewer = path.startsWith("/documents/") && !path.includes("/upload");
  const isChat = path === "/ai" || path.startsWith("/ai/");
  const isReels = path === "/reels" || path.startsWith("/reels/");
  const immersive = isFileViewer || isChat || isReels;

  useEffect(() => {
    if (isFileViewer || typeof window === "undefined") return;
    sessionStorage.setItem("dv_return", `${path}${window.location.search}`);
  }, [path, isFileViewer]);

  return (
    <div className={cn("bg-background", immersive ? "h-dvh overflow-hidden" : "min-h-screen")}>
      {!isFileViewer && (
        <aside className="fixed inset-y-0 left-0 hidden w-64 border-r bg-sidebar p-5 md:flex md:flex-col">
          <Link href="/home" className="mb-8">
            <p className="font-mono text-[11px] tracking-[0.28em] text-[var(--mint)]">PRIVATE AI</p>
            <h1 className="text-2xl font-bold tracking-tight">DocVault</h1>
          </Link>
          <nav className="flex flex-1 flex-col gap-1">
            {[...nav].map((item) => {
              const Icon = item.icon;
              const active = path.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent/60",
                  )}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
            <Link
              href="/privacy"
              className="mt-4 flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent/60"
            >
              <Shield className="size-4" />
              Privacy Center
            </Link>
          </nav>
          <div className="mt-auto space-y-3">
            <Link
              href="/documents/upload"
              className="flex items-center justify-center gap-2 rounded-full bg-primary px-4 py-2 text-sm text-primary-foreground"
            >
              <Upload className="size-4" />
              Upload
            </Link>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <Link href="/settings" className="flex items-center gap-2">
                <UserRound className="size-4" />
                {user?.full_name?.split(" ")[0]}
              </Link>
              <button onClick={logout}>Sign out</button>
            </div>
          </div>
        </aside>
      )}

      <div className={isFileViewer ? "" : "md:pl-64"}>
        {!immersive && (
          <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-background/80 px-2 py-1.5 backdrop-blur">
            <Link href="/home" className="px-2 text-lg font-semibold tracking-tight">
              DocVault
            </Link>
            <HeaderActions />
          </header>
        )}
        <main
          className={
            immersive
              ? "h-dvh overflow-hidden p-0"
              : "px-4 py-6 pb-24 md:px-8 md:pb-10"
          }
        >
          {children}
        </main>
      </div>

      {!isFileViewer && (
        <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t bg-background/95 p-2 backdrop-blur md:hidden">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = path.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-lg py-1 text-[10px]",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
