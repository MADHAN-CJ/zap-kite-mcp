import { describe, expect, it } from "vitest";
import { legacyForwardUrl, nextTokenExpiry } from "@/lib/server/kite";

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

describe("legacyForwardUrl (transition bridge to the successor app)", () => {
  it("is off when the env is unset", () => {
    expect(legacyForwardUrl("?request_token=rt&state=s", undefined)).toBeNull();
    expect(legacyForwardUrl("?request_token=rt&state=s", "  ")).toBeNull();
  });
  it("passes the callback query through untouched", () => {
    expect(
      legacyForwardUrl(
        "?status=success&request_token=rt&state=s.t",
        "https://new.example/api/broker/kite/callback/",
      ),
    ).toBe(
      "https://new.example/api/broker/kite/callback?status=success&request_token=rt&state=s.t",
    );
  });
});
