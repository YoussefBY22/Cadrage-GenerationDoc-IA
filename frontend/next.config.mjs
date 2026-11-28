process.env.NEXT_TELEMETRY_DISABLED = "1";

/** @type {import('next').NextConfig} */
const nextConfig = { reactStrictMode: true, distDir: process.env.NEXT_DIST_DIR || ".next", devIndicators: false };
export default nextConfig;
