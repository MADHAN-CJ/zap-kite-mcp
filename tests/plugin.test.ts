import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

describe("plugin folder", () => {
  it("ships the same skill the MCP server documents", () => {
    expect(read("plugin/skills/slash-markets-kite-data/SKILL.md")).toBe(read("mcp/SKILL.md"));
  });

  it("points the bundled connector at the production MCP host", () => {
    const mcp = JSON.parse(read("plugin/.mcp.json"));
    expect(mcp.mcpServers["slash-markets"]).toEqual({
      type: "http",
      url: "https://mcp.slash.markets/",
    });
  });

  it("has a manifest the directory can list", () => {
    const manifest = JSON.parse(read("plugin/.claude-plugin/plugin.json"));
    expect(manifest.name).toBe("slash-markets");
    for (const key of ["version", "description", "author", "license", "icon", "privacyPolicyUrl"]) {
      expect(manifest[key], key).toBeTruthy();
    }
    expect(manifest.author.name).toBeTruthy();
  });
});
