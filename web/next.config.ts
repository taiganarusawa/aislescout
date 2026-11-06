import type { NextConfig } from "next";

// Where the Python API (`aislescout serve`) is running. The browser only talks to
// this Next.js server; requests to /api/* are proxied to the backend, so there's
// no CORS setup and the backend URL never reaches the client.
const API_URL = process.env.AISLESCOUT_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
