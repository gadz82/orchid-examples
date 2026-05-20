<!-- Source: derived from orchid-website/src/content/best-practices.mdx, orchid-website/src/content/ecosystem.mdx, and codebase analysis -->

# Scenario Adaptation

Guidelines for adapting Orchid to different domains and use cases.

## Common Scenarios

### Customer Support

- **Agent fleet:** Triage, FAQ, Escalation, Knowledge Base, Order Status.
- **RAG namespaces:** support-faq, product-docs, policies.
- **Tools:** ticket lookup, order status, CRM search.
- **Skills:** "full-support-flow" (triage → FAQ → escalate if needed).
- **Guardrails:** Topic restriction to support domain, PII redaction.

### E-Commerce

- **Agent fleet:** Catalog Search, Cart Assistant, Order Tracking, Recommendations.
- **RAG namespaces:** products, reviews, policies, promotions.
- **Tools:** search catalog, get inventory, calculate shipping, apply promo.
- **Skills:** "complete-purchase" (search → cart → checkout).
- **Guardrails:** Max transaction value, fraud detection patterns.

### Education

- **Agent fleet:** Course Info, Enrollment, Progress Tracking, Tutor.
- **RAG namespaces:** courses, curriculum, faq, materials.
- **Tools:** check prerequisites, get schedule, submit assignment.
- **Skills:** "course-enrollment" (course info → check prereqs → enroll).
- **Guardrails:** Topic restriction to educational domain.

### Healthcare

- **Agent fleet:** Appointment, Medical Records, Prescriptions, Billing.
- **RAG namespaces:** departments, procedures, insurance, faq.
- **Tools:** check availability, lookup record, verify insurance.
- **Skills:** "scheduling" (find doctor → check availability → book).
- **Guardrails:** Strict PII redaction, HIPAA compliance patterns.

## Adaptation Checklist

### 1. Define Agents

Map your domain to agents:

- Identify distinct knowledge domains.
- Each agent = one domain of expertise.
- 3-10 agents for most deployments.

### 2. Create Knowledge Files

Write markdown knowledge files for each domain:

- 300-1500 words per file.
- Self-contained topics.
- H2/H3 headings for natural chunking.

### 3. Configure Guardrails

Set appropriate guardrails for your domain:

- Topic restrictions for each agent.
- Content safety for user-facing agents.
- PII detection for sensitive domains.
- Max length to prevent token abuse.

### 4. Define Cross-Agent Skills

Map common multi-domain workflows:

- Identify queries that span multiple agents.
- Define sequential agent chains.
- Write clear skill descriptions for supervisor detection.

### 5. Choose LLM Providers

Match models to agent requirements:

- Simple Q&A → cheap/fast models.
- Complex reasoning → powerful models.
- Privacy-sensitive → local models.

### 6. Design RAG Scopes

Plan your scope hierarchy:

- Shared knowledge → `tenant_id="__shared__"`.
- Domain knowledge → per-tenant or per-user.
- Conversation context → per-chat.

### 7. Test and Iterate

- Test with real queries from your domain.
- Adjust agent prompts based on response quality.
- Tune RAG k values for retrieval quality.
- Refine knowledge files based on gaps.

## Domain-Specific Considerations

- **Regulated industries** — Additional compliance guardrails, audit logging.
- **High-volume** — Scale horizontally, use fast models, enable caching.
- **Multi-language** — Use multilingual embedding models, translate knowledge files.
- **Real-time** — Use streaming, minimize latency with fast models and aggressive caching.
- **Offline-first** — Use Ollama for fully local deployment.
