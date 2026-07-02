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
  observational: { label: '관찰연구', fg: '#8A6D1F', bg: '#F5EFDD', strength: 0.5 },
  review: { label: '리뷰', fg: '#5F5E5A', bg: '#F1EFE8', strength: 0.4 },
  other: { label: '기타', fg: '#888780', bg: '#F1EFE8', strength: 0.2 },
  unclassified: { label: '미분류', fg: '#A1A1AA', bg: '#F4F4F5', strength: 0.2 },
};

// 26개 분야 영어 -> 한글
export const CATEGORY_KO = {
  'Agricultural and Biological Sciences': '농업·생물학',
  'Arts and Humanities': '예술·인문학',
  'Biochemistry, Genetics and Molecular Biology': '생화학·유전·분자생물학',
  'Business, Management and Accounting': '경영·회계',
  'Chemical Engineering': '화학공학', 'Chemistry': '화학',
  'Computer Science': '컴퓨터과학', 'Decision Sciences': '의사결정학',
  'Earth and Planetary Sciences': '지구·행성과학',
  'Economics, Econometrics and Finance': '경제·금융',
  'Energy': '에너지', 'Engineering': '공학', 'Environmental Science': '환경과학',
  'Immunology and Microbiology': '면역·미생물학', 'Materials Science': '재료공학',
  'Mathematics': '수학', 'Medicine': '의학', 'Neuroscience': '신경과학',
  'Nursing': '간호학', 'Pharmacology, Toxicology and Pharmaceutics': '약리·독성학',
  'Physics and Astronomy': '물리·천문학', 'Psychology': '심리학',
  'Social Sciences': '사회과학', 'Veterinary': '수의학', 'Dentistry': '치의학',
  'Health Professions': '보건의료', 'Biology': '생물학', 'Sociology': '사회과학',
  'Business': '경영·회계', 'Political Science': '정치학', 'Geography': '지리학',
  'Geology': '지질학', 'Art': '예술·인문학', 'History': '예술·인문학',
  'Philosophy': '예술·인문학', 'Education': '교육학', 'Law': '법학',
  'Linguistics': '언어학', 'Agricultural and Food Sciences': '농업·식품과학',
};

export function categoryKo(name) {
  if (!name) return '기타';
  return CATEGORY_KO[name] || name;
}

// 국가 코드 -> 한글
export const COUNTRY_LABELS = {
  US: '미국', GB: '영국', DE: '독일', FR: '프랑스', CA: '캐나다',
  AU: '호주', JP: '일본', CN: '중국', KR: '한국', NL: '네덜란드',
  IT: '이탈리아', ES: '스페인', SE: '스웨덴', CH: '스위스', AT: '오스트리아',
};

export function countryName(code) {
  return COUNTRY_LABELS[code] || code;
}
