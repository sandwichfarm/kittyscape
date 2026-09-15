import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { readFile, writeFile } from 'node:fs/promises'
import { serveArtifacts, artifacts } from '/home/sandwich/Develop/kittyscape/tests/site/common.mjs'

const require = createRequire(import.meta.url)
const playwright = require('/home/sandwich/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core')
const axeSource = await readFile('/home/sandwich/.npm/_npx/0f94ee7615faf582/node_modules/axe-core/axe.min.js', 'utf8')
const output = '/tmp/kittyscape-final-frontend-17c35e39'
const report = { checkedAt: new Date().toISOString(), browsers: [], failures: [] }
const { server, origin } = await serveArtifacts()

try {
  for (const name of ['chromium', 'firefox', 'webkit']) {
    const browser = await playwright[name].launch({
      headless: true,
      executablePath: name === 'webkit' ? '/tmp/kittyscape-webkit-wxpv4ff1/webkit-launch.sh' : undefined
    })
    const row = { name, version: browser.version(), layoutChecks: 0, accessibilityRuns: 0, searchFlows: 0 }
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
            await page.goto(`${origin}${base}contributing/index.html`, { waitUntil: 'networkidle' })
            assert.match(await page.locator('main').innerText(), /78 unit tests and 35 installation tests/)
            assert.doesNotMatch(await page.locator('main').innerText(), /77 unit tests/)
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
              await page.screenshot({ path: `${output}/${name}-${base === '/' ? 'root' : 'subpath'}-count.png` })
            }
          }
          if (colorScheme === 'light') {
            await page.getByRole('button', { name: 'Search', exact: true }).click()
            await page.locator('#localsearch-input').fill('78 unit tests')
            const match = page.locator('.VPLocalSearchBox .result[href*="contributing/"]').first()
            await match.waitFor({ state: 'visible' })
            assert((await match.getAttribute('href')).startsWith(base))
            await match.click()
            await page.waitForFunction(() => !document.querySelector('.VPLocalSearchBox'))
            assert.match(await page.locator('main').innerText(), /78 unit tests and 35 installation tests/)
            row.searchFlows += 1
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
      console.log(JSON.stringify(row))
    }
  }
} finally {
  await new Promise(resolve => server.close(resolve))
  await writeFile(`${output}/contributing-results.json`, JSON.stringify(report, null, 2) + '\n')
}
assert.deepEqual(report.failures, [])
