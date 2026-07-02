import type { APIRoute } from 'astro';
import { supabase, getServiceClient } from '../../lib/supabase.js';

// 초록을 한국어로 번역해서 돌려주고, 결과를 DB에 저장(캐시).
// 같은 논문을 다음에 열면 저장된 걸 바로 씀 -> 비용 한 번만.
export const POST: APIRoute = async ({ request }) => {
  try {
    const { id } = await request.json();
    if (!id) return json({ error: 'id 없음' }, 400);

    // 이미 번역돼 있으면 그대로 반환 (재요청 시 공짜)
    const { data: paper } = await supabase
      .from('papers')
      .select('abstract_en, abstract_ko')
      .eq('id', id)
      .single();

    if (!paper) return json({ error: '논문 없음' }, 404);
    if (paper.abstract_ko) return json({ abstract_ko: paper.abstract_ko });
    if (!paper.abstract_en) return json({ error: '번역할 초록이 없습니다.' }, 400);

    const apiKey = import.meta.env.ANTHROPIC_API_KEY;
    if (!apiKey) return json({ error: '번역 기능이 아직 설정되지 않았습니다.' }, 500);

    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 1024,
        messages: [{
          role: 'user',
          content: `다음 학술 논문 초록을 자연스러운 한국어로 번역해줘. 전문용어는 쉽게 풀어주되 정확하게. 번역문만 출력해:\n\n${paper.abstract_en}`,
        }],
      }),
    });

    if (!resp.ok) return json({ error: '번역 요청이 실패했습니다.' }, 502);

    const data = await resp.json();
    const abstract_ko = (data.content || []).map((b: any) => b.text || '').join('').trim();
    if (!abstract_ko) return json({ error: '번역 결과가 비었습니다.' }, 502);

    // 캐시 저장 (서버 전용 쓰기 연결)
    await getServiceClient()
      .from('papers')
      .update({ abstract_ko, abstract_ko_generated_at: new Date().toISOString() })
      .eq('id', id);

    return json({ abstract_ko });
  } catch (e) {
    return json({ error: '오류가 발생했습니다.' }, 500);
  }
};

function json(obj: any, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}
