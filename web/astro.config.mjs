import { defineConfig } from 'astro/config';
import vercel from '@astrojs/vercel';

// SEO 핵심: 페이지를 서버에서 미리 만들어 완성된 HTML을 보냄
export default defineConfig({
  output: 'server',
  adapter: vercel({
    webAnalytics: { enabled: true },
  }),
  site: 'https://example.vercel.app',
});
