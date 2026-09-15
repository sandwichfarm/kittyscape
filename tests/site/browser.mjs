import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { artifacts, requiredPages, serveArtifacts } from './common.mjs'

const require = createRequire(import.meta.url)
const playwrightPath = process.env.PLAYWRIGHT_PATH || '/usr/lib/node_modules/playwright'
const playwright = require(playwrightPath)
const axePath = process.env.AXE_PATH || require.resolve('axe-core/axe.min.js')
const axeSource = await readFile(axePath, 'utf8')
const output = resolve(process.env.SITE_EVIDENCE_DIR || 'docs/.vitepress/evidence')
const browserNames = process.argv.length > 2 ? process.argv.slice(2) : ['chromium', 'firefox', 'webkit']
assert(browserNames.every(name => ['chromium', 'firefox', 'webkit'].includes(name)), 'Unknown browser name')
await mkdir(output, { recursive: true })
const { server, origin } = await serveArtifacts()
const report = { checkedAt: new Date().toISOString(), playwrightPath, axePath, browserNames, browsers: [], failures: [] }

async function checkStructure(page) {
  const structure = await page.evaluate(() => {
    const h1 = document.querySelectorAll('h1')
    const headings = [...document.querySelectorAll('main h1, main h2, main h3')].map(node => Number(node.tagName[1]))
    return {
      language: document.documentElement.lang,
      main: document.querySelectorAll('main').length,
      h1: h1.length,
      headings,
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
      imagesWithoutAlt: [...document.querySelectorAll('img')].filter(image => !image.hasAttribute('alt')).length
    }
  })
  assert.equal(structure.language, 'en-US')
  assert.equal(structure.main, 1)
  assert.equal(structure.h1, 1)
  assert.equal(structure.overflow, false, `Page overflow at ${page.url()}`)
  assert.equal(structure.imagesWithoutAlt, 0)
  for (let index = 1; index < structure.headings.length; index += 1) {
    assert(structure.headings[index] <= structure.headings[index - 1] + 1, 'Skipped heading level')
  }
}

async function checkAccessibility(page, row) {
  await page.evaluate(axeSource)
  const result = await page.evaluate(async () => window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] }))
  row.accessibilityRuns += 1
  row.axeVersion = result.testEngine.version
  const violations = result.violations.filter(item => ['serious', 'critical'].includes(item.impact))
  assert.deepEqual(violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) })), [])
  const contrasts = result.violations.filter(item => item.id === 'color-contrast')
  assert.deepEqual(contrasts, [], 'WCAG AA color contrast failure')
}

async function checkKeyboard(page, base) {
  await page.goto(origin + base, { waitUntil: 'networkidle' })
  await page.keyboard.press('Tab')
  assert.match(await page.locator(':focus').innerText(), /Skip to content/)
  const focus = await page.locator(':focus').evaluate(node => getComputedStyle(node).outlineStyle)
  assert.notEqual(focus, 'none', 'Skip link needs a visible focus indicator')
  await page.keyboard.press('Enter')
  assert.match(page.url(), /#VPContent$/)
  await page.keyboard.press('Tab')
  assert.match(await page.locator(':focus').innerText(), /Read the docs/)
  await page.keyboard.press('Enter')
  await page.waitForURL(`${origin}${base}docs/`)
  await page.locator('h1').filter({ hasText: 'Documentation' }).waitFor()
}

async function checkSearch(page, base) {
  await page.goto(origin + base, { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  const input = page.locator('#localsearch-input')
  await input.fill('fallback')
  const result = page.locator('.VPLocalSearchBox .result').first()
  await result.waitFor({ state: 'visible' })
  const href = await result.getAttribute('href')
  assert(href.startsWith(base), `Search escaped ${base}: ${href}`)
  await input.press('ArrowDown')
  await input.press('Enter')
  await page.waitForURL(url => url.pathname.startsWith(base) && url.pathname !== base)
  await page.waitForFunction(() => /fallback/i.test(document.querySelector('main')?.textContent || ''))
  assert.match(await page.locator('main').innerText(), /fallback/i)
}

async function checkLayouts(page, row, name, base) {
  for (const colorScheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme, reducedMotion: 'reduce' })
    for (const width of [320, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 })
      for (const route of requiredPages) {
        await page.goto(origin + base + route)
        await checkStructure(page)
        await checkAccessibility(page, row)
        if (['index.html', 'docs/guide/getting-started.html'].includes(route)) {
          await page.waitForLoadState('networkidle')
          const prefix = base === '/' ? 'root' : 'subpath'
          const label = route === 'index.html' ? 'home' : 'guide'
          await page.screenshot({ path: `${output}/${name}-${prefix}-${colorScheme}-${width}-${label}.png`, fullPage: true })
        }
        row.layoutChecks += 1
      }
    }
  }
}

