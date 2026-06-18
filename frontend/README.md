# Bifrost frontend vendor build

A one-time bundler (re-run only when bumping the `@material/web` version) that
produces the self-contained, **offline** Material 3 web-component bundle Bifrost
serves. No runtime CDN, consistent with the rest of the stack.

## Build

```sh
cd frontend
npm install
npm run build
```

Output: [`../bifrost/web/static/vendor/material-web.js`](../bifrost/web/static/vendor/)
— committed and served locally. `node_modules/` is gitignored.

## Notes

- `entry.js` imports `@material/web/all.js` (every component). To shrink the
  bundle, switch to individual imports (e.g. `@material/web/button/filled-button.js`).
- Theming is separate: [`../bifrost/web/static/bifrost-md-theme.css`](../bifrost/web/static/)
  aliases Bifrost's existing `--bf-*` tokens onto the `--md-sys-*` roles, so the
  components follow the app's Nordic palette and light/dark theme automatically.
- `@material/web` is in maintenance mode upstream; pin a known-good version here
  and treat it as a stable, frozen dependency.
