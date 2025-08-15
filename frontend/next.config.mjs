/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  // Production optimizations
  productionBrowserSourceMaps: false,
  poweredByHeader: false,
  // Disable features not supported in static export
  experimental: {
    optimizePackageImports: ["@headlessui/react", "lucide-react"],
  },
}

export default nextConfig
