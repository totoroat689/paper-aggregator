import type { APIRoute } from 'astro';
import { supabase } from '../lib/supabase.js';

// 검색엔진에게 모든 페이지 주소와 수정일을 알려주는 지도(XML 사이트맵)
export const GET: APIRoute = async ({ site }) => {
  const base = (site?.toString() || 'https://paper-aggregator.vercel.app').replace(/\/$/, '');

  const [papersRes, postsRes] = await Promise.all([
    supabase
      .from('papers')
      .select('id, last_updated_at, first_seen_at')
      .eq('is_retracted', false)
      .order('publication_date', { ascending: false })
      .limit(45000),
    supabase
      .from('posts')
      .select('id, created_at')
      .order('created_at', { ascending: false })
      .limit(2000),
  ]);

  const day = (d: string | null) => (d ? String(d).slice(0, 10) : null);
  const entry = (loc: string, lastmod: string | null) =>
    `  <url><loc>${loc}</loc>${lastmod ? `<lastmod>${lastmod}</lastmod>` : ''}</url>`;

  const staticUrls = [
    entry(`${base}/`, null),
    entry(`${base}/about`, null),
    entry(`${base}/board`, null),
  ];
  const paperUrls = (papersRes.data || []).map((p) =>
    entry(`${base}/paper/${p.id}`, day(p.last_updated_at || p.first_seen_at)),
  );
  const postUrls = (postsRes.data || []).map((p) =>
    entry(`${base}/board/${p.id}`, day(p.created_at)),
  );

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${[...staticUrls, ...paperUrls, ...postUrls].join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=86400',
    },
  });
};
