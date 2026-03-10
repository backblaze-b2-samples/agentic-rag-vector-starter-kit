<!-- last_verified: 2026-03-10 -->
# Agentic RAG Vector Starter Kit

An open-source starter kit for building production-ready **Agentic RAG** (Retrieval-Augmented Generation) applications. Upload documents, automatically process them into searchable vectors, and chat with your knowledge base using a 9-step agentic retrieval pipeline — all backed by **[Backblaze B2](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=oss-starter)** cloud storage and **LanceDB** vector store.

**What you get out of the box:**
- ChatGPT/Claude-style chat UI with streaming responses and source citations
- Document processing pipeline: chunking, classification, summarization, and embedding
- 9-step agentic retrieval: intent routing, query planning, vector search, RRF fusion, LLM reranking, evidence validation with retry loops
- LanceDB vector store on B2 (no separate vector DB infrastructure)
- LangChain orchestration for LLM and embedding calls
- File upload with drag-and-drop, progress tracking, and RAG processing status
- Full-stack dashboard UI (Next.js 16 + React 19 + Tailwind v4 + shadcn/ui)
- FastAPI backend with strict layered architecture and structural tests
- Agent-optimized docs — your AI coding agent can read the repo and start contributing immediately

## Agent-First Architecture

This repo is optimized for coding agents. Use the template, point your agent at it, and start building.

The structure follows the principle that **repository knowledge is the system of record**. Anything an agent can't access in-context doesn't exist — so everything it needs to reason about the codebase is versioned, co-located, and discoverable from the repo itself.

### How it works

**[AGENTS.md](AGENTS.md) is the single source of truth for all coding agents.** A ~100 line entry point gives agents the repository layout, architectural invariants, commands, conventions, and pointers to deeper docs. Agent-specific files (CLAUDE.md, .cursorrules, etc.) are thin pointers back to AGENTS.md.

**Architecture is enforced mechanically, not by convention.** Layering rules, import boundaries, file size limits, and SDK containment are verified by structural tests and lints that run on every change. When rules are enforceable by code, agents follow them reliably.

**The knowledge base is structured for progressive disclosure:**

```
AGENTS.md              Single source of truth — layout, invariants, commands, conventions
ARCHITECTURE.md        System layout, layering rules, data flows
docs/
  features/            Feature docs (inputs, outputs, flows, edge cases)
  app-workflows.md     User journeys
  dev-workflows.md     Engineering workflows and testing
  SECURITY.md          Security principles
  RELIABILITY.md       Reliability expectations
  exec-plans/          Execution plans and tech debt tracker
```

### Key design decisions

| Principle | Implementation |
|-----------|---------------|
| Give agents a single source of truth | AGENTS.md ~100 lines — layout, invariants, commands, conventions |
| Enforce invariants mechanically | Structural tests + ruff + ESLint verify boundaries |
| DRY documentation | Each fact lives in one place; no redundant files to drift |
| Strict layered architecture | `types -> config -> repo -> service -> runtime`, enforced by tests |
| Prefer boring, composable libraries | stdlib logging over frameworks, Pydantic over ad-hoc validation |
| Contain external SDKs | `boto3`, `lancedb`, `langchain*` only in `repo/` — verified by structural tests |
| Keep files agent-sized | 300-line limit per file, enforced by test |
| Docs updated with code | Same-PR requirement prevents documentation rot |
| Structured observability | JSON logging, `/metrics` endpoint, request tracing |

