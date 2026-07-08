/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_EXPORT === "1" ? "export" : undefined,
  trailingSlash: true,
};

module.exports = nextConfig;
