import { defineConfig } from 'astro/config';
import vercel from '@astrojs/vercel/serverless';

// SEO 핵심: 페이지를 서버에서 미리 만들어 완성된 HTML을 보냄
// (Flare[V]의 '빈 껍데기' 문제가 구조적으로 재발하지 않음)
export default defineConfig({
  output: 'server',
  adapter: vercel({
    webAnalytics: { enabled: true },
  }),
  site: 'https://example.vercel.app',
});
