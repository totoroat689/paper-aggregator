import type { APIRoute } from 'astro';
import { getServiceClient } from '../../lib/supabase.js';

// 한글 검색어 -> 영어 학술용어 확장 (+DB 캐시).
// 같은 검색어는 저장해두고 재사용 -> 두 번째부터 비용 0.
export const POST: APIRoute = async ({ request }) => {
  try {
    const { q } = await request.json();
    const query = (q || '').trim();
    if (!query) return json({ terms: [] });

    const db = getServiceClient();

    // 1) 캐시 확인
    const { data: cached } = await db
      .from('search_expansions')
      .select('terms')
      .eq('query', query)
      .single();
    if (cached?.terms) return json({ terms: cached.terms });

    // 2) Claude로 확장
    const apiKey = import.meta.env.ANTHROPIC_API_KEY;
    if (!apiKey) return json({ terms: [query] });

    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 200,
        messages: [{
          role: 'user',
          content: `한국어 검색어를 학술 논문 검색용 영어 용어로 확장해줘. 실제 논문에서 쓰이는 표현 3~5개를 JSON 배열로만 출력해. 다른 말 없이 배열만.\n\n검색어: ${query}`,
        }],
      }),
    });

    if (!resp.ok) return json({ terms: [query] });

    const data = await resp.json();
    const text = (data.content || []).map((b: any) => b.text || '').join('').trim();
    let terms: string[];
    try {
      terms = JSON.parse(text.replace(/```json|```/g, '').trim());
      if (!Array.isArray(terms) || terms.length === 0) terms = [query];
    } catch {
      terms = [query];
    }

    // 3) 캐시 저장
    await db.from('search_expansions').insert({ query, terms });

    return json({ terms });
  } catch {
    return json({ terms: [] });
  }
};

function json(obj: any, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
