import { createServer } from 'node:http'
import { readFile, readdir, stat } from 'node:fs/promises'
import { extname, resolve } from 'node:path'

export const artifacts = [
  { base: '/', directory: resolve('docs/.vitepress/dist') },
  { base: '/kittyscape/', directory: resolve('docs/.vitepress/dist-subpath') }
]

export const requiredPages = [
  'index.html', 'guide/getting-started.html', 'guide/installation.html', 'guide/configuration.html',
  'guide/shells.html', 'guide/kitty-settings.html', 'guide/troubleshooting.html', 'guide/uninstall.html',
  'reference/compatibility.html', 'reference/configuration.html', 'reference/actions.html',
  'contributing/index.html', 'releases.html', 'development/compatibility-findings.html', 'development/website.html',
  'development/release-checklist.html'
]

export async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map(entry => {
    const path = resolve(directory, entry.name)
    return entry.isDirectory() ? filesUnder(path) : [path]
  }))
  return nested.flat()
}

/** Serve only the built artifacts, so missing routes cannot fall through to a dev server. */
export async function serveArtifacts() {
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json' }
  const server = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
      const artifact = pathname.startsWith('/kittyscape/') ? artifacts[1] : artifacts[0]
      let target = resolve(artifact.directory, `.${pathname.slice(artifact.base.length - 1)}`)
      if (!target.startsWith(`${artifact.directory}/`) && target !== artifact.directory) throw new Error('Invalid path')
      if ((await stat(target)).isDirectory()) target = resolve(target, 'index.html')
      const content = await readFile(target)
      response.writeHead(200, { 'Content-Type': types[extname(target)] || 'application/octet-stream' })
      response.end(content)
    } catch {
      response.writeHead(404)
      response.end('Not found')
    }
  })
  await new Promise(resolveListening => server.listen(0, '127.0.0.1', resolveListening))
  return { server, origin: `http://127.0.0.1:${server.address().port}` }
}
