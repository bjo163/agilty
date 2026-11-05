import type { NextConfig } from "next";
const apiOrigin = (process.env.ROCKSOUL_API_INTERNAL_URL ?? "http://127.0.0.1:8765").replace(/\/$/, "");
const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiOrigin}/api/:path*` },
      { source: "/healthz", destination: `${apiOrigin}/healthz` },
    ];
  },
};
export default nextConfig;
