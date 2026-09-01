import Link from "next/link";
import { Lock, Shield, Sparkles, HardDrive } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_color-mix(in_oklch,var(--mint)_18%,transparent),_transparent_38%),_radial-gradient(circle_at_90%_0%,_color-mix(in_oklch,var(--primary)_22%,transparent),_transparent_32%),_var(--background)]">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div>
          <p className="font-mono text-[11px] tracking-[0.28em] text-[var(--mint)]">PRIVATE AI</p>
          <h1 className="text-2xl font-bold tracking-tight">DocVault</h1>
        </div>
        <div className="flex gap-3">
          <Link href="/login" className="rounded-full px-4 py-2 text-sm text-foreground/80 hover:text-foreground">
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Create your vault
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-16">
        <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-[var(--mint)]">
          <Lock className="size-3" /> Files stay on your Hostinger disk
        </p>
        <h2 className="max-w-3xl text-5xl font-bold leading-[1.05] tracking-tight md:text-7xl">
          A private personal AI for the documents that actually matter.
        </h2>
        <p className="mt-6 max-w-xl text-lg text-muted-foreground">
          Upload once. Ask anything. Originals never leave your VPS unless you
          explicitly allow Cloud AI — and even then, Gemini only sees the
          minimum metadata required.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Link
            href="/login"
            className="rounded-full bg-[var(--mint)] px-6 py-3 text-sm font-medium text-[var(--mint-foreground)]"
          >
            Continue as guest
          </Link>
          <Link
            href="/register"
            className="rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground"
          >
            Start with Private AI
          </Link>
          <Link href="/privacy-policy" className="rounded-full border border-white/15 px-6 py-3 text-sm">
            How privacy works
          </Link>
        </div>
        <div className="mt-20 grid gap-4 md:grid-cols-3">
          {[
            {
              icon: HardDrive,
              title: "Your disk, your files",
              body: "Originals live under /var/lib/docvault on your VPS. They are never uploaded to Gemini File Search, S3, or third-party storage.",
            },
            {
              icon: Shield,
              title: "Privacy gateway",
              body: "Aadhaar, PAN, passports, bank and medical records stay local. Cloud AI is off by default.",
            },
            {
              icon: Sparkles,
              title: "Ask My Vault",
              body: "Every answer comes with evidence: document, page, and confidence. If it isn’t in your files, the AI says so.",
            },
          ].map((item) => (
            <div key={item.title} className="rounded-[24px] border border-white/10 bg-card p-6">
              <item.icon className="mb-4 size-5 text-[var(--mint)]" />
              <h3 className="text-xl font-bold">{item.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{item.body}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