This approach draws from [OpenAI's experience building with Codex](https://openai.com/index/harness-engineering/): agents work best in environments with strict boundaries, predictable structure, and progressive context disclosure.

## Quick Start

You need: Node.js >= 20, pnpm >= 9, Python >= 3.11, and a free **[Backblaze B2 account](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=oss-starter)**.

### Start a new project

**Option 1: GitHub Template (recommended)**

Click the green **"Use this template"** button at the top of this repo, name your project, then:

```bash
git clone https://github.com/yourorg/my-cool-app.git
cd my-cool-app
```

**Option 2: Clone and reinitialize**

```bash
git clone https://github.com/backblaze-b2-samples/agentic-rag-vector-starter-kit.git my-rag-app
cd my-rag-app
rm -rf .git
git init
git add .
git commit -m "Initial commit from agentic-rag-vector-starter-kit"
```

Either way you get a clean project with no upstream history — ready to push to your own repo and point your agent at it.

### Setup

**1. Install dependencies**

```bash
pnpm install
```

**2. Set up the backend**

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../..
```

**3. Add your B2 credentials**

Create a bucket and an application key in your [B2 dashboard](https://secure.backblaze.com/b2_buckets.htm?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=oss-starter) (the key needs `readFiles`, `writeFiles`, `deleteFiles` permissions), then:

```bash
cp .env.example .env
```

Fill in your `.env`:

```
# B2 storage (required)
B2_S3_ENDPOINT=https://s3.us-west-004.backblazeb2.com
B2_APPLICATION_KEY_ID=your-key-id
B2_APPLICATION_KEY=your-key
B2_BUCKET_NAME=your-bucket

# LLM (required for chat, classification, reranking)
ANTHROPIC_API_KEY=your-anthropic-key
# LLM_MODEL=claude-sonnet-4-20250514  # optional, default shown

# Embeddings (required for RAG)
OPENAI_API_KEY=your-openai-key
# EMBEDDING_MODEL=text-embedding-3-small  # optional, default shown
```

See `.env.example` for all options including `LANCEDB_URI`, `CHUNK_SIZE`, and `MAX_CHUNKS_PER_DOC`.

**4. Run it**

```bash
pnpm dev
```

That's it. Frontend at `localhost:3000`, API at `localhost:8000`. Upload a document and ask it questions in the Chat page.

For production deployment, see [Railway docs](infra/railway/README.md).

## Core Features

- [Chat UI](docs/features/chat.md) — ChatGPT/Claude-style interface with streaming and citations
- [Agentic Retrieval](docs/features/agentic-retrieval.md) — 9-step RAG pipeline with intent routing, query planning, reranking
- [Document Pipeline](docs/features/document-pipeline.md) — automatic chunking, classification, summarization, embedding
- [File Upload](docs/features/file-upload.md) — drag-and-drop upload with real-time progress and RAG processing
- [File Browser](docs/features/file-browser.md) — list, preview, download, delete files
- [Dashboard](docs/features/dashboard.md) — stats cards, upload chart, recent uploads
- [Metadata Extraction](docs/features/metadata-extraction.md) — image dimensions, EXIF, PDF info, checksums
- Structural tests — verify layering rules, import boundaries, SDK containment, file size limits
- Structured JSON logging — every request traced with `request_id` and timing
- `/health` endpoint — B2 connectivity check
- `/metrics` endpoint — Prometheus-format counters (request count, latency, uploads)

## Tech Stack

- TypeScript, Next.js 16, React 19, Tailwind v4, shadcn/ui, Recharts
- Python 3.11+, FastAPI, Pydantic v2, Pillow, PyPDF2
- LanceDB (vector store on S3/B2), LangChain (LLM orchestration)
- Anthropic Claude (chat, classification, reranking), OpenAI (embeddings)
- Backblaze B2 (S3-compatible object storage — files + vectors)
- pnpm workspaces (monorepo)

## Commands

| Command | What it does |
|---------|-------------|
| `pnpm dev` | Start frontend + backend |
| `pnpm dev:web` | Frontend only |
| `pnpm dev:api` | Backend only |
| `pnpm build` | Build frontend |
| `pnpm lint` | Lint frontend |
| `pnpm lint:api` | Lint backend (ruff) |
| `pnpm test:api` | Run backend tests |
| `pnpm check:structure` | Verify layering rules |
| `pnpm test:e2e` | Playwright e2e tests |

## Documentation Map

| Doc | Purpose |
|-----|---------|
| [AGENTS.md](AGENTS.md) | Agent table of contents — start here |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System layout, layering, data flows |
| [docs/features/](docs/features/) | Feature docs (chat, retrieval, pipeline, upload, browser, dashboard) |
| [docs/app-workflows.md](docs/app-workflows.md) | User journeys |
| [docs/dev-workflows.md](docs/dev-workflows.md) | Engineering workflows and testing |
| [docs/SECURITY.md](docs/SECURITY.md) | Security principles |
| [docs/RELIABILITY.md](docs/RELIABILITY.md) | Reliability expectations |
| [docs/exec-plans/](docs/exec-plans/) | Execution plans and tech debt tracker |

## Contributing

Start with [AGENTS.md](AGENTS.md). It's the map — everything else is discoverable from there.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Claude Agent B2 Skill

Manage Backblaze B2 from your terminal using natural language (list/search, audits, stale or large file detection, security checks, safe cleanup).

Repo: [https://github.com/backblaze-b2-samples/claude-skill-b2-cloud-storage](https://github.com/backblaze-b2-samples/claude-skill-b2-cloud-storage)