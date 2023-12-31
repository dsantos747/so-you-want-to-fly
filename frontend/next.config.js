/** @type {import('next').NextConfig} */
const nextConfig = {
  // experimental: {
  //   serverActions: true,
  // },
  async headers() {
    return [
      {
        source: '/',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
        ],
      },
    ];
  },
  rewrites: async () => {
    return [
      {
        source: '/api/:path*',
        destination: process.env.NODE_ENV === 'development' ? 'http://localhost:8080/api/:path*' : '/api/',
      },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https', //https://images.unsplash.com/photo-1565012975094-cad0b63d3646?
        hostname: 'images.unsplash.com',
      },
    ],
  },
};

module.exports = nextConfig;
