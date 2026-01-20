import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "BGC Viewer",
  description: "Interactive documentation and component demos for BGC Viewer",
  // Use /bgc-viewer/ for GitHub Pages deployment, / for local preview
  base: process.env.VITEPRESS_BASE || '/',
  
  // Ignore dead links for localhost URLs and external links during build
  ignoreDeadLinks: [
    // Ignore localhost links (development servers)
    /^https?:\/\/localhost/,
    // Ignore configuration.md which doesn't exist yet
    /\.\/configuration$/,
    // Ignore API index link
    /\.\.\/api\/index$/,
  ],
  
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'Components', link: '/components/track-viewer' },
      { text: 'API Reference', link: '/api/overview' }
    ],

    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Getting Started', link: '/guide/getting-started' },
          { text: 'Installation', link: '/guide/installation' },
          { text: 'Quick Start', link: '/guide/quick-start' }
        ]
      },
      {
        text: 'Components',
        items: [
          { text: 'Track Viewer', link: '/components/track-viewer' },
          { text: 'Web Components', link: '/components/web-components' }
        ]
      },
      {
        text: 'REST API',
        items: [
          { text: 'Overview', link: '/api/overview' },
          { text: 'Data Loading', link: '/api/data-loading' },
          { text: 'Records & Features', link: '/api/records' },
          { text: 'Database', link: '/api/database' },
          { text: 'File System (Local)', link: '/api/filesystem' }
        ]
      },
      {
        text: 'Examples',
        items: [
          { text: 'Basic Usage', link: '/examples/basic' },
          { text: 'Interactive Demo', link: '/examples/interactive' }
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/medema-group/bgc-viewer' }
    ],

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2026 BGC Viewer Contributors'
    }
  },

  vite: {
    resolve: {
      alias: {
        '@': '/src'
      }
    }
  }
})
