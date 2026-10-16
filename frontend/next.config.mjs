import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep the server bundle for the existing web deployment while allowing
  // the Tauri build script to request a static renderer bundle explicitly.
  output: process.env.NAVIS_TAURI_BUILD === 'true' ? 'export' : 'standalone',
  trailingSlash: process.env.NAVIS_TAURI_BUILD === 'true',
  // Tauri serves the static export from its embedded asset bundle rather than
  // an HTTP origin. Relative chunk URLs keep the packaged CSS and JavaScript
  // beside index.html instead of resolving them against a missing web root.
  assetPrefix: process.env.NAVIS_TAURI_BUILD === 'true' ? './' : undefined,
  eslint: {
    ignoreDuringBuilds: true,
  },
  webpack: (config) => {
    // Keep the markdown dependency tree server-compatible. The CJS `debug`
    // package is bundled as a namespace by Next's server compiler, while the
    // app only needs its no-op behavior in the browser and during SSR.
    config.resolve.alias['debug'] = path.resolve(__dirname, 'src/mocks/debug.js');
    return config;
  }
};

export default nextConfig;
