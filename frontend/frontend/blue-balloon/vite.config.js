import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  build: { target: 'es2022' },
  // Dev: forward /api (and the page-asset URLs under it) to the FastAPI backend
  // so the SPA is same-origin — the login cookie and the "/api/..." asset paths
  // just work, no CORS. Override the backend with BB_BACKEND if it's elsewhere.
  server: {
    proxy: {
      '/api': { target: process.env.BB_BACKEND || 'http://localhost:8000', changeOrigin: true },
    },
  },
});
