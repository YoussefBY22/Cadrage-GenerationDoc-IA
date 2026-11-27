import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.resolve(__dirname, "..");
const SKIP = new Set(["node_modules", ".next", "tests"]);

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    if (SKIP.has(name) || name.startsWith(".next")) return [];
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.(tsx?|css|mjs)$/.test(name) ? [p] : [];
  });
}

describe("affichage sûr et hors ligne", () => {
  const files = sources(ROOT).filter((f) => !f.endsWith("next-env.d.ts"));

  it("aucun dangerouslySetInnerHTML ni innerHTML", () => {
    for (const f of files) {
      const text = readFileSync(f, "utf8");
      expect(text, f).not.toMatch(/dangerouslySetInnerHTML|\.innerHTML/);
    }
  });

  it("aucune URL externe codée en dur (hors localhost) ni Google Fonts", () => {
    for (const f of files) {
      const text = readFileSync(f, "utf8");
      const urls = text.match(/https?:\/\/[^\s"'`)]+/g) ?? [];
      for (const u of urls) {
        expect(u, f).toMatch(/^https?:\/\/(localhost|127\.0\.0\.1)/);
      }
      expect(text, f).not.toMatch(/fonts\.googleapis|fonts\.gstatic/);
    }
  });
});
