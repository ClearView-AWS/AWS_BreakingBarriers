# 인수인계 (현재) — 프론트 리디자인 + AWS 데모 배포

*작성일: 2026-11-04 · 저녁 이후 갱신: `main` ≈ `6d72514` (grade10 PRs #31–#35 머지) · 계정: `767828752508` (Workshop Studio / `WSParticipantRole`)*

이전 오전 스냅샷(보관용)은 [`HANDOFF.md`](./HANDOFF.md)를 보세요 — **아키텍처 진실은 [`infra.md`](./infra.md) + [`README.md`](../README.md) + [`how-it-works.md`](./how-it-works.md).**  
**이 문서는 라이브 데모 URL과, grade10 이후 실제로 머지된 것을 기준으로 이어가기 위한 문서입니다.**

---

## 1. 한 줄 요약

- 프론트를 plan.md 방향(브리프 / Just show me results / List·Map)으로 리디자인함. 지도는 **Leaflet + OSM** (Amazon Location 없음).
- FastAPI를 **Fargate + ALB**, React를 **S3 + CloudFront**로 올려 **HTTPS 데모 URL**을 확보함.
- **Bedrock·OpenSearch·DynamoDB(RuntimeState 1테이블)·Translate·Guardrails** 라이브. CDK는 4스택: `GsAppStack`, `GsOpenSearchStack`, `GsGatewayStack`, `GsVoiceStack` (Gateway/Voice는 기본 배포 off).
- `main` 머지 시 GitHub Actions가 자동 재배포 (OIDC).

---

## 2. 지금 열려 있는 데모

| 항목 | 값 |
|---|---|
| **CloudFront URL** | https://dvpvz48phigre.cloudfront.net (`main` 자동 배포) |
| ALB (직접) | `http://GsAppS-ApiLB-mkXviaySO4Qm-551537671.us-east-1.elb.amazonaws.com` |
| 스택 | `GsAppStack` (`us-east-1`) |
| Bedrock | **켜짐** (`BEDROCK_ENABLED=1`, route/extract가 `bedrock`으로 응답) |
| OpenSearch | **연결됨** — `GsOpenSearchStack` 도메인 `searchdomainfdc-imug9ulee6sc`, `schools` 인덱스 적재 |
| DynamoDB | `GsAppStack`의 **단일** `RuntimeState` 테이블 (`pk`/`sk` + `data_json`: 세션·인박스·콜). `/tmp/gs-state.json`은 테이블 없을 때만 쓰는 폴백 |
| Translate | 켜짐 |
| Bedrock Guardrails | 켜짐 — `GsAppStack`이 커뮤니티 글 PII 가드레일을 만들고 `BEDROCK_GUARDRAIL_ID`로 넘김 |
| Maps | Leaflet + OpenStreetMap tiles (`frontend/src/Views.tsx`) — **not** Amazon Location / MapLibre |
| SES | 앱 플래그 `SES_ENABLED` (CDK가 SES를 만들지 않음). 기본 배포에서는 보통 off |
| Voice | `GsVoiceStack` 코드는 `main`에 있음. 기본 CI는 `DEPLOY_VOICE` off — Connect 인스턴스 + env 필요 |

예전 `InfraStack`(두 번째 OpenSearch 도메인, 미사용)은 11/04 저녁에 삭제함.

확인:

```bash
curl -s https://dvpvz48phigre.cloudfront.net/api/health
# → {"ok":true,"schools":...}
```

부모용 진입점은 항상 **CloudFront URL**. 어제처럼 IP:포트로 접속하지 않음.

---

## 3. 브랜치 / 커밋 상태

- 리디자인·배포: PR #18. 이후 #21 (Translate), #22 (OpenSearch + DynamoDB + 자동 배포), #23 (Grid/Map 이벤트).
- **grade10 (머지됨):** #35 Voice-as-code (`GsVoiceStack`), #34 eval rigor (holdout + Bedrock cost metering), #33 pitch kit (`docs/pitch/`), #32 feasibility (answer freshness, call limits / `calls.yaml`, school controls, inbound voice stub), #31 a11y/mobile (Playwright axe `npm run test:a11y`, WCAG polish, screenshots).
- 이슈 #15 (대화 루프) 등은 제품 백로그로 남을 수 있음 — 최신은 GitHub 이슈 보드를 보세요.

### 자동 배포

- `.github/workflows/deploy-demo.yml` — `main` push / 수동 실행 시 `./scripts/deploy-demo.sh`.
- 인증은 **GitHub OIDC** → IAM 역할 `GsGitHubDeploy` (repo 변수 `AWS_DEPLOY_ROLE_ARN`). 이 역할은 이 repo의 `main`만 신뢰함.
- 예전처럼 Workshop 세션 키를 secret에 넣던 방식은 토큰이 1시간 안에 만료돼서 #22 이후 배포가 실패했음. 다시 키 방식으로 돌리지 말 것.

---

## 4. 오늘 한 일

### 4-1. HANDOFF 권장 퀵픽스

| 항목 | 내용 |
|---|---|
| `.gitignore` 복구 | `.venv/`, `node_modules/`, `.env`, `data/runtime/`, `frontend/dist/`, `infra/cdk.out/` 등 |
| `pytest.ini` | 루트에서 `pytest` 시 `pythonpath = backend` |

### 4-2. 프론트엔드 리디자인

| 경로 | 역할 |
|---|---|
| `frontend/src/App.tsx` | 랜딩 + 검색 워크스페이스 |
| `frontend/src/components/*` | Brief, QuestionPrompt, SchoolResult, EvidenceGrid, DetailPanel, Saved/Inbox |
| `frontend/src/api.ts` | `/api/*` 클라이언트 |
| `frontend/src/styles.css` | GreatSchools 그린 + cool mist (기존 cream/Fraunces 탈피) |
| `frontend/index.html` | 폰트: Bricolage Grotesque + Figtree |

UX (백엔드는 아직 구계약이어도 UI는 plan 쪽을 닮게):

- 브랜드 히어로: GreatSchools / “We investigate. You decide.”
- **Search brief** (must / nice / avoid) + Looks right
- 질문 + **Just show me results**
- 결과 **List / Grid** 토글 (Map은 M2 자리표시, disabled)
- 디테일은 사이드 드로어

API는 기존 `POST /api/turn` 등 그대로.

### 4-3. AWS 배포 (데모 호스팅)

| 경로 | 역할 |
|---|---|
| `Dockerfile` | FastAPI + `Sample Data` + `data/` 베이크인 · **linux/amd64** |
| `.dockerignore` | 빌드 컨텍스트 축소 |
| `infra/lib/app-stack.ts` | **GsAppStack**: VPC, Fargate, ALB, S3, CloudFront, IAM(Bedrock/OS) |
| `infra/lib/infra-stack.ts` | **GsOpenSearchStack**: OpenSearch 도메인 (선택) |
| `infra/bin/infra.ts` | 스택 등록 · `-c enableOpenSearch=false` · `-c bedrockEnabled=true` |
| `scripts/deploy-demo.sh` | 프론트 빌드 → cdk bootstrap → deploy |
| `infra/README.md` | 배포/정리 요약 |
| `data/index/indexer.py` | hard filter 필드(`city_untokenized`, `level_codes`, `entity_type` 등) 포함하도록 보완 |

아키텍처 (라이브):

```text
Browser → CloudFront (HTTPS)
            ├─ /*      → S3 (frontend/dist)  + Leaflet/OSM map in the SPA
            └─ /api/*  → ALB → ECS Fargate (FastAPI)
                              ├─ DynamoDB RuntimeState (pk/sk)
                              ├─ Bedrock / Guardrails / Translate
                              └─ OpenSearch when OPENSEARCH_URL is set
Optional: GsVoiceStack (Connect→Lex→Lambda), GsGatewayStack (MCP), SES flag
```

기존 FastAPI를 살리려고 **Fargate**를 선택함 (API Gateway+Lambda 전면 교체 아님).

### 4-4. 배포 중 겪은 이슈 (다시 밟지 말 것)

1. **`Sample Data` 공백** → Dockerfile은 JSON `COPY` 형식 사용.
2. **Apple Silicon ARM 이미지 vs Fargate amd64** → Circuit Breaker.  
   해결: `FROM --platform=linux/amd64` + CDK `platform: LINUX_AMD64` + `CpuArchitecture.X86_64`.
3. **ROLLBACK_IN_PROGRESS** 중 재배포 불가 → 스택 삭제 완료 후 재배포.  
   `describe-stacks`가 “does not exist”면 바로 재배포 가능.
4. Workshop Studio 세션 만료 → 주최 링크 재접속 후 `aws login`.
5. 터미널에 Access Key를 paste하지 말 것. **`aws login`만** 사용.

---

## 5. 로컬 / 재배포 방법

### 자격증명

```bash
aws login
export AWS_REGION=us-east-1
export CDK_DEFAULT_REGION=us-east-1
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_DEFAULT_REGION
aws sts get-caller-identity
```

Docker Desktop 필요.

### 데모 스택만 다시 올리기

```bash
SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh
```

Bedrock은 기본으로 켜짐 (`BEDROCK=0`이면 규칙 엔진만). `GsOpenSearchStack`이 있으면 스크립트가 엔드포인트를 자동으로 읽어 앱에 넘김 (`OPENSEARCH_ENDPOINT=none`이면 로컬 검색).

### 로컬 개발 (어제 방식)

```bash
cd backend && ../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

### 정리 (과금 중단)

```bash
cd infra
npx cdk destroy GsAppStack GsOpenSearchStack GsGatewayStack GsVoiceStack --force
aws iam detach-role-policy --role-name GsGitHubDeploy --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
aws iam delete-role --role-name GsGitHubDeploy
```

OpenSearch는 유휴 시에도 시간당 과금이 큼.

---

## 6. grade10 이후 상태 / 남은 일

**머지되어 `main`에 있는 것 (요약):**

| 영역 | 내용 | 위치 |
|---|---|---|
| Voice as code | Connect / Lex / voice Lambda CDK | `infra/lib/voice-stack.ts`, `DEPLOY_VOICE` |
| Pitch kit | Impact / cost / RAI / demo script / judge Q&A | `docs/pitch/` |
| A11y + mobile | axe Playwright gate, skip links, 44px targets, screenshots | `frontend/tests/a11y.spec.ts`, `npm run test:a11y` |
| Eval rigor | Holdout set + Bedrock token/cost metering | `eval/holdout.jsonl`, `eval/run_eval.py --set holdout` |
| Feasibility | Answer freshness (`max_age_days` / stale), call limits, school do-not-call, inbound voice stub | `backend/config/calls.yaml`, evidence engine, phone paths |

**아직 / 선택:**

1. 샌드박스에 `GsVoiceStack` + Connect 인스턴스를 실제로 붙이고 데모 콜 검증.
2. SES를 AppStack에 first-class로 넣을지, 문서처럼 플래그-only로 둘지 (별도 grade11 태스크).
3. 이슈 #15 대화 루프 등 UX 폴리시.
4. plan.md에 남은 평가 셋(안전 필터 게시글, “붙을까요?” 등) — 필요 시.

---

## 7. 문서 지도

| 문서 | 용도 |
|---|---|
| **이 파일** (`HANDOFF-CURRENT.md`) | 라이브 URL + 재배포 + grade10 이후 상태 |
| [`HANDOFF.md`](./HANDOFF.md) | 11/04 **오전** 보관용 (배너 참고) |
| [`how-it-works.md`](./how-it-works.md) | 심사/설명용 스택 내러티브 |
| [`plan.md`](./plan.md) | 목표 UX·마일스톤 (코드보다 앞선 설계일 수 있음) |
| [`infra.md`](./infra.md) | **현재** AWS 아키텍처 (4 stacks, 1 DynamoDB table, Leaflet) |
| [`infra/README.md`](../infra/README.md) | CDK 스택 짧은 운영 메모 |
| [`docs/pitch/`](./pitch/) | Impact / Originality 피치 키트 |

---

## 8. 주의

- AWS 키·세션 토큰을 채팅/스크린샷/커밋에 넣지 말 것.
- CloudFront URL은 배포마다 바뀔 수 있음. 최신 값은:

  ```bash
  aws cloudformation describe-stacks --stack-name GsAppStack --region us-east-1 \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" --output text
  ```

- 해커톤 끝나면 `cdk destroy`로 스택 삭제.
