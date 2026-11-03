# Technical Environment Document: GreatSchools Guided Agent

## Hackathon Context

- Build in an empty AWS sandbox account. No access to GreatSchools' environment.
- Greenfield. Mirror GreatSchools' stack where practical so the work can transfer afterward.
- Data must be synthetic, mocked, or already publicly available.

## Project Technical Summary

- **Project Name**: GreatSchools Guided Search (Level 2 Guided Agent)
- **Primary Runtime Environment**: Cloud
- **Cloud Provider**: AWS
- **Customer Context**: GreatSchools runs on AWS (us-east-1, multi-account organization) on self-managed EC2, with a Ruby on Rails application, MySQL as the main database, OpenSearch for search, and an S3/Athena data lake for internal analytics. GreatSchools cares about outcomes over implementation. They are open to teams choosing their own languages, frameworks, models, and level of agent autonomy, and want to see which approaches teams take.

## How Search Works Today

This is the pattern the Guided Agent builds on.

GreatSchools combines an LLM (OpenAI gpt-5.4-nano) with NLP to turn a parent's plain-language query into **needs**, and each need maps directly to OpenSearch query parameters.

Example:
1. The query contains "top school."
2. It maps to the **high performing** need.
3. That need becomes a hard filter on summary rating 8–10, plus a boost for community rating 4–5 stars.

Level 2 adds the guided layer on top: clarifying questions, gap-spotting, and evidence for each result.

---

## Firm Choices

| Area | Choice | Why |
|------|--------|-----|
| Search | Amazon OpenSearch Service | GreatSchools' search platform |
| Foundation models | Amazon Bedrock | Breaking Barriers standard |
| Region | us-east-1 | Matches GreatSchools production |

## Flexible Choices

GreatSchools has no preference on these. Teams choose and note their choices in the README.

| Area | Options | Notes |
|------|---------|-------|
| Language | Any | Rails is GreatSchools' production language; Python is a good fit for agent work |
| Model | Any model on Bedrock | No preference from GreatSchools |
| How agentic | Guided flow to autonomous investigation | GreatSchools is open to different approaches |
| Agent framework | Strands Agents, LangGraph, or similar | Optional |
| Compute / hosting | Lambda, Fargate, EC2, or local for the demo | GreatSchools wants to see what teams choose |
| Infrastructure as code | CloudFormation, Terraform, CDK, or none | No preference |
| Frontend | Team's choice | Use the POC mockup as the visual reference |

---

## Cloud Environment

### Services Likely Used

| Service | Role |
|---------|------|
| Amazon Bedrock | Foundation models for the agent |
| Amazon OpenSearch Service | Keyword and vector search over school and program documents |
| Amazon S3 | Sample data files and artifacts |
| AWS Lambda | Simple tool backends (optional) |

### Things to Avoid

| Item | Reason |
|------|--------|
| Real GreatSchools data or credentials | Not allowed in the sandbox |
| Student data of any kind | GreatSchools requirement |
| Building login / accounts | Out of scope; assume the user is signed in |

---

## Data

- **From GreatSchools (coming):** sample OpenSearch documents for schools and programs, plus sample data feeds.
- **Starter dataset (available now):** `greatschools_synthetic_sample.json` with schools, ratings, test scores, demographics, district info, programs, reviews, and example parent queries.
- **Reference:** greatschools.org shows the range of data GreatSchools loads.

## Handoff

Each team ships to its own GitHub repo. The README should cover how to run the project, the decisions made, and the AWS services used, so GreatSchools can pick up the work afterward.
