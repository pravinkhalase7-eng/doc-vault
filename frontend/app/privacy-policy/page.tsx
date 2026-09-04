export default function PrivacyPolicyPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 px-6 py-16">
      <p className="text-[11px] tracking-[0.28em] text-primary">🔒 PRIVATE AI</p>
      <h1 className="text-3xl">How DocVault uses data</h1>
      <section>
        <h2 className="text-2xl">Where files are stored</h2>
        <p className="text-muted-foreground">
          Original documents are stored on your Hostinger VPS disk under a private directory such as
          <code> /var/lib/docvault</code>. That path is not served by Nginx. Files are only available through
          authenticated API endpoints.
        </p>
      </section>
      <section>
        <h2 className="text-2xl">How AI works</h2>
        <p className="text-muted-foreground">
          Private AI runs locally: OCR, classification, and embeddings. Cloud AI (Gemini) is optional and off by
          default.
        </p>
      </section>
      <section>
        <h2 className="text-2xl">What Gemini receives</h2>
        <p className="text-muted-foreground">
          If you enable Cloud AI, Gemini may receive minimized extracted text and metadata required for the
          question — never the original PDF/image by default.
        </p>
      </section>
      <section>
        <h2 className="text-2xl">What is never sent automatically</h2>
        <p className="text-muted-foreground">
          Aadhaar, PAN, passport, bank details, medical records, passwords, OTPs, and credit card information are
          treated as highly sensitive. External AI is blocked unless you explicitly override.
        </p>
      </section>
      <section>
        <h2 className="text-2xl">Email ingest</h2>
        <p className="text-muted-foreground">
          If you forward a file to your private DocVault address, the attachment is stored on this VPS like any other
          upload. The message still travels through your mail provider first. Treat that address like a password and
          rotate it in Settings if it leaks.
        </p>
      </section>
      <section>
        <h2 className="text-2xl">How data is deleted</h2>
        <p className="text-muted-foreground">
          Documents go to trash for 30 days. You can delete AI data (embeddings, chats, evidence) without deleting
          the original file.
        </p>
      </section>
    </main>
  );
}
