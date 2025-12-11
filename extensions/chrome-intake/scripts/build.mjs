import { build } from "esbuild";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { resolve } from "path";
import { fileURLToPath } from "url";

// Use fileURLToPath to avoid double drive letters on Windows (e.g., "C:\\C:\\")
const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const dist = resolve(root, "dist");
const src = resolve(root, "src");

mkdirSync(dist, { recursive: true });

// Copy static assets
for (const file of ["manifest.json", "popup.html", "options.html"]) {
  copyFileSync(resolve(src, file), resolve(dist, file));
}

const common = {
  bundle: true,
  minify: false,
  sourcemap: true,
  target: ["chrome110"],
  loader: { ".ts": "ts" },
};

await build({
  ...common,
  entryPoints: [resolve(src, "background.ts")],
  outfile: resolve(dist, "background.js"),
  format: "iife",
});

await build({
  ...common,
  entryPoints: [resolve(src, "contentScript.ts")],
  outfile: resolve(dist, "contentScript.js"),
  format: "iife",
});

await build({
  ...common,
  entryPoints: [resolve(src, "popup.ts")],
  outfile: resolve(dist, "popup.js"),
  format: "iife",
});

await build({
  ...common,
  entryPoints: [resolve(src, "options.ts")],
  outfile: resolve(dist, "options.js"),
  format: "iife",
});

// Simple manifest version bump helper (optional)
const manifestPath = resolve(dist, "manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
if (!manifest.version) {
  manifest.version = "0.1.0";
}
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
