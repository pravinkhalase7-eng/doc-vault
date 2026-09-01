"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Camera, MoreVertical, Search, Settings } from "lucide-react";
import { useAuth } from "@/lib/auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

function IconBtn({
  href,
  label,
  onClick,
  children,
}: {
  href?: string;
  label: string;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  const className =
    "flex size-10 items-center justify-center rounded-full text-foreground hover:bg-muted";
  if (href) {
    return (
      <Link href={href} aria-label={label} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" aria-label={label} onClick={onClick} className={className}>
      {children}
    </button>
  );
}

export function HeaderActions({ className }: { className?: string }) {
  const router = useRouter();
  const { logout } = useAuth();

  return (
    <div className={cn("flex items-center", className)}>
      <IconBtn href="/search" label="Search">
        <Search className="size-5" />
      </IconBtn>
      <IconBtn href="/documents/upload" label="Camera">
        <Camera className="size-5" />
      </IconBtn>
      <IconBtn href="/settings" label="Settings">
        <Settings className="size-5" />
      </IconBtn>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="flex size-10 items-center justify-center rounded-full text-foreground hover:bg-muted"
          aria-label="More options"
        >
          <MoreVertical className="size-5" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-48">
          <DropdownMenuItem onClick={() => router.push("/settings")}>
            <Settings className="size-4" />
            Settings
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => router.push("/notifications")}>
            Notifications
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => router.push("/collections")}>
            Collections
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => router.push("/privacy")}>
            Privacy
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => router.push("/documents/upload")}>
            New document
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onClick={logout}>
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
