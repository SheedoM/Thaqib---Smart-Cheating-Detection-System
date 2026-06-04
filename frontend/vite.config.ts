/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    // Allow Cloudflare quick-tunnel hosts (and any dev host) to serve the app over
    // HTTPS. getUserMedia (microphone) only works in a secure context, so the phone
    // must reach the app via the tunnel's https URL — not http://<LAN-IP>:5173.
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        ws: true,
        // Preserve cookies on WebSocket upgrades from LAN clients
        configure: (proxy) => {
          proxy.on('proxyReqWs', (_proxyReq, _req, _socket, _options, _head) => {
            // cookies are forwarded automatically; this hook ensures the
            // proxy does not strip the Cookie header before upgrade.
          });
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
