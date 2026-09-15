import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { once } from 'node:events'
import { closeSync, openSync } from 'node:fs'
import { lstat, mkdir, readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { artifacts, filesUnder, requiredPages, serveArtifacts } from './common.mjs'

const require = createRequire(import.meta.url)
const playwrightPath = process.env.PLAYWRIGHT_PATH || '/home/sandwich/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core'
const playwright = require(playwrightPath)
const axePath = process.env.AXE_PATH || '/home/sandwich/.npm/_npx/0f94ee7615faf582/node_modules/axe-core/axe.min.js'
const axeSource = await readFile(axePath, 'utf8')
const output = resolve(process.env.ZOOM_EVIDENCE_DIR || `/tmp/kittyscape-browser-zoom-${Date.now()}`)
assert(output.startsWith('/tmp/'), 'Zoom evidence must stay in /tmp')
const browsers = process.argv.slice(2).length ? process.argv.slice(2) : ['chromium', 'firefox', 'webkit']
assert(browsers.every(name => ['chromium', 'firefox', 'webkit'].includes(name)))
await mkdir(output, { recursive: true })

async function refuseExistingDisplay() {
  for (const path of ['/tmp/.X103-lock', '/tmp/.X11-unix/X103']) {
    try {
      await lstat(path)
    } catch (error) {
      if (error.code === 'ENOENT') continue
      throw error
    }
    throw new Error(`Refusing existing display resource: ${path}`)
  }
}

async function startDisplay() {
  await refuseExistingDisplay()
  const log = openSync(`${output}/xvfb.log`, 'wx')
  const child = spawn('/tmp/kittyscape-tools/xvfb/usr/bin/Xvfb', [':103', '-screen', '0', '1600x1200x24', '-dpi', '96', '-nolisten', 'tcp'],
    { stdio: ['ignore', log, log] })
  closeSync(log)
  for (let attempt = 0; attempt < 100; attempt += 1) {
    assert.equal(child.exitCode, null, 'Owned Xvfb exited during startup')
    try {
      if ((await readFile('/tmp/.X103-lock', 'utf8')).trim() === String(child.pid)) return child
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
    await delay(25)
  }
  child.kill('SIGTERM')
  throw new Error('Owned Xvfb did not create its lock')
}

function input(owner, command) {
  const result = spawnSync('python', [resolve('tests/site/zoom.py'), String(owner.pid), JSON.stringify(command)], { encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  return JSON.parse(result.stdout)
}

async function keys(owner, names) {
  input(owner, { keys: names })
  await delay(180)
}

function screenshot(owner, name) {
  input(owner, { screenshot: `${output}/${name}.png` })
}

function options(name) {
  const env = { ...process.env, DISPLAY: ':103', WAYLAND_DISPLAY: '', GDK_BACKEND: 'x11', MOZ_ENABLE_WAYLAND: '0' }
  const common = { headless: false, env }
  if (name === 'chromium') return { ...common, args: ['--ozone-platform=x11', '--window-size=1440,1000'] }
  if (name !== 'webkit') return common
  const bundle = '/home/sandwich/.cache/ms-playwright/webkit-2311/minibrowser-gtk'
  return { ...common, executablePath: `${bundle}/bin/MiniBrowser`, env: {
    ...env, WEBKIT_EXEC_PATH: `${bundle}/bin`, WEBKIT_INJECTED_BUNDLE_PATH: `${bundle}/lib`, WEBKIT_FORCE_COMPLEX_TEXT: '1',
    LD_LIBRARY_PATH: `${bundle}/lib:${bundle}/sys/lib:/tmp/kittyscape-webkit-wxpv4ff1/usr/lib/x86_64-linux-gnu`
  } }
}

async function metrics(page) {
  return page.evaluate(() => ({
    dpr: devicePixelRatio, innerWidth, innerHeight, outerWidth, outerHeight,
    viewportScale: visualViewport.scale, cssZoom: getComputedStyle(document.documentElement).zoom,
    scrollWidth: document.documentElement.scrollWidth
  }))
}

async function setZoom(page, owner) {
  input(owner, { prepare: true })
  await delay(300)
  await keys(owner, ['Control_L', '0'])
  const baseline = { ...await metrics(page), native: input(owner, {}).geometry }
  const steps = [baseline]
  for (let count = 0; count < 12; count += 1) {
    await keys(owner, ['Control_L', 'Shift_L', 'equal'])
    const current = { ...await metrics(page), native: input(owner, {}).geometry }
    steps.push(current)
    if (current.dpr / baseline.dpr >= 1.99) break
  }
  const zoomed = steps.at(-1)
  return { baseline, zoomed, steps, exact200: Math.abs(zoomed.dpr / baseline.dpr - 2) < .02 &&
    Math.abs(baseline.innerWidth / zoomed.innerWidth - 2) < .02 && zoomed.native.width === baseline.native.width }
}

async function focusDetails(page) {
  return page.evaluate(() => {
    const node = document.activeElement
    const style = getComputedStyle(node)
    const rect = node.getBoundingClientRect()
    return { tag: node.tagName, name: node.getAttribute('aria-label') || node.textContent.trim().slice(0, 100),
      href: node.getAttribute('href'), outline: style.outlineStyle, outlineWidth: style.outlineWidth,
      focusVisible: node.matches(':focus-visible'), visible: rect.bottom > 0 && rect.top < innerHeight }
  })
}

async function reach(page, owner, selector, trace, backwards = false) {
  for (let step = 0; step < 18; step += 1) {
    await keys(owner, backwards ? ['Shift_L', 'Tab'] : ['Tab'])
    const focus = await focusDetails(page)
    trace.push(focus)
    if (await page.locator(selector).evaluateAll(nodes => nodes.includes(document.activeElement))) return focus
  }
  throw new Error(`Keyboard could not reach ${selector}`)
}

async function checkKeyboard(page, owner, base, prefix) {
  const trace = []
  const accessibility = []
  await page.goto(origin + base, { waitUntil: 'networkidle' })
  await keys(owner, ['Escape'])
  await keys(owner, ['Tab'])
  const skip = await focusDetails(page)
  trace.push(skip)
  assert.match(skip.name, /Skip to content/)
  assert.notEqual(skip.outline, 'none')
  assert(skip.visible)
  screenshot(owner, `${prefix}-skip-focus`)
  await keys(owner, ['Return'])
  assert.match(page.url(), /#VPContent$/)
  await keys(owner, ['Tab'])
  trace.push(await focusDetails(page))
  assert.match(trace.at(-1).name, /Read the docs/)
  await keys(owner, ['Return'])
  await page.waitForURL(`${origin}${base}guide/getting-started.html`)
  await writeFile(`${output}/${prefix}-getting-started.aria.txt`, await page.locator('body').ariaSnapshot())
  await page.goto(origin + base, { waitUntil: 'networkidle' })
  await reach(page, owner, 'button[aria-label="Search"]', trace)
  await keys(owner, ['Return'])
  await page.locator('#localsearch-input').waitFor({ state: 'visible' })
  input(owner, { text: 'fallback' })
  await page.locator('.VPLocalSearchBox .result').first().waitFor({ state: 'visible' })
  await writeFile(`${output}/${prefix}-search.aria.txt`, await page.locator('body').ariaSnapshot())
  accessibility.push(await interactiveAccessibility(page, 'search-open'))
  screenshot(owner, `${prefix}-search-open`)
  await keys(owner, ['Escape'])
  trace.push(await focusDetails(page))
  assert.match(trace.at(-1).name, /Search/)
  await reach(page, owner, '.VPNavBarHamburger', trace)
  await keys(owner, ['Return'])
  assert.equal(await page.locator('.VPNavBarHamburger').getAttribute('aria-expanded'), 'true')
  await reach(page, owner, '.VPNavScreen .VPSwitchAppearance', trace)
  const wasDark = await page.locator('html').evaluate(node => node.classList.contains('dark'))
  await keys(owner, ['space'])
  await page.waitForFunction(previous => document.documentElement.classList.contains('dark') !== previous, wasDark)
  accessibility.push(await interactiveAccessibility(page, 'menu-open'))
  screenshot(owner, `${prefix}-menu-focus`)
  await reach(page, owner, '.VPNavScreen a[href$="/guide/getting-started.html"]', trace, true)
  await keys(owner, ['Return'])
  await page.waitForURL(`${origin}${base}guide/getting-started.html`)
  const failed = accessibility.some(state => state.violations.some(item => ['serious', 'critical'].includes(item.impact)))
  return { status: failed ? 'accessibility-failed' : 'passed', trace, accessibility }
}

async function interactiveAccessibility(page, state) {
  await page.evaluate(axeSource)
  const result = await page.evaluate(() => window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] }))
  return { state, axeVersion: result.testEngine.version,
    violations: result.violations.map(item => ({ id: item.id, impact: item.impact, help: item.help,
      targets: item.nodes.map(node => node.target) })) }
}

async function structure(page) {
  return page.evaluate(() => ({
    language: document.documentElement.lang, main: document.querySelectorAll('main').length,
    headings: [...document.querySelectorAll('main h1,main h2,main h3,main h4')]
      .map(node => ({ level: Number(node.tagName[1]), text: node.textContent.replace(/\s*#\s*$/, '').trim() })),
    images: [...document.images].map(node => ({ alt: node.getAttribute('alt'), hidden: node.getAttribute('aria-hidden') })),
    firstParagraph: document.querySelector('main p')?.textContent.trim(),
    paragraphs: [...document.querySelectorAll('main p')].length,
    overflow: document.documentElement.scrollWidth > innerWidth + 1,
    cssWidth: innerWidth, dpr: devicePixelRatio
  }))
}

async function checkRoutes(page, owner, base, prefix) {
  const routes = []
  for (const theme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    for (const route of requiredPages) {
      await page.goto(origin + base + route, { waitUntil: 'networkidle' })
      const content = await structure(page)
      assert.equal(content.language, 'en-US')
      assert.equal(content.main, 1)
      assert.equal(content.headings.filter(heading => heading.level === 1).length, 1)
      assert.equal(content.overflow, false, `${prefix} ${route} page overflow`)
      assert(content.images.every(image => image.alt !== null))
      for (let index = 1; index < content.headings.length; index += 1) {
        assert(content.headings[index].level <= content.headings[index - 1].level + 1)
      }
      if (['index.html', 'guide/configuration.html'].includes(route)) {
        const label = route === 'index.html' ? 'home' : 'configuration'
        screenshot(owner, `${prefix}-${theme}-${label}`)
        await writeFile(`${output}/${prefix}-${theme}-${label}.aria.txt`, await page.locator('body').ariaSnapshot())
        await writeFile(`${output}/${prefix}-${theme}-${label}.reading.txt`, await page.locator('main').innerText())
        if (label === 'configuration') {
          await keys(owner, ['Next'])
          screenshot(owner, `${prefix}-${theme}-${label}-scrolled`)
        }
      }
      routes.push({ route, theme, ...content })
    }
  }
  return routes
}

async function artifactHashes() {
  const hashes = {}
  for (const artifact of artifacts) {
    for (const file of await filesUnder(artifact.directory)) {
      hashes[file] = createHash('sha256').update(await readFile(file)).digest('hex')
    }
  }
  return hashes
}

async function stopDisplay(display) {
  if (display.exitCode !== null || display.signalCode !== null) return
  const exited = once(display, 'exit')
  display.kill('SIGTERM')
  await exited
}

const display = await startDisplay()
let server, origin
const report = { checkedAt: new Date().toISOString(), display: ':103', displayPid: display.pid, output, browsers: [] }
try {
  ;({ server, origin } = await serveArtifacts())
  report.artifacts = await artifactHashes()
  if (browsers.includes('webkit')) {
    const launch = options('webkit')
    const help = spawnSync(launch.executablePath, ['--help'], { env: launch.env, encoding: 'utf8' })
    await writeFile(`${output}/webkit-help.txt`, `${help.stdout}\n${help.stderr}`)
    console.log(JSON.stringify({ webkitHelpExit: help.status, help: help.stdout }))
  }
  for (const name of browsers) {
    const row = { name, bases: [] }
    let browser
    try {
      browser = await playwright[name].launch(options(name))
      row.version = browser.version()
      for (const artifact of artifacts) {
        const context = await browser.newContext({ viewport: null, reducedMotion: 'reduce' })
        const page = await context.newPage()
        await page.goto(origin + artifact.base, { waitUntil: 'networkidle' })
        await page.bringToFront()
        const zoom = await setZoom(page, display)
        const label = artifact.base === '/' ? 'root' : 'subpath'
        const base = { base: artifact.base, ...zoom }
        row.bases.push(base)
        base.routes = await checkRoutes(page, display, artifact.base, `${name}-${label}`)
        base.keyboard = await checkKeyboard(page, display, artifact.base, `${name}-${label}`)
        console.log(JSON.stringify({ name, base: artifact.base, zoom: zoom.zoomed.dpr / zoom.baseline.dpr,
          exact200: zoom.exact200, routes: base.routes.length, keyboard: base.keyboard.status }))
        await context.close()
      }
      row.status = row.bases.every(base => base.exact200 && base.keyboard.status === 'passed') ? 'passed' : 'zoom-or-accessibility-unverified'
    } catch (error) {
      row.status = 'failed'
      row.error = error.stack
      console.log(JSON.stringify({ name, error: error.message }))
    } finally {
      if (browser) await browser.close()
      report.browsers.push(row)
    }
  }
} finally {
  server?.close()
  await stopDisplay(display)
  report.displayStopped = display.exitCode !== null || display.signalCode !== null
  report.artifactUnchanged = JSON.stringify(await artifactHashes()) === JSON.stringify(report.artifacts)
  await writeFile(`${output}/zoom-results.json`, `${JSON.stringify(report, null, 2)}\n`)
  console.log(JSON.stringify({ output, displayStopped: report.displayStopped }))
}
assert(report.artifactUnchanged, 'Built artifacts changed during verification')
assert(report.browsers.every(browser => browser.status === 'passed'), 'Exact zoom/keyboard acceptance has unverified rows')
