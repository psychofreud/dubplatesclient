import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The window loads ui/dist/index.html from disk: relative paths.
export default defineConfig({ plugins: [react()], base: './' });
