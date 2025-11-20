import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  build: {
    outDir: 'build',
    emptyOutDir: true,
    rollupOptions: {
      input: 'index.html'
    }
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5006'
    }
  }
})
