import { describe, expect, it } from "vitest";
import { nextTokenExpiry } from "@/lib/server/kite";

describe("nextTokenExpiry", () => {
  it("is 06:00 IST next day when it is after 06:00 IST", () => {
    const now = new Date("2026-10-15T09:00:00+05:30");
    expect(nextTokenExpiry(now).toISOString()).toBe("2026-10-16T00:30:00.000Z");
  });

  it("is 06:00 IST today when it is before 06:00 IST", () => {
    const now = new Date("2026-10-15T02:00:00+05:30");
    expect(nextTokenExpiry(now).toISOString()).toBe("2026-10-15T00:30:00.000Z");
  });
});
