# 인수인계 문서 (Handoff)

> ## ⚠️ HISTORICAL — pre–Nov 4 afternoon (do not trust for “what ships”)
>
> This file is a **morning-of-2026-11-04** snapshot (`infra/opensearch` @ `beabe0f`). Many claims below are **stale** after grade10 merges on `main` (~`6d72514`).
>
> **Source of truth for live architecture and ops:**
> - [`HANDOFF-CURRENT.md`](./HANDOFF-CURRENT.md) — demo URL, stacks, redeploy
> - [`README.md`](../README.md) — flags, local run, CDK table
> - [`how-it-works.md`](./how-it-works.md) — judge-facing stack narrative
> - [`infra.md`](./infra.md) — AWS as shipped (4 stacks, one DynamoDB table, Leaflet/OSM)
>
> **Dangerous claims in this file (corrected):** OpenSearch **is** on the request path when `OPENSEARCH_URL` is set (`backend/search/engine.py`). DynamoDB is **one** `RuntimeState` (`pk`/`sk` + `data_json`), not six tables. Maps are **Leaflet + OSM**, not Amazon Location. SES is optional (`SES_ENABLED`), not always-on.

*작성일: 2026-11-04 · 기준 브랜치: `infra/opensearch` (HEAD `beabe0f`) · 대상: 이 프로젝트를 이어서 개발할 사람 · **보관용***

이 문서 하나만 읽고 바로 이어서 개발할 수 있도록, **지금까지 한 일 / 지금 실제로 동작하는 것 / 문서와 코드가 어긋난 곳 / 다음에 할 일**을 정리했습니다.
"동작한다"고 적은 항목은 모두 2026-11-04 **오전**에 직접 실행해서 확인한 결과입니다. 확인하지 못한 항목은 **미확인**으로 표시했습니다. **오후 이후 배포·OpenSearch 연결·DynamoDB·Voice·pitch/a11y/eval은 위 배너의 현재 문서를 보세요.**

---

## 1. 한 줄 요약

GreatSchools 해커톤용 **"가이드형 학교 검색 에이전트"**. 부모가 자연어로 원하는 조건을 말하면, 코드가 조건을 추출하고 데이터에 근거(인용)해서 학교를 순위화합니다.
**현재 로컬(룰 엔진)로는 데모 스크립트 M1–M4까지 완성**되어 있고, AWS 쪽은 **OpenSearch 도메인 CDK 스택과 SigV4 인덱서까지만** 작업된 상태입니다.

> 핵심 원칙: **모델은 부모의 말을 읽고, 무엇이 사실인지는 코드가 결정한다.** 화면의 모든 사실은 필드/리뷰 ID를 인용해야 하며, 인용 없는 문장은 표시하지 않는다.

---

## 2. 먼저 읽을 문서

| 문서 | 내용 | 비고 |
|---|---|---|
| `docs/Vision - Final - GreatSchools.md` | GreatSchools가 준 요구사항 (P1–P4) | 원본, 수정하지 않음 |
| `docs/Tech - Final - GreatSchools.md` | GreatSchools 기술 스택/데이터 설명 | 원본, 수정하지 않음 |
| `docs/plan.md` | 구현 계획: 차별점, 규칙, 계약(contract), 마일스톤 M1–M6, 데모 스크립트 | **코드보다 나중에 개편됨** (§6 참고) |
| `docs/infra.md` | AWS 아키텍처, IAM, Day 0 셋업, 비용/정리 | plan.md의 짝 문서 |
| `README.md` | 로컬 실행법, 설계 결정, AWS 플래그, eval 결과 | **현재 코드 기준** 설명 |
| `infra/` | OpenSearch CDK 스택 | `infra/README.md`는 CDK 기본 템플릿 그대로 |

---

## 3. 지금까지 한 일 (커밋 타임라인)

