# Person C: AWS architect

**Clock:** 3:00–4:10 (1:10 · ~160 words)  
**You:** Stand beside the screen. Don't touch the laptop.  
**Screen:** Seattle results stay up. Optional: architecture slide (`docs/infra.md` diagram) on a second display.

---

## Say (word-for-word)

Everything you just saw runs in one AWS account, deployed as four CDK stacks.

CloudFront serves the React app from S3, and the API runs on ECS Fargate behind a load balancer. Session state lives in a single DynamoDB table.

Bedrock does two jobs. Claude Haiku reads what the parent typed, and Sonnet handles the harder turns. Bedrock Guardrails strip personal information from parent posts. OpenSearch adds hybrid keyword and vector search. Translate and Comprehend let a parent search in their own language.

Every one of those is behind a flag with a local fallback. If Bedrock goes down, the rules engine answers and the page still works.

We kept the model off the write path on purpose. On thirty holdout queries we never tuned on, Bedrock found ninety-seven percent of what parents asked for. Even so, a model never marks a fact Confirmed. Code does that.

Next, the part no filter can do. We pick up the phone.

---

## Stage notes

- Don't list services faster than you can point at them. If you run long, cut the Translate sentence.
- Hand to Person D on "pick up the phone". D is already at the laptop.

## Where the numbers come from

| Line | Source |
| --- | --- |
| Four CDK stacks, one DynamoDB table | `docs/infra.md` (GsAppStack, GsOpenSearchStack, GsGatewayStack, GsVoiceStack) |
| Haiku / Sonnet | `backend/config/models.yaml` |
| 97% holdout recall (96/99), Bedrock on | README → Evaluation → Holdout, Bedrock on |
