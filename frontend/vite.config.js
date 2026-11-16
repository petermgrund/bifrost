import { svelte } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const here = (path) => fileURLToPath(new URL(path, import.meta.url));

const blankImmichAssets = {
  name: 'blank-immich-assets',
  enforce: 'pre',
  resolveId(source, importer) {
    if (importer?.includes('/@immich/ui/') && /\/assets\/[^/]+\.(svg|png)$/.test(source)) return '\0blank-asset';
  },
  load(id) {
    if (id === '\0blank-asset') return 'export default "";';
  },
};

export default defineConfig({
  base: '/static/app/',
  plugins: [blankImmichAssets, tailwindcss(), svelte()],
  resolve: {
    alias: {
      '$app/environment': here('src/shims/environment.js'),
      '$app/navigation': here('src/shims/navigation.js'),
      '$app/state': here('src/shims/state.js'),
    },
  },
  build: {
    outDir: here('../bifrost/web/static/app'),
    emptyOutDir: true,
    modulePreload: false,
    rolldownOptions: {
      input: here('src/app/main.js'),
      output: {
        entryFileNames: 'app.js',
        chunkFileNames: '[name].js',
        assetFileNames: (asset) => (asset.names.some((n) => n.endsWith('.css')) ? 'app.css' : '[name][extname]'),
      },
    },
  },
});
