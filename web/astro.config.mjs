import { defineConfig } from 'astro/config';
import vercel from '@astrojs/vercel';

// SEO 핵심: 페이지를 서버에서 미리 만들어 완성된 HTML을 보냄
export default defineConfig({
  output: 'server',
  adapter: vercel({
    webAnalytics: { enabled: true },
  }),
  // 화면 전환 속도: 링크에 손을 올리는(모바일은 터치 시작) 순간 다음 페이지를 미리 받아옴
  prefetch: {
    prefetchAll: true,
    defaultStrategy: 'hover',
  },
  site: 'https://paper-aggregator.vercel.app',
});