async function checkMobileControls(page, base) {
  await page.setViewportSize({ width: 320, height: 950 })
  await page.goto(origin + base, { waitUntil: 'networkidle' })
  const menu = page.locator('.VPNavBarHamburger')
  for (let step = 0; step < 8; step += 1) {
    await page.keyboard.press('Tab')
    if (await menu.evaluate(node => node === document.activeElement)) break
  }
  assert(await menu.evaluate(node => node === document.activeElement), 'Mobile menu must be keyboard reachable')
  await page.keyboard.press('Enter')
  assert.equal(await menu.getAttribute('aria-expanded'), 'true')
  const toggle = page.locator('.VPNavScreen .VPSwitchAppearance')
  const wasDark = await page.locator('html').evaluate(node => node.classList.contains('dark'))
  await toggle.focus()
  await page.keyboard.press('Space')
  await page.waitForFunction(previous => document.documentElement.classList.contains('dark') !== previous, wasDark)
  const docs = page.locator('.VPNavScreen').getByRole('link', { name: 'Docs', exact: true })
  await docs.focus()
  await page.keyboard.press('Enter')
  await page.waitForURL(`${origin}${base}docs/`)
  await page.locator('h1').filter({ hasText: 'Documentation' }).waitFor()
}

/** A 1440px window at 200% page zoom has a 720 CSS-pixel layout viewport. */
async function checkZoom(browser, name, base) {
  const context = await browser.newContext({ viewport: { width: 720, height: 500 }, deviceScaleFactor: 2 })
  try {
    const page = await context.newPage()
    await page.goto(origin + base + 'docs/guide/configuration.html', { waitUntil: 'networkidle' })
    await checkStructure(page)
    await page.screenshot({ path: `${output}/${name}-${base === '/' ? 'root' : 'subpath'}-zoom200.png`, fullPage: true })
  } finally {
    await context.close()
  }
}

async function checkArtifact(browser, name, artifact, row) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  const page = await context.newPage()
  const failures = []
  const consoleReads = []
  page.on('pageerror', error => failures.push(`JavaScript: ${error.message}`))
  page.on('console', message => {
    if (message.type() !== 'error') return
    const source = `${page.url()} ${JSON.stringify(message.location())}`
    consoleReads.push(Promise.all(message.args().map(arg => arg.evaluate(value => String(value))))
      .then(values => failures.push(`Console at ${source}: ${values.join(' ')}`))
      .catch(() => failures.push(`Console at ${source}: ${message.text()}`)))
  })
  page.on('request', request => { if (!request.url().startsWith(origin)) failures.push(`Third-party request: ${request.url()}`) })
  page.on('response', response => { if (response.status() >= 400) failures.push(`HTTP ${response.status()}: ${response.url()}`) })
  for (const route of requiredPages) {
    await page.goto(origin + artifact.base + route)
    await checkStructure(page)
    await checkAccessibility(page, row)
    row.routes += 1
  }
  await checkLayouts(page, row, name, artifact.base)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await checkKeyboard(page, artifact.base)
  await checkSearch(page, artifact.base)
  await checkMobileControls(page, artifact.base)
  await Promise.all(consoleReads)
  assert.deepEqual(failures, [], `${name} request/console failures`)
  await context.close()
  await checkZoom(browser, name, artifact.base)
  const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 768, height: 1000 } })
  const readable = await noJs.newPage()
  await readable.goto(origin + artifact.base)
  await readable.getByRole('link', { name: 'Read the docs', exact: true }).click()
  await readable.waitForURL(`${origin}${artifact.base}docs/`)
  assert.match(await readable.locator('main').innerText(), /Documentation/)
  await noJs.close()
}

try {
  for (const name of browserNames) {
    let browser
    const row = { name, routes: 0, layoutChecks: 0, accessibilityRuns: 0 }
    try {
      const executablePath = name === 'webkit' ? process.env.WEBKIT_EXECUTABLE_PATH : undefined
      browser = await playwright[name].launch({ headless: true, executablePath })
      row.version = browser.version()
      for (const artifact of artifacts) await checkArtifact(browser, name, artifact, row)
      row.status = 'passed'
    } catch (error) {
      row.status = 'failed'
      row.error = error.message
      report.failures.push({ browser: name, error: error.message })
    } finally {
      if (browser) await browser.close()
      report.browsers.push(row)
      console.log(JSON.stringify(row))
    }
  }
} finally {
  server.close()
  await writeFile(`${output}/browser-results.json`, `${JSON.stringify(report, null, 2)}\n`)
}
assert.equal(report.failures.length, 0, 'Browser acceptance failed; see evidence/browser-results.json')
