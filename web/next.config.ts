import type { NextConfig } from "next";

// In development the FastAPI backend runs separately (uvicorn on :8000);
// requests to /api/* are proxied there so the browser only talks to one origin.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
