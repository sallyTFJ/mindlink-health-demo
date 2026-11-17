import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dist = join(here, 'dist');
const output = resolve(here, '..', 'MindLink-离线版.html');

let html = readFileSync(join(dist, 'index.html'), 'utf8');
const css = readFileSync(join(dist, 'styles.css'), 'utf8');
let js = readFileSync(join(dist, 'app.js'), 'utf8');
const logo = readFileSync(join(dist, 'assets', 'logo-mark.svg'));
const sample = readFileSync(join(dist, 'data', 'mindlink-sample.json'), 'utf8');

const logoUri = `data:image/svg+xml;base64,${logo.toString('base64')}`;
const sampleUri = `data:application/json;charset=utf-8,${encodeURIComponent(sample)}`;

html = html
  .replace(/\s*<link rel="manifest"[^>]*>/, '')
  .replace(/<link rel="icon"[^>]*>/, `<link rel="icon" href="${logoUri}">`)
  .replace('<link rel="stylesheet" href="styles.css">', `<style>\n${css}\n</style>`)
  .replaceAll('src="assets/logo-mark.svg"', `src="${logoUri}"`)
  .replace('href="data/mindlink-sample.json" download', `href="${sampleUri}" download="mindlink-sample.json"`)
  .replace('<script src="app.js" defer></script>', `<script>\n${js.replaceAll("'assets/logo-mark.svg'", JSON.stringify(logoUri))}\n</script>`)
  .replace('</head>', '<meta name="offline-build" content="self-contained">\n</head>');

const forbiddenExternalResources = [
  [/<script[^>]+\ssrc=/i, 'external script'],
  [/<link[^>]+rel=["']stylesheet["']/i, 'external stylesheet'],
  [/<img[^>]+src=["']https?:\/\//i, 'external image'],
  [/@import\s+url/i, 'CSS @import'],
];

for (const [pattern, label] of forbiddenExternalResources) {
  if (pattern.test(html)) {
    throw new Error(`Offline build still contains ${label}.`);
  }
}

// Parse the embedded application script without executing browser-only code.
new Function(js.replaceAll("'assets/logo-mark.svg'", JSON.stringify(logoUri)));

writeFileSync(output, html, 'utf8');
console.log(output);
