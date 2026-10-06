import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build gọn cho Docker (node server.js, không cần node_modules đầy đủ)
  output: "standalone",
};

export default nextConfig;
