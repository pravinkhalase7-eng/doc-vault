import { api } from "./api";

export function pushSupported() {
  return (
    typeof window !== "undefined" &&
    window.isSecureContext &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

export async function enablePush() {
  if (!pushSupported()) {
    throw new Error("This browser needs HTTPS (or localhost) for lock-screen alerts.");
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Allow notifications to get reminder alerts.");
  }
  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const config = await api<{ enabled: boolean; public_key: string }>("/push/config");
  if (!config.enabled || !config.public_key) {
    throw new Error("Push is not configured on the server yet.");
  }
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(config.public_key),
  });
  await api("/push/subscribe", { method: "POST", body: JSON.stringify(subscription.toJSON()) });
  await api("/users/me/preferences", { method: "PATCH", body: JSON.stringify({ notification_push: true }) });
}

export async function disablePush() {
  await api("/users/me/preferences", { method: "PATCH", body: JSON.stringify({ notification_push: false }) });
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.ready.catch(() => null);
  const subscription = await registration?.pushManager.getSubscription();
  if (subscription) {
    await api("/push/unsubscribe", {
      method: "POST",
      body: JSON.stringify({ endpoint: subscription.endpoint }),
    }).catch(() => undefined);
    await subscription.unsubscribe();
  }
}