| 커밋 | 작성자 | 내용 |
|---|---|---|
| `ecd1208` ~ `ec4a8d9` | Nathan Simon | 최초 커밋, plan/데이터 이전, `docs/infra.md` 작성 |
| `46c1594` | dlwnstjd98 | **로컬 에이전트 전체 구현** (backend, frontend, 합성 데이터 275개 학교, eval 42개 쿼리, 테스트) |
| `4cca95e` ~ `3c285a3` | Nathan Simon | **plan.md 대폭 개편**: 질문 최대 3개 + 브리프 승인, 부모 커뮤니티, Guardrails, 지도, 입학(Getting in) 추가 / why-not·웹사이트 확인·방문 체크리스트 삭제 |
| `76abd8d`, `c0b5199` | Nathan Simon | `.DS_Store` 무시 |
| `35fb8f9` | dlwnstjd98 | `infra/` CDK 스택: OpenSearch 도메인 1개 |
| `9db9972` | Junseong Lee | `main` → `infra/opensearch` 머지 |
| `beabe0f` | dlwnstjd98 | 인덱서에 SigV4 서명(`AWSV4SignerAuth`) 추가, `boto3`/`opensearch-py` 의존성 추가 |

---

## 4. 현재 상태 — 실제로 실행해서 확인한 결과 (2026-11-04)

| 항목 | 명령 | 결과 |
|---|---|---|
| 백엔드 테스트 | `cd backend && ../.venv/bin/python -m pytest tests -q` | ✅ 16 passed |
| 백엔드 테스트 (README 방식) | 리포 루트에서 `.venv/bin/python -m pytest backend/tests -q` | ❌ `ModuleNotFoundError: No module named 'agent'` (§7-2) |
| Eval | `.venv/bin/python eval/run_eval.py` | ✅ recall 110/110, precision 110/110, strength 39/39, ask 39/39, 인용 30/30, 누락 0, 중앙값 0.03s |
| 인덱서 (로컬) | `.venv/bin/python data/index/indexer.py` | ✅ 374개 문서 → `data/index/documents.jsonl`, `OPENSEARCH_URL` 없으면 클러스터 건너뜀 |
| 프론트엔드 빌드 | `cd frontend && npm ci && npm run build` | ✅ 빌드 성공 |
| CDK | `cd infra && npm ci && npx tsc --noEmit && npx cdk synth -q && npx jest` | ✅ 타입체크/synth/테스트 통과 (테스트는 빈 플레이스홀더) |
| OpenSearch 도메인 실제 배포 여부 | — | **미확인** (이 세션에 AWS 자격증명 없음) |
| Bedrock / SES 실제 호출 | — | **미확인** (플래그 꺼진 상태로만 검증됨) |

Eval 수치는 **Bedrock을 끈 결정론적 룰 엔진**의 결과입니다. 실제 모델 성능이 아닙니다.

---

## 5. 로컬 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
```

```bash
cd backend && ../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

http://127.0.0.1:5173 에서 데모 쿼리: *"Middle school in Jacksonville with STEM and after-school care. Money is tight."*

- 데모 도시: Jacksonville, 규칙용 고정 날짜: `GS_TODAY=2026-11-03`
- 세션/저장 목록/학교 인박스는 `data/runtime/state.json` (DynamoDB 대용, `GS_STATE_PATH`로 변경)
- 합성 데이터 재생성: `python data/synthetic/generate.py` (`Sample Data/`의 25개 원본은 건드리지 않음)

### API

| 메서드 | 경로 | 역할 |
|---|---|---|
| GET | `/api/health` | 헬스체크 |
| POST | `/api/turn` | 대화 1턴 (라우팅 → 추출 → 검색 → 근거 → 점수 → 설명) |
| GET | `/api/session/{session_id}` | 세션 조회 |
| GET | `/api/inbox` | 학교 인박스 (부모 질문) |
| POST | `/api/inbox/{question_id}/reply` | 학교 답변 |
| GET | `/api/schools/{school_id}` | 학교 상세 |

### 코드 지도

