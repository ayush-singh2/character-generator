// Reproduce the supplied reference's bundled font assets without network requests.
import fs from 'node:fs';
const input = process.argv[2];
if (!input) throw new Error('Usage: node scripts/extract-fonts.mjs <reference.html>');
const source = fs.readFileSync(input, 'utf8');
const manifest = JSON.parse(source.split('<script type="__bundler/manifest">')[1].split('</script>')[0]);
fs.mkdirSync('public/fonts', { recursive: true });
for (const [id, item] of Object.entries(manifest)) {
  if (item.mime === 'font/woff2') fs.writeFileSync('public/fonts/' + id + '.woff2', Buffer.from(item.data, 'base64'));
}
