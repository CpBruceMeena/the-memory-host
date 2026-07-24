import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow images from the backend if needed
  images: {
    remotePatterns: [],
  },

  // Don't want to rewrite headers for the BFF — it uses the same origin
};

export default nextConfig;
