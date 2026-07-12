import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export", // static site → deploy anywhere (Netlify/Vercel/GH Pages)
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
