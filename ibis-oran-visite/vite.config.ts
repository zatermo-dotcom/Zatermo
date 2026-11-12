import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' : le dossier dist/ peut être servi depuis n'importe quel sous-chemin.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1200 },
});
