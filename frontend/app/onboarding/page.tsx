"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import OnboardingFlow from "./flow";

export default function OnboardingPage() {
  const { user, loading, load } = useAuth();
  const router = useRouter();
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);
  if (loading || !user) return null;
  return <OnboardingFlow />;
}
