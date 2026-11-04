# 인수인계 (현재) — 프론트 리디자인 + AWS 데모 배포

*작성일: 2026-11-04 · 브랜치: `feature/frontend-redesign` · 계정: `767828752508` (Workshop Studio / `WSParticipantRole`)*

이전 배경·코드 갭·OpenSearch 이슈는 [`HANDOFF.md`](./HANDOFF.md)를 보세요.  
**이 문서는 오늘(11/04) 세션에서 실제로 한 일과, 지금 열린 데모 URL을 기준으로 이어가기 위한 문서입니다.**

---

## 1. 한 줄 요약

- 프론트를 plan.md 방향(브리프 / Just show me results / List·Grid)으로 리디자인함.
- FastAPI를 **Fargate + ALB**, React를 **S3 + CloudFront**로 올려 **HTTPS 데모 URL**을 확보함.
- OpenSearch·Bedrock은 아직 요청 경로에 안 붙였거나 꺼져 있음. 검색은 컨테이너 안 **로컬 하이브리드 엔진**으로 동작.

---

## 2. 지금 열려 있는 데모

| 항목 | 값 |
|---|---|
| **CloudFront URL** | https://dvpvz48phigre.cloudfront.net (redeployed from `main` after PR #18) |
| ALB (직접) | `http://GsAppS-ApiLB-mkXviaySO4Qm-551537671.us-east-1.elb.amazonaws.com` |
| 스택 | `GsAppStack` (`us-east-1`) |
| Bedrock | **꺼짐** (`BedrockEnabled=0`) |
| OpenSearch | **미배포** (`SKIP_OPENSEARCH=1`로 올렸음) |

확인:

```bash
curl -s https://dvpvz48phigre.cloudfront.net/api/health
# → {"ok":true,"schools":...}
```

부모용 진입점은 항상 **CloudFront URL**. 어제처럼 IP:포트로 접속하지 않음.

---

## 3. 브랜치 / 커밋 상태

- 작업 브랜치: **`feature/frontend-redesign`**
  - 처음 요청이 “프론트 리디자인용 별도 브랜치”였고, 이어서 AWS 배포를 같은 브랜치에 올림 (속도 때문).
- **아직 커밋되지 않은 변경이 많음** (`git status`에 수정·untracked 다수).
- 기준이 된 이전 HEAD: `f1adf02` (기존 `docs/HANDOFF.md` 추가 커밋) 위.

인수인계 시 먼저 커밋·푸시 여부를 팀에 맞출 것.

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

아키텍처 (오늘 올린 것):

```text
Browser → CloudFront (HTTPS)
            ├─ /*      → S3 (frontend/dist)
            └─ /api/*  → ALB → ECS Fargate (FastAPI, 로컬 검색 + JSON state)
```

다이어그램의 Lambda/API Gateway 대신, 기존 FastAPI를 살리려고 **Fargate**를 선택함.

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

Bedrock 켠 재배포:

```bash
BEDROCK=1 SKIP_OPENSEARCH=1 ./scripts/deploy-demo.sh
```

### 로컬 개발 (어제 방식)

```bash
cd backend && ../.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

### 정리 (과금 중단)

```bash
cd infra
npx cdk destroy GsAppStack --force
# OpenSearch까지 올렸다면:
# npx cdk destroy GsOpenSearchStack --force
```

OpenSearch는 유휴 시에도 시간당 과금이 큼.

---

## 6. 아직 안 된 것 / 다음 할 일

우선순위 제안:

1. **변경분 커밋·원격 푸시** (지금 uncommitted).
2. **Bedrock** — 샌드박스 모델 액세스 확인 → `models.yaml` ID 맞추기 → `BEDROCK=1` 재배포.
3. **OpenSearch** — `cdk deploy GsOpenSearchStack` → indexer → `OPENSEARCH_ENDPOINT=...`로 앱 재배포.  
   검색 엔진이 `OPENSEARCH_URL`일 때 실제 `_search`를 부르도록 연결은 아직 약함 ([`HANDOFF.md`](./HANDOFF.md) §7-3). 지금은 로컬 엔진으로 데모 가능.
4. **plan.md 정렬** — 브리프 승인 후 검색, 질문 최대 3개, Getting in / Map / Community 백엔드.
5. DynamoDB로 `state.json` 대체 (Fargate는 태스크 교체 시 `/tmp` 상태 유실).

방향 합의(plan vs 현재 코드)는 예전 HANDOFF §6 그대로 열려 있음. 오늘은 **데모 URL 확보**를 우선했음.

---

## 7. 문서 지도

| 문서 | 용도 |
|---|---|
| **이 파일** (`HANDOFF-CURRENT.md`) | 오늘 작업 + 라이브 URL + 재배포 |
| [`HANDOFF.md`](./HANDOFF.md) | 11/04 오전 기준 전체 코드/갭/eval |
| [`plan.md`](./plan.md) | 목표 UX·마일스톤 (코드보다 앞선 설계) |
| [`infra.md`](./infra.md) | 목표 AWS 아키텍처 (Fargate/CF 등) |
| [`infra/README.md`](../infra/README.md) | CDK 스택 짧은 운영 메모 |

---

## 8. 주의

- AWS 키·세션 토큰을 채팅/스크린샷/커밋에 넣지 말 것.
- CloudFront URL은 배포마다 바뀔 수 있음. 최신 값은:

  ```bash
  aws cloudformation describe-stacks --stack-name GsAppStack --region us-east-1 \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" --output text
  ```

- 해커톤 끝나면 `cdk destroy`로 스택 삭제.
