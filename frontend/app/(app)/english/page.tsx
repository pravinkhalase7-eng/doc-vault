"use client";

import { CoachChat } from "@/components/coach-chat";

export default function EnglishPage() {
  return (
    <CoachChat
      mode="english"
      title="English"
      initials="EN"
      hint="Talk like a teacher — ask anything or send a sentence"
    />
  );
}
