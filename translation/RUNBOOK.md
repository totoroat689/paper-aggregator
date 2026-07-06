# 한글화 작업 지침서 (Claude/Sonnet 실행용)

사용자가 **"한글화 이어서 진행해줘"**(또는 비슷한 요청)라고 하면, 아래 절차를 그대로 반복 실행한다.
질문하지 말고 바로 시작한다. 작업 상태는 전부 DB가 기억하므로(번역 안 된 것만 자동 추출) 이어받기에 아무 준비도 필요 없다.

## 원리 (1분 요약)
- Claude는 Supabase에 직접 접속 불가. GitHub은 가능. GitHub Actions는 Supabase 접속 가능.
- 그래서 저장소가 우체통: `translation/request.json` push → Actions가 번역거리 추출(`pending.json`) →
  Claude가 채팅에서 번역 → `done.json` push → Actions가 DB 반영 + 파일 정리.
- 워크플로우: `.github/workflows/manual-translate.yml`, 스크립트: `manual_translate.py`

## 한 라운드 절차 (그대로 실행)

1. **요청 push**
   ```bash
   cd /home/claude/repo && git pull origin main
   mkdir -p translation
   cat > translation/request.json << 'EOF'
   {"title_limit": 200, "abstract_limit": 0}
   EOF
   git add translation/request.json && git commit -m "번역 요청" && git push origin main
   ```
   - 제목 단계: `{"title_limit": 200, "abstract_limit": 0}`
   - 초록 단계(제목 소진 후): `{"title_limit": 0, "abstract_limit": 25}`

2. **추출 대기 후 수신** (Actions 실행 ~30초)
   ```bash
   sleep 45 && git pull origin main && cat translation/pending.json | head -c 300
   ```
   - `pending.json`이 없으면 30초 더 기다렸다 다시 pull (최대 3회). 그래도 없으면 사용자에게 Actions 탭 확인 요청.
   - `remaining_titles` / `remaining_abstracts` 값 = 남은 전체 건수. 사용자에게 진행률 보고에 사용.

3. **번역** — pending.json의 모든 항목을 Claude가 직접 번역한다.
   - 학술 용어는 통용되는 한국어 학술용어로, 자연스러운 한국어로.
   - 고유명사/약어(RCT, DNA, 모델명 등)는 원문 유지 가능.
   - 같은 영어 제목이 중복되면 같은 번역을 재사용.

4. **결과 push** — python heredoc으로 `translation/done.json` 작성 후 push:
   ```json
   {"items": [{"id": "...", "title_ko": "..."}, {"id": "...", "abstract_ko": "..."}]}
   ```
   (title_ko / abstract_ko 중 해당하는 것만 포함)
   ```bash
   git add translation/done.json && git commit -m "번역 결과 N건" && git push origin main
   ```

5. **반영 확인**
   ```bash
   sleep 45 && git pull origin main && ls translation/ 2>&1
   ```
   - `done.json`과 `pending.json`이 삭제돼 있으면 = DB 반영 완료. 다음 라운드로.

## 세션 운영 규칙
- **라운드 크기**: 제목 200건 / 초록 25건 (품질·분량 균형점. 늘리지 말 것)
- **세션당 한도**: 제목 라운드 최대 5회(약 1,000건) 또는 초록 라운드 최대 4회(약 100건).
  이 한도에 도달하면 멈추고 사용자에게 보고: 남은 건수 + "새 대화에서 '한글화 이어서 진행해줘'라고 하면 계속됩니다."
- **우선순위**: 제목 먼저 전부 → 그다음 초록 (제목이 SEO·화면 효과가 훨씬 큼)
- **중복 실행 금지**: 이전 라운드의 done.json 반영 확인 전에 다음 request를 push하지 말 것.
- 매 라운드 종료 시 진행률 한 줄 보고: "이번 라운드 N건 반영, 제목 남은 것 X건 / 초록 남은 것 Y건"

## 완료 판정
- `pending.json`의 `remaining_titles`와 `remaining_abstracts`가 0이면 전체 완료.
- 사용자에게 최종 확인 SQL 안내:
  ```sql
  select
    count(*) filter (where title_ko is not null) as 제목_한글화,
    count(*) filter (where abstract_ko is not null) as 초록_한글화,
    count(*) as 전체
  from papers;
  ```

## 주의
- 매일 밤 자동수집의 Haiku 배치 번역(translate_titles.py)과 충돌하지 않음 — 둘 다 "번역 안 된 것만" 처리.
- DB가 초기화되면 남은 건수가 다시 늘어나는 게 정상 (새로 수집된 논문).
