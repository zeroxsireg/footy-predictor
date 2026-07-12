// Data bridge: copy the Python-generated prediction JSON into public/data/,
// where the Next.js build reads it. Run before `build`/`dev`.

import { cpSync, mkdirSync, existsSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "predictions");
const dst = join(here, "..", "public", "data");

if (!existsSync(src)) {
  console.error("✗ predictions/ non trovata — genera prima i JSON (generate_json.py)");
  process.exit(1);
}

rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
cpSync(src, dst, { recursive: true });
console.log("✓ dati sincronizzati: predictions/ → web/public/data/");
