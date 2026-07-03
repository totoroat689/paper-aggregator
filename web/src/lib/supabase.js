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

// 연구유형 코드 -> 한글 이름 + 색상 (배지: 색조 또렷하게)
export const STUDY_TYPE_LABELS = {
  meta_analysis: { label: '메타분석', fg: '#0A5C4A', bg: '#D6F0E7', strength: 0.95 },
  rct: { label: '무작위대조실험', fg: '#1A5DA8', bg: '#DCEBFB', strength: 0.85 },
  experimental_likely: { label: '실험연구', fg: '#2E7D64', bg: '#D9F0E5', strength: 0.65 },
  observational: { label: '관찰연구', fg: '#9A6A15', bg: '#F6EACE', strength: 0.5 },
  review: { label: '리뷰', fg: '#7A5AA6', bg: '#EDE6F7', strength: 0.4 },
  other: { label: '기타', fg: '#6B6A64', bg: '#ECEBE6', strength: 0.2 },
  unclassified: { label: '미분류', fg: '#71717A', bg: '#EAEAEC', strength: 0.2 },
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


// 분야별 파스텔 색 (계열별로 묶어서 조화롭게)
const FIELD_PASTEL = {
  // 의학·보건 계열: 연분홍/연코랄
  '의학': { fg: '#A34A5E', bg: '#FBE8EC' },
  '간호학': { fg: '#A34A5E', bg: '#FBE8EC' },
  '치의학': { fg: '#A85A4A', bg: '#FAEAE5' },
  '보건의료': { fg: '#A85A4A', bg: '#FAEAE5' },
  '약리·독성학': { fg: '#96548C', bg: '#F6E9F4' },
  // 생명과학 계열: 연그린
  '생화학·유전·분자생물학': { fg: '#3E7D4F', bg: '#E3F2E6' },
  '면역·미생물학': { fg: '#3E7D4F', bg: '#E3F2E6' },
  '농업·생물학': { fg: '#5B7E3A', bg: '#EBF2DF' },
  '생물학': { fg: '#3E7D4F', bg: '#E3F2E6' },
  '농업·식품과학': { fg: '#5B7E3A', bg: '#EBF2DF' },
  '수의학': { fg: '#5B7E3A', bg: '#EBF2DF' },
  '신경과학': { fg: '#7A5AA6', bg: '#EFE8F8' },
  // 자연과학 계열: 연블루/연보라
  '물리·천문학': { fg: '#5A5AA8', bg: '#EAEAF9' },
  '화학': { fg: '#4A6FA5', bg: '#E6EEF8' },
  '수학': { fg: '#5A5AA8', bg: '#EAEAF9' },
  '지구·행성과학': { fg: '#4A7A96', bg: '#E4F0F5' },
  '환경과학': { fg: '#3E8578', bg: '#E1F1EE' },
  '에너지': { fg: '#96742E', bg: '#F7EFDD' },
  // 공학 계열: 연슬레이트
  '공학': { fg: '#5F6E85', bg: '#EAEEF4' },
  '화학공학': { fg: '#5F6E85', bg: '#EAEEF4' },
  '재료공학': { fg: '#5F6E85', bg: '#EAEEF4' },
  '컴퓨터과학': { fg: '#4A6FA5', bg: '#E6EEF8' },
  // 사회과학 계열: 연노랑/연민트
  '심리학': { fg: '#B07A2A', bg: '#FBF0DC' },
  '사회과학': { fg: '#A8842E', bg: '#F8F1DE' },
  '경제·금융': { fg: '#3E8578', bg: '#E1F1EE' },
  '경영·회계': { fg: '#3E8578', bg: '#E1F1EE' },
  '의사결정학': { fg: '#5F6E85', bg: '#EAEEF4' },
  '정치학': { fg: '#A8842E', bg: '#F8F1DE' },
  '교육학': { fg: '#B07A2A', bg: '#FBF0DC' },
  '법학': { fg: '#A8842E', bg: '#F8F1DE' },
  '지리학': { fg: '#4A7A96', bg: '#E4F0F5' },
  '지질학': { fg: '#4A7A96', bg: '#E4F0F5' },
  // 인문·예술 계열: 연라벤더
  '예술·인문학': { fg: '#96548C', bg: '#F6E9F4' },
  '언어학': { fg: '#96548C', bg: '#F6E9F4' },
};

export function fieldColor(nameKo) {
  return FIELD_PASTEL[nameKo] || { fg: '#71717A', bg: '#EFEFF1' };
}

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
