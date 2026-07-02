import { createClient } from '@supabase/supabase-js';

// 키는 Vercel 환경변수에서 읽어옵니다 (코드에 직접 안 박음).
// anon 키는 읽기 전용이라 공개돼도 안전하지만, 관리 편의상 환경변수로 둡니다.
const SUPABASE_URL = import.meta.env.PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// 연구유형 코드 -> 한글 이름 + 색상
export const STUDY_TYPE_LABELS = {
  meta_analysis: { label: '메타분석', fg: '#085041', bg: '#E1F5EE', strength: 0.95 },
  rct: { label: '무작위대조실험', fg: '#185FA5', bg: '#E6F1FB', strength: 0.85 },
  experimental_likely: { label: '실험연구', fg: '#3F6B5E', bg: '#E1F0EA', strength: 0.65 },
  review: { label: '리뷰', fg: '#5F5E5A', bg: '#F1EFE8', strength: 0.4 },
  unclassified: { label: '미분류', fg: '#888780', bg: '#F1EFE8', strength: 0.25 },
};

// 국가 코드 -> 한글
export const COUNTRY_LABELS = {
  US: '미국', GB: '영국', DE: '독일', FR: '프랑스', CA: '캐나다',
  AU: '호주', JP: '일본', CN: '중국', KR: '한국', NL: '네덜란드',
  IT: '이탈리아', ES: '스페인', SE: '스웨덴', CH: '스위스', AT: '오스트리아',
};

export function countryName(code) {
  return COUNTRY_LABELS[code] || code;
}
