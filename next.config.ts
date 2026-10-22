import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(import.meta.dirname),
  turbopack: { root: path.join(import.meta.dirname) },
};

export default nextConfig;
