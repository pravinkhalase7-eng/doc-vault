/** Crop a photo and wrap one or more JPEGs in a simple PDF. */

export type CropNorm = { x: number; y: number; w: number; h: number };

const MAX_EDGE = 2000;
const MAX_PAGES = 12;

export function clampCrop(crop: CropNorm): CropNorm {
  const x = Math.min(0.95, Math.max(0, crop.x));
  const y = Math.min(0.95, Math.max(0, crop.y));
  const w = Math.min(1 - x, Math.max(0.05, crop.w));
  const h = Math.min(1 - y, Math.max(0.05, crop.h));
  return { x, y, w, h };
}

export async function cropToJpeg(
  source: Blob,
  crop: CropNorm,
  maxEdge = MAX_EDGE,
): Promise<{ blob: Blob; width: number; height: number }> {
  const box = clampCrop(crop);
  const bitmap = await createImageBitmap(source, { imageOrientation: "from-image" });
  try {
    const sx = Math.round(box.x * bitmap.width);
    const sy = Math.round(box.y * bitmap.height);
    const sw = Math.max(1, Math.round(box.w * bitmap.width));
    const sh = Math.max(1, Math.round(box.h * bitmap.height));
    const scale = Math.min(1, maxEdge / Math.max(sw, sh));
    const width = Math.max(1, Math.round(sw * scale));
    const height = Math.max(1, Math.round(sh * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Could not crop this photo");
    ctx.drawImage(bitmap, sx, sy, sw, sh, 0, 0, width, height);
    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (next) => (next ? resolve(next) : reject(new Error("Could not save this photo"))),
        "image/jpeg",
        0.84,
      );
    });
    return { blob, width, height };
  } finally {
    bitmap.close();
  }
}

export async function jpegsToPdf(
  pages: Array<{ jpeg: Uint8Array; width: number; height: number }>,
  filename: string,
): Promise<File> {
  if (!pages.length) throw new Error("Add at least one page");
  if (pages.length > MAX_PAGES) throw new Error(`A scan can have at most ${MAX_PAGES} pages`);
  const pdf = buildJpegPdf(pages.slice(0, MAX_PAGES));
  const copy = new ArrayBuffer(pdf.byteLength);
  new Uint8Array(copy).set(pdf);
  const name = filename.endsWith(".pdf") ? filename : `${filename}.pdf`;
  return new File([copy], name, { type: "application/pdf" });
}

function buildJpegPdf(pages: Array<{ jpeg: Uint8Array; width: number; height: number }>): Uint8Array {
  const chunks: Uint8Array[] = [];
  const offsets: number[] = [0];
  let size = 0;

  function add(part: string | Uint8Array) {
    const bytes = typeof part === "string" ? new TextEncoder().encode(part) : part;
    chunks.push(bytes);
    size += bytes.length;
  }

  function markObj() {
    offsets.push(size);
  }

  add("%PDF-1.4\n");
  markObj();
  add("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n");
  const kids = pages.map((_, i) => `${3 + i * 3} 0 R`).join(" ");
  markObj();
  add(`2 0 obj\n<< /Type /Pages /Kids [${kids}] /Count ${pages.length} >>\nendobj\n`);

  pages.forEach((page, i) => {
    const pageId = 3 + i * 3;
    const contentId = pageId + 1;
    const imageId = pageId + 2;
    const { pw, ph } = pagePoints(page.width, page.height);
    const content = `q ${pw.toFixed(2)} 0 0 ${ph.toFixed(2)} 0 0 cm /Im1 Do Q\n`;
    markObj();
    add(
      `${pageId} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pw.toFixed(2)} ${ph.toFixed(2)}] ` +
        `/Resources << /XObject << /Im1 ${imageId} 0 R >> >> /Contents ${contentId} 0 R >>\nendobj\n`,
    );
    markObj();
    add(`${contentId} 0 obj\n<< /Length ${content.length} >>\nstream\n${content}endstream\nendobj\n`);
    markObj();
    add(
      `${imageId} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${page.width} /Height ${page.height} ` +
        `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${page.jpeg.length} >>\nstream\n`,
    );
    add(page.jpeg);
    add("\nendstream\nendobj\n");
  });

  const xrefAt = size;
  const objCount = offsets.length;
  let xref = `xref\n0 ${objCount}\n0000000000 65535 f \n`;
  for (let i = 1; i < objCount; i += 1) {
    xref += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  add(xref);
  add(`trailer\n<< /Size ${objCount} /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`);

  const out = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

function pagePoints(width: number, height: number) {
  const max = 842;
  const scale = Math.min(max / Math.max(1, width), max / Math.max(1, height), 1);
  return { pw: Math.max(72, width * scale), ph: Math.max(72, height * scale) };
}

export const SCAN_MAX_PAGES = MAX_PAGES;