| 무엇 | 어디 |
|---|---|
| 니즈(Needs), 문구, 근거 조건, 검색 부스트 | `backend/config/needs.yaml` |
| 장학금 규칙/공식 링크 | `backend/config/funding_rules.yaml` |
| 용어 정의 | `backend/config/glossary.yaml` |
| 모델 ID | `backend/config/models.yaml` |
| 턴 전체 흐름 | `backend/pipeline.py` |
| 상태/점수/why-not | `backend/evidence/` |
| 언제 질문할지 | `backend/clarify/clarifier.py` |
| 라우팅/추출/인용/설명 (Bedrock 포함) | `backend/agent/` |
| 검색 (로컬 하이브리드 + OpenSearch DSL 생성) | `backend/search/` |
| 웹사이트, 인박스, SES | `backend/gaps/` |
| 화면 블록 렌더링 | `frontend/src/App.tsx` |
| 인덱스 매핑 / 인덱서 | `data/index/` |
| OpenSearch CDK | `infra/lib/infra-stack.ts` |

---

## 6. ⚠️ plan.md와 코드가 어긋난 곳

코드(`46c1594`)가 먼저 만들어지고, 그 **이후에** plan.md가 개편(`4cca95e`)되었습니다. 그래서 **plan.md는 "앞으로 만들 것", README는 "지금 있는 것"** 입니다. 둘을 혼동하지 마세요.

| 주제 | plan.md (목표) | 현재 코드 |
|---|---|---|
| 검색 전 질문 | 최대 3개, 건너뛰기 가능, 브리프(must/nice/avoid) 승인 후 검색 | 턴당 최대 1개 질문, 결과를 같은 턴에 표시 |
| Why-not ("왜 이 학교가 없나") | **삭제됨** | `backend/evidence/why_not.py` 존재, 데모에 사용 |
| 학교 웹사이트로 공백 채우기 | **삭제됨** | `backend/gaps/websites.py` 존재 |
| 부모 커뮤니티 (스레드, 댓글, 추천, Guardrails) | M4 | 없음 (`backend/community/` 없음) |
| 입학 정보 (Getting in, `enrollment_rules.yaml`) | M3 | 없음 |
| 지도 뷰 (Amazon Location) | M2 | 없음 |
| 디렉터리 | `brief/`, `community/`, `enrollment/`, `geo/` | `clarify/`, `gaps/`, `search/geo.py` |
| 상태 저장 | DynamoDB 6개 테이블 | JSON 파일 |

**결정 필요:** 개편된 plan.md 방향으로 코드를 옮길지, 현재 코드 기준으로 plan.md를 되돌릴지 팀과 먼저 합의하세요.

### infra.md와 코드의 이름 불일치

| 항목 | `docs/infra.md` | 코드 |
|---|---|---|
| OpenSearch 엔드포인트 환경변수 | `OPENSEARCH_ENDPOINT` | `OPENSEARCH_URL` (`backend/runtime_config.py`) |
| SES 발신자 환경변수 | `SES_FROM_ADDRESS` | `SES_SOURCE` + `SES_VERIFIED_TO` (`backend/gaps/ses_mailer.py`) |
| `models.yaml` 키 | `router`/`extractor`/`tagger`/`explainer`/`embedding` | `fast_model`/`strong_model`/`embed_model`/`embed_dimension` |
| 임베딩 차원 | 1024 | 256 (`models.yaml`, `mappings.json`) |
| 벡터 필드명 | `search_vector` | `embedding` |
| 인덱스 | 버전 인덱스(`schools_vN`) + alias 교체 | `schools`/`programs`를 **삭제 후 재생성** |
| 하이브리드 검색 파이프라인 | `gs-guided-hybrid` (min-max 정규화) | 없음 |
| 리소스 이름/태그 | `gs-guided-` 접두사, `Project=greatschools-guided-search` 태그 | 스택 이름 `InfraStack`, 태그 없음 |

---

## 7. ⚠️ 확인된 문제 (증거 포함, 아직 수정 안 함)

수정 전에 증거로 확인한 사실만 적었습니다. 고칠지 여부와 방법은 다음 담당자가 결정하세요.

