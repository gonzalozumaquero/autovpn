// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isDev = mode === 'development'

  return {
    plugins: [react()],
    base: '/',
    envPrefix: 'VITE_', // solo variables que empiecen por VITE_ serán expuestas al cliente

    server: {
      host: '127.0.0.1',
      port: 3000,
      strictPort: true,
      open: true,
      // Proxy al backend local del instalador (FastAPI/Express)
      proxy: {
        '/install': {
          target: 'http://localhost:4000',
          changeOrigin: true,
          // WebSocket / SSE funcionan bien sin ws:true; actívalo si tu backend usa WS puros:
          // ws: true,
          // rewrite opcional si tu backend no usa el prefijo /install:
          // rewrite: (path) => path.replace(/^\/install/, '')
        },
      },
    },

    // Para `vite preview` (build ya hecho)
    preview: {
      host: '127.0.0.1',
      port: 5050,
      strictPort: true,
      proxy: {
        '/install': {
          target: 'http://localhost:4000',
          changeOrigin: true,
        },
      },
    },

    build: {
      sourcemap: isDev,
      outDir: 'dist',
      emptyOutDir: true,
      target: 'es2018',
    },

    // Resoluciones/alias opcionales
    // resolve: {
    //   alias: { '@': '/src' },
    // },
  }
})

