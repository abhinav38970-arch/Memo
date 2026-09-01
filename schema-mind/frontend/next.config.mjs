/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'db.onlinewebfonts.com',
      },
      {
        protocol: 'https',
        hostname: 'd8j0ntlcm91z4.cloudfront.net',
      },
    ],
  },
  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the browser can use
    // relative URLs (works locally, in sandboxes, and behind proxies).
    // Set BACKEND_URL to override (e.g. your Render backend URL).
    const backend = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
