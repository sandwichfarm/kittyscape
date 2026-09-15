import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'en-US',
  title: 'Kittyscape',
  description: 'Directory-aware backgrounds for kitty, with your image settings intact.',
  lastUpdated: false,
  appearance: true,
  cleanUrls: false,
  transformHead: ({ siteData }) => [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${siteData.base}cat-mark.svg` }],
    ['meta', { name: 'theme-color', content: '#f8f7f2' }]
  ],
  themeConfig: {
    logo: { src: '/cat-mark.svg', alt: '' },
    nav: [
      { text: 'Docs', link: '/guide/getting-started' },
      { text: 'Compatibility', link: '/reference/compatibility' }
    ],
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Getting started', link: '/guide/getting-started' },
          { text: 'Installation', link: '/guide/installation' },
          { text: 'Configuration', link: '/guide/configuration' },
          { text: 'Shells', link: '/guide/shells' },
          { text: 'Kitty settings', link: '/guide/kitty-settings' },
          { text: 'Troubleshooting', link: '/guide/troubleshooting' },
          { text: 'Uninstall & rollback', link: '/guide/uninstall' }
        ]
      },
      {
        text: 'Reference',
        items: [
          { text: 'Compatibility', link: '/reference/compatibility' },
          { text: 'Configuration fields', link: '/reference/configuration' },
          { text: 'Actions', link: '/reference/actions' }
        ]
      },
      {
        text: 'Project',
        items: [
          { text: 'Contributing', link: '/contributing/' },
          { text: 'Runtime findings', link: '/development/compatibility-findings' },
          { text: 'Website & assets', link: '/development/website' },
          { text: 'Release checks', link: '/development/release-checklist' },
          { text: 'Release notes', link: '/releases' }
        ]
      }
    ],
    search: { provider: 'local', options: { disableQueryPersistence: true } },
    outline: { level: [2, 3], label: 'On this page' },
    docFooter: { prev: 'Previous', next: 'Next' }
  }
})
