import {defineConfig} from 'vite';
export default defineConfig({build:{rollupOptions:{output:{manualChunks:{charts:['lightweight-charts'],workspace:['react-grid-layout','react-resizable']}}}}});
