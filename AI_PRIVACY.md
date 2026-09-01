# AI Privacy

Default: **Private AI ON**, **Cloud AI OFF**.

## What stays local

Original PDFs/images, OCR pages, and highly sensitive identity/financial/medical documents.

## What Gemini may see (only if Cloud AI is enabled)

Minimized extracted text and structured metadata required for the current question. Context is built in `context_builder.py` and must pass `privacy_gateway.check_ai_request`.

## What is never sent automatically

Aadhaar, PAN, passport, bank statements, medical records, passwords, OTPs, credit cards, and any document with **Exclude from AI**.

## Evidence and audit

Every chat stores:

- Answer
- Source document + page
- Whether a raw document was sent (always false in the default design)
- Model name and external_ai flag

Users can open **AI Privacy Center**, **View AI Activity**, and **Delete AI Data** without deleting original files.

This product does **not** claim “zero access”. Operators of the VPS can access disk and database. Cloud AI, when enabled, sends minimized metadata to Google.
