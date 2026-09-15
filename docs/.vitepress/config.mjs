import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'en-US',
  title: 'Kittyscape',
  description: 'Directory-aware backgrounds for kitty, with your image settings intact.',
  lastUpdated: false,
  appearance: true,
  cleanUrls: false,
  rewrites: {
    'guide/:slug*': 'docs/guide/:slug*',
    'reference/:slug*': 'docs/reference/:slug*',
    'contributing/:slug*': 'docs/contributing/:slug*',
    'development/:slug*': 'docs/development/:slug*',
    'releases.md': 'docs/releases.md'
  },
  transformHead: ({ siteData }) => [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${siteData.base}cat-mark.svg` }],
    ['meta', { name: 'theme-color', content: '#f8f7f2' }]
  ],
  themeConfig: {
    logo: { src: '/cat-mark.svg', alt: '' },
    nav: [
      { text: 'Docs', link: '/docs/' },
      { text: 'Compatibility', link: '/docs/reference/compatibility' }
    ],
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Getting started', link: '/docs/guide/getting-started' },
          { text: 'Installation', link: '/docs/guide/installation' },
          { text: 'Configuration', link: '/docs/guide/configuration' },
          { text: 'Shells', link: '/docs/guide/shells' },
          { text: 'Kitty settings', link: '/docs/guide/kitty-settings' },
          { text: 'Troubleshooting', link: '/docs/guide/troubleshooting' },
          { text: 'Uninstall & rollback', link: '/docs/guide/uninstall' }
        ]
      },
      {
        text: 'Reference',
        items: [
          { text: 'Compatibility', link: '/docs/reference/compatibility' },
          { text: 'Configuration fields', link: '/docs/reference/configuration' },
          { text: 'Actions', link: '/docs/reference/actions' }
        ]
      },
      {
        text: 'Project',
        items: [
          { text: 'Contributing', link: '/docs/contributing/' },
          { text: 'Runtime findings', link: '/docs/development/compatibility-findings' },
          { text: 'Website & assets', link: '/docs/development/website' },
          { text: 'Release checks', link: '/docs/development/release-checklist' },
          { text: 'Release notes', link: '/docs/releases' }
        ]
      }
    ],
    search: { provider: 'local', options: { disableQueryPersistence: true } },
    outline: { level: [2, 3], label: 'On this page' },
    docFooter: { prev: 'Previous', next: 'Next' }
  }
})
