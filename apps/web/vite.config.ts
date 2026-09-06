import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Vite 在 Docker 容器中运行，需通过 compose 服务名访问 API。
        target: 'http://api:8000',
        changeOrigin: true,
      },
    },
  },
})
