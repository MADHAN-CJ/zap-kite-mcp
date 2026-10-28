import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync("app/globals.css", "utf8");

describe("brand tokens", () => {
  it("uses the /markets palette and font system", () => {
    for (const value of ["#20251b", "#62675f", "#f7f6f2", "#f6d64d", "#171a17", "#e4e7dc"]) {
      expect(css).toContain(value);
    }
    for (const family of ["Libre Baskerville", "Onest", "Departure Mono"]) {
      expect(css).toContain(`font-family: "${family}"`);
    }
    expect(css).not.toMatch(/Geist/);
  });

  it("ships the self-hosted font files and logos", () => {
    for (const file of [
      "public/brand/fonts/libre-baskerville-500-latin.woff2",
      "public/brand/fonts/onest-latin.woff2",
      "public/brand/fonts/departure-mono.woff2",
      "public/brand/markets-logomark-mono.svg",
      "public/brand/markets-slash.svg",
      "app/icon.svg",
    ]) {
      expect(readFileSync(file).length).toBeGreaterThan(100);
    }
  });
});
