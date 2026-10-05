import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';
import { loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000';
  return {
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: [],
      manifest: {
        name: 'PRAMANA Evidence Workspace', short_name: 'PRAMANA',
        description: 'Evidence-led Ayurvedic IP and regulatory research', theme_color: '#f7f8f5',
        background_color: '#f7f8f5', display: 'standalone', start_url: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
      workbox: {
        navigateFallback: '/index.html', globPatterns: ['**/*.{js,mjs,css,html,svg,png,woff2}'],
        manifestTransforms: [async (entries) => ({
          manifest: entries.map((entry) => entry.url.endsWith('.mjs')
            ? { ...entry, revision: `${entry.revision ?? entry.url}-module-mime-v1` } : entry),
          warnings: [],
        })],
      },
    }),
  ],
  preview: { proxy: { '/v1': { target: proxyTarget, changeOrigin: true } } },
  server: {
    host: '0.0.0.0',
    ...(env.VITE_API_MODE !== 'mock' ? { proxy: { '/v1': { target: proxyTarget, changeOrigin: true } } } : {}),
  },
  };
});
