import type { APIRoute } from 'astro';
import { supabase } from '../lib/supabase.js';

// 검색엔진에게 모든 논문 페이지 주소를 알려주는 지도(XML 사이트맵).
// SEO 필수: 이게 없으면 구글이 개별 페이지를 못 찾음.
export const GET: APIRoute = async ({ site }) => {
  const base = site?.toString().replace(/\/$/, '') || '';

  const { data: papers } = await supabase
    .from('papers')
    .select('id')
    .eq('is_retracted', false)
    .order('publication_date', { ascending: false })
    .limit(5000);

  const urls = (papers || [])
    .map((p) => `  <url><loc>${base}/paper/${p.id}</loc></url>`)
    .join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${base}/</loc></url>
${urls}
</urlset>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
