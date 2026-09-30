import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the API runs separately (python server.py on :5000) and the
// dev server proxies to it. In production Flask serves the built `dist/`.
const backend = process.env.VITE_API_ENDPOINT || 'http://127.0.0.1:5000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': backend,
      '/socket.io': { target: backend, ws: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
});