### 7-1. 루트 `.gitignore`가 머지에서 사라짐
- **증거:** `46c1594`의 `.gitignore`는 11줄(`.venv/`, `__pycache__/`, `node_modules/`, `frontend/dist/`, `data/runtime/`, `.env` 등). 머지 `9db9972`에서 `.gitignore | 10 -` → 현재는 `.DS_Store` 한 줄.
- **영향:** 테스트/서버 실행 후 `git status`에 `__pycache__/`, `data/runtime/`, `data/index/documents.jsonl`이 뜸. **`.env`(AWS 정보)가 커밋될 위험.**
- 복구: `git show 46c1594:.gitignore`의 내용을 되살리면 됨 (`data/index/documents.jsonl`도 추가 고려).

### 7-2. README의 테스트 명령이 루트에서 실패
- **증거:** 루트에서 `pytest backend/tests` → `No module named 'agent'`. `backend/`에서 `pytest tests` → 16 passed. 리포에 `conftest.py`/`pytest.ini`/`pyproject.toml` 없음.
- 당장은 `backend/`에서 실행하세요.

### 7-3. OpenSearch는 요청 경로에 연결되어 있지 않음
- **⚠️ SUPERSEDED (post–Nov 4):** live `main` calls OpenSearch when `OPENSEARCH_URL` is set (`search_school_ids` in `backend/search/engine.py` + `opensearch_client.py`). The morning note below is historical only.
- **당시 증거 (오전):** `backend/search/engine.py`에서 `build_query(...)` 반환값을 버리고 클라이언트 호출이 없었음. `OPENSEARCH_URL`은 인덱서만 사용.

### 7-4. 인덱서가 하드 필터 필드를 넣지 않음
- **증거:** `data/index/indexer.py`는 `id`, `search_text`, `embedding`만 인덱싱. 그런데 `query.py`의 하드 필터는 `city_untokenized`, `level_codes`, `entity_type` 사용 (`mappings.json`에는 정의됨).
- **영향:** 검색을 OpenSearch로 옮기면 필터가 걸린 쿼리는 **결과 0건**이 됩니다. 연결 전에 학교 원본 필드도 함께 인덱싱해야 함.

### 7-5. 인덱서는 항상 해시 임베딩 사용
- **증거:** `indexer.py`는 `embed_hash`를 직접 호출 → `BEDROCK_ENABLED=1`이어도 Titan을 쓰지 않음. 반면 `mapping/embedder.py`의 `embed_texts`는 Bedrock 실패 시 조용히 해시로 fallback(`except Exception: pass`).
- **영향:** 인덱스 벡터와 쿼리 벡터의 임베딩 방식이 달라질 수 있음.

### 7-6. CDK 스택의 열린 점
- `infra/lib/infra-stack.ts`: OpenSearch 2.17, `t3.small.search` 1노드, EBS 10GB, HTTPS/암호화 on, 접근 정책은 계정 루트에 `es:*`, `RemovalPolicy.DESTROY`.
- `env`가 지정되지 않음 → 배포 리전은 CLI 기본값을 따름 (infra.md는 `us-east-1` 고정).
- `t3.small.search`에서 k-NN이 지원되는지 **미확인** — 배포 전에 AWS 콘솔/문서로 확인 필요 (infra.md도 "Day 0에 확인"으로 남겨둠).
- `infra/test/infra.test.ts`는 CDK 기본 SQS 예제가 주석 처리된 빈 테스트 → 실제로 검증하는 것 없음.
- DynamoDB, S3, SES, Guardrails, Fargate, CloudFront는 아직 CDK에 없음.

---

## 8. AWS 연결 플래그 (현재 코드 기준)

모두 꺼져 있으면 룰 엔진 + 로컬 인덱스 + JSON 파일 + 로컬 HTML이 대신 동작합니다. 리전 `us-east-1`.

