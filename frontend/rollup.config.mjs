import { nodeResolve } from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';

// Bundles @material/web (and its lit dependency) into one self-contained ES
// module so it can be served locally with no runtime CDN. Output lands next to
// the existing vendored lit bundle.
export default {
  input: 'entry.js',
  output: {
    file: '../bifrost/web/static/vendor/material-web.js',
    format: 'es',
  },
  plugins: [nodeResolve(), terser()],
};
