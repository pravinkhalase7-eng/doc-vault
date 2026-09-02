import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { PwaRegister } from "@/components/pwa-register";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DocVault AI",
  description: "A private personal AI operating system for your documents.",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, title: "DocVault" },
};

export const viewport: Viewport = {
  themeColor: "#121212",
  width: "device-width",
  initialScale: 1,
};

const UUID_POLYFILL = `(function(){try{var c=globalThis.crypto;if(!c||typeof c.randomUUID==="function")return;c.randomUUID=function(){var b=new Uint8Array(16);if(c.getRandomValues)c.getRandomValues(b);else for(var i=0;i<16;i++)b[i]=Math.floor(Math.random()*256);b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;var h="";for(i=0;i<16;i++)h+=(b[i]+256).toString(16).slice(1);return h.slice(0,8)+"-"+h.slice(8,12)+"-"+h.slice(12,16)+"-"+h.slice(16,20)+"-"+h.slice(20)};}catch(e){}})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: UUID_POLYFILL }} />
      </head>
      <body className="min-h-full flex flex-col">
        <PwaRegister />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
