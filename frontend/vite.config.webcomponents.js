import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          // Treat all tags starting with 'bgc-' as custom elements
          isCustomElement: (tag) => tag.startsWith('bgc-')
        }
      }
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/web-components.ts'),
      name: 'BGCViewerComponents',
      formats: ['es', 'umd'],
      fileName: (format) => `bgc-viewer-components.${format}.js`
    },
    rollupOptions: {
      // Externalize dependencies that shouldn't be bundled
      external: ['d3'],
      output: {
        // Provide global variables to use in the UMD build
        globals: {
          d3: 'd3'
        }
      }
    },
    outDir: 'dist/web-components'
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify('production')
  }
})
