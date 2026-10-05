import type { NextConfig } from "next";

// Locally the FastAPI backend runs separately (uvicorn on :8000), so /api/* is
// proxied there and the browser only talks to one origin. On Vercel, vercel.json
// routes /api/* to the Python service before requests ever reach Next.js.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.VERCEL) return [];
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
