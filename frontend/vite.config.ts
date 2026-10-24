import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  envDir: '..',
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': loadEnv(mode, '..', '').CLOUDPILOT_API_PROXY || 'http://127.0.0.1:8001' },
  },
}));

