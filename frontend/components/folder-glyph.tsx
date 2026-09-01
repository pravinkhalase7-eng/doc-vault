export function FolderGlyph({ size = "md" }: { size?: "sm" | "md" }) {
  const box = size === "sm" ? "h-8 w-10" : "h-12 w-[3.7rem]";
  return (
    <svg viewBox="0 0 88 72" className={box} aria-hidden>
      <path
        d="M8 20c0-4.4 3.4-8 7.6-8h16.2c2.2 0 4.2 1.1 5.5 2.9L41 20h34.4c4.2 0 7.6 3.6 7.6 8v32.4c0 4.4-3.4 8-7.6 8H15.6C11.4 68.4 8 64.8 8 60.4V20Z"
        className="fill-amber-500/90 dark:fill-amber-500"
      />
      <path
        d="M8 28c0-3.3 2.5-6 5.6-6h60.8c3.1 0 5.6 2.7 5.6 6v32.4c0 4.4-3.4 8-7.6 8H15.6C11.4 68.4 8 64.8 8 60.4V28Z"
        className="fill-amber-300 dark:fill-amber-400"
      />
      <path
        d="M8 20c0-4.4 3.4-8 7.6-8h15.4c2.1 0 4 1 5.3 2.7L40 20H15.6C11.4 20 8 23.6 8 28v-8Z"
        className="fill-amber-400 dark:fill-amber-300"
      />
    </svg>
  );
}
