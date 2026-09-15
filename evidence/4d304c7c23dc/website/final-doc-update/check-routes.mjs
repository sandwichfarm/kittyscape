import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { readFile, writeFile } from 'node:fs/promises'
import { serveArtifacts, artifacts } from '/home/sandwich/Develop/kittyscape/tests/site/common.mjs'

const require = createRequire(import.meta.url)
const playwright = require('/home/sandwich/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core')
const axeSource = await readFile('/home/sandwich/.npm/_npx/0f94ee7615faf582/node_modules/axe-core/axe.min.js', 'utf8')
const output = '/tmp/kittyscape-final-frontend-scoped-redraw'
const report = { checkedAt: new Date().toISOString(), browsers: [], failures: [] }
const routes = [
  {
    path: 'contributing/index.html',
    query: 'unit suite',
    resultPath: 'contributing/',
    text: /This runs scripts\/check\.py, the unit suite, and the installation suite\./,
    absent: /\b\d+ unit tests and \d+ installation tests\b/
  },
  {
    path: 'development/compatibility-findings.html',
    query: 'explicit screen damage',
    resultPath: 'development/compatibility-findings',
    text: /Kittyscape refreshes only that OS window’s active pane after a successful write,\s+so an unfocused window repaints/
  }
]
const { server, origin } = await serveArtifacts()

try {
  for (const name of ['chromium', 'firefox', 'webkit']) {
    const browser = await playwright[name].launch({
      headless: true,
      executablePath: name === 'webkit' ? '/tmp/kittyscape-webkit-wxpv4ff1/webkit-launch.sh' : undefined
    })
    const row = { name, version: browser.version(), layoutChecks: 0, accessibilityRuns: 0, searchFlows: 0, cases: [] }
    const errors = []
    try {
      for (const { base } of artifacts) {
        for (const colorScheme of ['light', 'dark']) {
          const context = await browser.newContext({ colorScheme, reducedMotion: 'reduce' })
          const page = await context.newPage()
          page.on('pageerror', error => errors.push(error.message))
          page.on('response', response => {
            if (response.status() >= 400) errors.push(`${response.status()}: ${response.url()}`)
          })
          page.on('request', request => {
            if (!request.url().startsWith(origin)) errors.push(`External request: ${request.url()}`)
          })
          for (const width of [320, 768, 1440]) {
            await page.setViewportSize({ width, height: 1000 })
            for (const route of routes) {
              await page.goto(`${origin}${base}${route.path}`, { waitUntil: 'networkidle' })
              const mainText = await page.locator('main').innerText()
              assert.match(mainText, route.text)
              if (route.absent) assert.doesNotMatch(mainText, route.absent)
              assert.equal(await page.locator('h1').count(), 1)
              assert.equal(await page.locator('main').count(), 1)
              assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
              assert.equal(await page.locator('html').evaluate(node => node.classList.contains('dark')), colorScheme === 'dark')
              await page.evaluate(axeSource)
              const axe = await page.evaluate(() => window.axe.run(document, {
                runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']
              }))
              assert.deepEqual(axe.violations.map(item => ({ id: item.id, impact: item.impact })), [])
              row.axeVersion = axe.testEngine.version
              row.layoutChecks += 1
              row.accessibilityRuns += 1
              if (width === 320 && colorScheme === 'light') {
                const label = route.path.split('/')[0]
                await page.screenshot({ path: `${output}/${name}-${base === '/' ? 'root' : 'subpath'}-${label}.png` })
              }
              await page.getByRole('button', { name: 'Search', exact: true }).click()
              await page.locator('#localsearch-input').fill(route.query)
              const match = page.locator(`.VPLocalSearchBox .result[href*="${route.resultPath}"]`).first()
              await match.waitFor({ state: 'visible' })
              assert((await match.getAttribute('href')).startsWith(base))
              await match.click()
              await page.waitForFunction(() => !document.querySelector('.VPLocalSearchBox'))
              assert.match(await page.locator('main').innerText(), route.text)
              row.searchFlows += 1
              row.cases.push({ base, colorScheme, width, route: route.path, layout: 'passed', axeViolations: 0, search: 'passed' })
            }
          }
          await context.close()
        }
      }
      assert.deepEqual(errors, [])
      row.status = 'passed'
    } catch (error) {
      row.status = 'failed'
      row.error = error.stack
      report.failures.push({ browser: name, error: error.message })
    } finally {
      await browser.close()
      report.browsers.push(row)
      console.log(JSON.stringify({ ...row, cases: row.cases.length }))
    }
  }
} finally {
  await new Promise(resolve => server.close(resolve))
  await writeFile(`${output}/route-results.json`, JSON.stringify(report, null, 2) + '\n')
}
assert.deepEqual(report.failures, [])
