"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

const modes = [
  { id: "PRIVATE", title: "Private AI", body: "Local processing only. Gemini is never called." },
  { id: "CLOUD", title: "Cloud AI", body: "Gemini may receive minimized metadata. Originals stay on disk." },
  { id: "CUSTOM", title: "Custom", body: "You choose per operation later in Privacy Center." },
];

export default function OnboardingFlow() {
  const router = useRouter();
  const { load } = useAuth();
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState("PRIVATE");

  async function finish() {
    await api("/users/onboarding", {
      method: "POST",
      body: JSON.stringify({
        ai_privacy_mode: mode,
        external_ai_enabled: mode === "CLOUD",
        weekly_report_enabled: true,
      }),
    });
    await load();
    router.push("/home");
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-xl items-center px-4">
      <div className="w-full space-y-6">
        <p className="text-sm text-muted-foreground">Step {step} of 3</p>
        {step === 1 && (
          <div className="space-y-4">
            <h1 className="text-4xl">Welcome to DocVault</h1>
            <p>Create your secure vault. Originals remain on your Hostinger disk.</p>
            <Button className="rounded-full" type="button" onClick={() => setStep(2)}>
              Continue
            </Button>
          </div>
        )}
        {step === 2 && (
          <div className="space-y-4">
            <h1 className="text-4xl">Choose AI privacy mode</h1>
            {modes.map((item) => (
              <button
                key={item.id}
                onClick={() => setMode(item.id)}
                className={`w-full rounded-3xl border p-5 text-left ${mode === item.id ? "border-primary bg-accent" : "bg-card"}`}
              >
                <p className="text-lg">{item.title}</p>
                <p className="text-sm text-muted-foreground">{item.body}</p>
              </button>
            ))}
            <Button className="rounded-full" type="button" onClick={() => setStep(3)}>
              Continue
            </Button>
          </div>
        )}
        {step === 3 && (
          <div className="space-y-4">
            <h1 className="text-4xl">Ready when you are</h1>
            <p>Upload your first document after this. We’ll extract metadata locally first.</p>
            <Button className="rounded-full" type="button" onClick={finish}>
              Enter vault
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
