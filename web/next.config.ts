import type { NextConfig } from "next";

// The Python API (python -m immigration_helper.api). Only this server talks to it, so the browser never sees
// the OpenAI key and no CORS setup is needed.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