| 플래그 | 켜지는 것 |
|---|---|
| `BEDROCK_ENABLED=1` | Converse로 라우팅/추출/설명, Titan V2 임베딩 (`models.yaml`의 ID 사용) |
| `OPENSEARCH_URL=https://...` | `data/index/indexer.py`가 SigV4로 서명해 `schools`/`programs` 인덱스를 **삭제 후 재생성**하고 문서 적재 |
| `SES_ENABLED=1` + `SES_SOURCE` + `SES_VERIFIED_TO` | 인박스 메시지를 SES 샌드박스로도 발송 (검증된 주소로만) |

OpenSearch에 인덱싱하는 순서:

```bash
cd infra && npm ci && npx cdk deploy
```

```bash
OPENSEARCH_URL=https://<DomainEndpoint 출력값> .venv/bin/python data/index/indexer.py
```

`DomainEndpoint` 출력값에는 `https://`가 붙어 있지 않으니 직접 붙이세요. 실행하는 사람의 AWS 자격증명으로 서명합니다.

---

## 9. 다음에 할 일 (추천 순서)

1. **방향 합의** — plan.md(개편안)와 현재 코드 중 무엇을 기준으로 할지 (§6). 이게 정해져야 나머지 우선순위가 정해집니다.
2. **`.gitignore` 복구** (§7-1) — `.env` 사고 방지. 5분짜리 작업.
3. **테스트 명령 정리** (§7-2) — README를 고치거나 pytest 설정을 추가.
4. **OpenSearch 실제 배포/확인** — `cdk deploy` 후 인스턴스 타입의 k-NN 지원, 리전, 엔드포인트 확인 (§7-6).
5. **인덱서 보완** — 하드 필터 필드 포함(§7-4), 임베딩 모델/차원을 infra.md와 맞추기(§7-5, §6).
6. **검색 경로 연결** — `search/engine.py`가 `OPENSEARCH_URL`이 있을 때 실제로 `_search`를 호출하도록 (§7-3). 로컬 엔진과 결과를 eval로 비교.
7. **Bedrock 실제 호출 확인** — 샌드박스에서 활성화된 모델 ID를 `models.yaml`에 반영하고 `BEDROCK_ENABLED=1`로 eval 재실행.
8. 그 다음 plan.md 마일스톤(M2 브리프 → M3 입학/비교 → M4 커뮤니티 → M5 학교 질문/비용) 순서로 진행.

---

## 10. 아직 열려 있는 질문

`docs/plan.md`, `docs/infra.md`의 Open Questions에서 아직 답이 없는 것:

- 해커톤 기간과 인원 → 목표 마일스톤 결정
- 샌드박스에서 활성화된 Bedrock 모델
- 샌드박스에서 공개 OpenSearch 엔드포인트, SES, CloudFront, Amazon Location 허용 여부, 기본 VPC 존재 여부
- GreatSchools 실제 OpenSearch 샘플 문서 제공 여부 (오면 계약을 바꾸지 말고 어댑터 작성)
- 커뮤니티를 GreatSchools 기존 리뷰(85만+)와 어떻게 합칠지
- CDK로 갈지 콘솔로 갈지 → **CDK로 시작함** (`infra/`), 이후 리소스도 CDK로 추가할지 결정 필요

---

## 11. 주의사항

- AWS 액세스 키를 리포나 `.env`에 커밋하지 말 것 (현재 `.gitignore`가 `.env`를 막지 못함, §7-1).
- 인박스의 학교 주소는 `office@<id>.example.org` 형태로 생성됨 (`backend/gaps/inbox.py:32`). SES는 실제로는 `SES_VERIFIED_TO` 한 주소로만 보냄.
- 장학금 문구는 "You may qualify" + 플로리다 교육부 공식 링크. 금액을 약속하지 않음.
- 모든 합성 레코드는 `_synthetic: true`. `Sample Data/`는 원본이므로 수정 금지.
- OpenSearch 도메인은 쉬고 있어도 시간당 과금. 해커톤이 끝나면 `cd infra && npx cdk destroy`.
