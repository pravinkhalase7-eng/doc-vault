import type { ReactNode } from "react";

export function AuthScreen({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_color-mix(in_oklch,var(--mint)_22%,transparent),_transparent_42%),_radial-gradient(circle_at_85%_10%,_color-mix(in_oklch,var(--primary)_28%,transparent),_transparent_34%)]" />
      <div className="relative w-full max-w-md">{children}</div>
    </div>
  );
}
