"use client";

import { CoachChat } from "@/components/coach-chat";

export default function EnglishPage() {
  return (
    <CoachChat
      mode="english"
      title="English"
      initials="EN"
      hint="Learn English and get corrections"
    />
  );
}
