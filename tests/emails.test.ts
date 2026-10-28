import { describe, expect, it } from "vitest";
import { loginCodeEmail } from "@/lib/server/emails";

describe("login code email", () => {
  it("is branded, carries the code in html and text, and escapes", () => {
    const m = loginCodeEmail("482913");
    expect(m.subject).toBe("482913 is your /markets login code");
    for (const token of [
      "#20251b",
      "#f7f6f2",
      "Libre Baskerville",
      "/markets",
      "482913",
      "10 minutes",
    ]) {
      expect(m.html).toContain(token);
    }
    expect(m.html).toContain('viewBox="0 0 341 174"');
    expect(m.html).toContain("<path");
    expect(m.html).not.toMatch(/Zap|Slash Markets/);
    expect(m.text).toContain("482913");
    expect(m.text).not.toContain("<");
    expect(loginCodeEmail("<1>").html).toContain("&lt;1&gt;");
  });
});
