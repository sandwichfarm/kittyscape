import assert from 'node:assert/strict'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { extname, relative, resolve } from 'node:path'
import { gzipSync } from 'node:zlib'
import { artifacts, filesUnder, requiredPages } from './common.mjs'

const report = { checkedAt: new Date().toISOString(), artifacts: [], assets: {} }
const decode = value => value.replaceAll('&amp;', '&').replaceAll('&#39;', "'").replaceAll('&quot;', '"')

for (const artifact of artifacts) {
  const files = await filesUnder(artifact.directory)
  const paths = new Set(files)
  const pages = files.filter(path => path.endsWith('.html'))
  const html = new Map(await Promise.all(pages.map(async path => [path, await readFile(path, 'utf8')])))
  let links = 0
  for (const page of requiredPages) assert(paths.has(resolve(artifact.directory, page)), `Missing required page: ${page}`)
  for (const [path, text] of html) {
    const route = relative(artifact.directory, path)
    const location = new URL(artifact.base + route, 'https://site.invalid')
    for (const match of text.matchAll(/<(?:a|img|script|link)\b[^>]*?\b(?:href|src)="([^"]+)"/g)) {
      const url = new URL(decode(match[1]), location)
      if (url.origin !== location.origin) continue
      assert(url.pathname.startsWith(artifact.base), `${route} escapes ${artifact.base}: ${url.href}`)
      let target = decodeURIComponent(url.pathname.slice(artifact.base.length))
      if (!target || target.endsWith('/')) target += 'index.html'
      if (!extname(target)) target += '.html'
      const file = resolve(artifact.directory, target)
      assert(paths.has(file), `${route} has missing target: ${match[1]}`)
      if (url.hash && file.endsWith('.html')) {
        const anchor = decodeURIComponent(url.hash.slice(1))
        assert(html.get(file).includes(`id="${anchor}"`), `${route} has missing fragment: ${match[1]}`)
      }
      links += 1
    }
  }
  assert(!files.some(path => /\.(?:woff2?|ttf|otf)$/.test(path)), 'System-font site emitted a font asset')
  report.artifacts.push({ base: artifact.base, pages: pages.length, localLinksAndAssets: links })
}

for (const filename of ['cat-mark.svg', 'terminal-cat.svg']) {
  const image = await readFile(`docs/public/${filename}`)
  assert(image.byteLength <= 150 * 1024, `${filename} exceeds illustration budget`)
  report.assets[filename] = { bytes: image.byteLength, gzipBytes: gzipSync(image).byteLength }
}
const theme = await Promise.all(['index.js', 'Layout.vue'].map(name => readFile(`docs/.vitepress/theme/${name}`, 'utf8')))
report.assets.customThemeSourceGzipBytes = gzipSync(theme.join('\n')).byteLength
assert(report.assets.customThemeSourceGzipBytes < 10 * 1024, 'Custom theme source exceeds JavaScript budget')
await mkdir('docs/.vitepress/evidence', { recursive: true })
await writeFile('docs/.vitepress/evidence/static-results.json', `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
