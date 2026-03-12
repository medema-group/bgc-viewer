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
  server: {
    port: 5174,
    fs: {
      // Allow serving files from the demos directory (for data files)
      allow: ['..']
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
})
