import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  base: '/static/',
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        admin: resolve(__dirname, 'admin.html'),
        borrow: resolve(__dirname, 'borrow.html'),
      },
    },
  },
});
