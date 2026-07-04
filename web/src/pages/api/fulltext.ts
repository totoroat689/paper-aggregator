import type { APIRoute } from 'astro';
import { supabase } from '../../lib/supabase.js';
import { extractText, getDocumentProxy } from 'unpdf';

// 원문 가져오기 (테스트 단계: 번역 없이 원어 그대로 반환)
// 흐름: 논문의 fulltext_url 접속 -> PDF면 텍스트 추출, 웹페이지면 본문만 추려냄

function htmlToText(html: string): string {
  let s = html;
  // 본문 아닌 영역 제거
  s = s.replace(/<script[\s\S]*?<\/script>/gi, ' ')
       .replace(/<style[\s\S]*?<\/style>/gi, ' ')
       .replace(/<nav[\s\S]*?<\/nav>/gi, ' ')
       .replace(/<header[\s\S]*?<\/header>/gi, ' ')
       .replace(/<footer[\s\S]*?<\/footer>/gi, ' ')
       .replace(/<aside[\s\S]*?<\/aside>/gi, ' ');
  // 논문 사이트는 보통 <article>이나 main에 본문이 있음 — 있으면 그 부분만
  const article = s.match(/<article[\s\S]*?<\/article>/i) || s.match(/<main[\s\S]*?<\/main>/i);
  if (article) s = article[0];
  // 문단 경계 유지하며 태그 제거
  s = s.replace(/<\/(p|div|h[1-6]|li|section|tr)>/gi, '\n')
       .replace(/<br\s*\/?>/gi, '\n')
       .replace(/<[^>]+>/g, ' ');
  // HTML 특수문자 최소 복원
  s = s.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
       .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  return s;
}

function clean(t: string): string {
  return t
    .replace(/[ \t]+/g, ' ')
    .replace(/ *\n */g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

const j = (obj: object, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json' } });

export const POST: APIRoute = async ({ request }) => {
  try {
    const { id } = await request.json();
    if (!id) return j({ error: '논문 id가 필요해요' }, 400);

    const { data: paper } = await supabase
      .from('papers')
      .select('id, fulltext_url, doi')
      .eq('id', id)
      .single();
    if (!paper) return j({ error: '논문을 찾을 수 없어요' }, 404);

    const url = paper.fulltext_url || (paper.doi ? `https://doi.org/${paper.doi}` : null);
    if (!url) return j({ error: '원문 링크가 없는 논문이에요' }, 422);

    const resp = await fetch(url, {
      redirect: 'follow',
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; ResearchArchiveBot/1.0)',
        'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8',
      },
      signal: AbortSignal.timeout(20000),
    });
    if (!resp.ok) return j({ error: `원문 사이트가 접근을 거부했어요 (응답 ${resp.status})` }, 422);

    const ct = (resp.headers.get('content-type') || '').toLowerCase();
    let text = '';
    let kind = 'html';

    if (ct.includes('pdf') || url.toLowerCase().split('?')[0].endsWith('.pdf')) {
      const buf = new Uint8Array(await resp.arrayBuffer());
      if (buf.length > 15 * 1024 * 1024) return j({ error: '파일이 너무 커요 (15MB 초과)' }, 422);
      const pdf = await getDocumentProxy(buf);
      const r = await extractText(pdf, { mergePages: true });
      text = typeof r.text === 'string' ? r.text : String(r.text || '');
      kind = 'pdf';
    } else {
      const html = await resp.text();
      text = htmlToText(html);
    }

    text = clean(text);
    if (text.length < 600) {
      return j({ error: '본문을 추출하지 못했어요. 사이트가 자동 접근을 막고 있거나 본문이 없는 페이지예요.', kind }, 422);
    }
    if (text.length > 60000) {
      text = text.slice(0, 60000) + '\n\n…(이하 생략 — 테스트 표시 한도)';
    }
    return j({ text, kind, chars: text.length });
  } catch (e: any) {
    const msg = e?.name === 'TimeoutError' ? '원문 사이트 응답이 너무 느려요 (20초 초과)' : (e?.message || '알 수 없는 오류');
    return j({ error: '가져오기 실패: ' + msg }, 500);
  }
};
