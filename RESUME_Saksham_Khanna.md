# SAKSHAM KHANNA

Mumbai, Maharashtra · sakshamkhanna71@gmail.com · +91 77176 69507 · LinkedIn · GitHub

---

## EDUCATION

**Narsee Monjee College of Commerce and Economics** — Mumbai
B.Com (Economics and Analytics) | 2nd Year, 3rd Semester · Expected 2028

*Relevant coursework:* Econometrics, Statistical Modeling, Derivatives Pricing, Probability
Theory, Decision Theory (EMV/EOL/EVPI), Quantitative Research, Financial Markets

---

## TECHNICAL PROJECTS

**Securitized Products AI Surveillance Pipeline** — `github.com/sakkshamxkhanna/securitized-risk-ai` · 2026

- Built an end-to-end RMBS surveillance system that generates the monthly desk report from a
  loan-level collateral tape: stratification tapes (FICO/LTV/geography), sequential-pay tranche
  waterfall, and exposure/RWA/expected-loss analytics across a three-tranche capital structure.
- Implemented a temporal-attention **Transformer** forecasting prepayment (CPR) and default (CDR)
  speeds from macro paths, achieving **R² 0.86 / 0.97** on a 400-sequence holdout; diagnosed and
  fixed a multi-task loss-scaling failure where CDR variance was ~100× smaller than CPR, causing
  the model to emit a constant CDR (holdout R² improved from 0.10 to 0.97).
- Designed a **graph neural network** over an originator × state cohort graph to capture correlated
  default risk that loan-level hazard models structurally understate, producing a per-cohort risk
  multiplier applied to projected default speeds.
- Generated stress scenarios by sampling the latent space of a **VAE** trained on macro regime paths,
  producing plausible combinations not hand-specified; credit-stress scenarios drove cumulative
  losses to **3.2% of UPB** against a 1.2% base case, triggering automated desk escalation.
- Orchestrated the pipeline as a **LangGraph** state machine with conditional escalation routing,
  **Redis**-backed stage caching, **Docker** deployment, and a structural-invariant test suite
  (loss allocation seniority, no tranche overpayment, stratification reconciliation).
- Added a **LoRA**-adapted GPT-2 (rank-8 adapters, 0.24% of parameters trainable) to draft
  surveillance commentary in desk register; all reported figures remain deterministically computed.

**Polymarkets Algorithmic Trading & Quant Research** — `github.com/sakkshamxkhanna/Polymarkets-algo` · 2025

- Designed and backtested a multi-strategy system across prediction markets spanning oracle
  resolution, price-mismatch hedging, latency modeling, and a news/social signal crawler.
- Engineered a real-time ingestion pipeline consuming market data and social signals for dynamic
  signal generation and execution.

**Claude Obsidian Second Brain** — `github.com/sakkshamxkhanna/Claude-Obsidian-Second_brain` · 2025

- Built an AI-assisted knowledge system managing 1,000+ structured notes with contextual retrieval
  and session-persistent memory.
- Achieved a **2.76× reduction in token usage** via session-based context reloading, replacing
  full-context injection with selective retrieval and structured memory layers.

---

## WORK EXPERIENCE

**LayrAI** — Mumbai
*Founder & AI/ML Platform Builder | Financial Crime Intelligence* · Nov 2025 – Present

- Built a 12-agent LangGraph AML investigation platform covering entity resolution, transaction
  pattern analysis, behavioral profiling, and regulatory context retrieval — reducing analyst
  false-positive workload by **89%** on test-dataset evaluation.
- Architected graph-led investigation logic on **Neo4j** for entity and transaction network
  analysis, supporting real-time transaction streams and batch ingestion concurrently.
- Delivered every output with full explainability, audit trails, and case persistence to meet
  regulatory review and zero-error operational standards.
- Conducted 100+ hours of stakeholder discovery with RBI professionals, Chief Compliance Officers,
  and financial crime investigators, translating operational pain points into product requirements.
- Shipped full-stack MVP: Next.js, React, TailwindCSS, FastAPI, PostgreSQL, Neo4j, Docker, on
  AWS/GCP with LangChain/LangGraph orchestration and vector retrieval.

**Foundershala** — Mumbai
*Investment Banking Associate | Boutique IB & Financial Advisory* · Aug 2025 – Oct 2025

- Built financial models and DCF/comparable-company valuation frameworks for **18+ startups**
  across fintech, SaaS, and consumer sectors.
- Contributed to 20+ investor pitch decks and due diligence workflows supporting **$10M+** in
  aggregate fundraising across founder-led companies.
- Conducted market research, growth-metric benchmarking, and competitive analysis to support
  investment and fundraising strategy.

---

## CERTIFICATIONS

- **Machine Learning Specialization** — Stanford University / DeepLearning.AI · Completed
- **Deep Learning Specialization** — DeepLearning.AI · Completed
- **IBM Product Management Professional Certificate** — IBM · Completed
- **Calculus for Machine Learning** — Coursera · Completed
- **CFA Level 1** — CFA Institute · In Preparation

---

## SKILLS

| | |
|---|---|
| **Securitized Products** | RMBS/CMBS/ABS structures, collateral stratification, cashflow waterfalls, credit enhancement, CPR/CDR modeling, RWA & expected loss |
| **Quant / Finance** | Derivatives Pricing, Econometrics, DCF Valuation, Market Microstructure, Systematic Strategy Design, Probabilistic Forecasting |
| **Programming** | Python (advanced), SQL, VBA, JavaScript/TypeScript, FastAPI |
| **Data & Reporting** | Excel (advanced), PowerPoint, Pandas, NumPy, PostgreSQL, Neo4j |
| **ML / AI** | PyTorch, Transformers, GNNs, LSTMs, CNNs, LoRA / parameter-efficient fine-tuning, LangChain, LangGraph, RAG, Agent Orchestration |
| **Infrastructure** | Docker, Kubernetes, Redis, Apache Kafka, AWS (S3, EC2), GCP |
| **Languages** | English (fluent), Hindi (native) |

---

*Interests: Structured credit, quantitative research, financial crime intelligence, AI-native
product building, open-source tooling.*
