import { createClient } from '@supabase/supabase-js';

// 화면 읽기용 (anon 키, 공개돼도 안전 - 읽기 전용)
const SUPABASE_URL = import.meta.env.PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.PUBLIC_SUPABASE_ANON_KEY;

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// 서버 전용 쓰기 연결 (번역 결과 저장 등).
// service_role 키는 서버 안에서만 쓰이고 화면(브라우저)에는 절대 노출되지 않습니다.
export function getServiceClient() {
  const key = import.meta.env.SUPABASE_SERVICE_KEY;
  if (!key) return supabase; // 키 없으면 읽기용으로 대체(저장은 실패하지만 앱은 안 죽음)
  return createClient(SUPABASE_URL, key);
}

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
