# Agentic Deployment Guide (Frontend + Backend + FastAPI + Postgres + Neo4j + Supabase)

## What is added
- `rtgs_fastapi_app.py`: FastAPI backend for reconciliation, synthetic generation, and deployment bootstrap endpoints.
- `rtgs_agent_runtime.py`: agent orchestrator layer.
- `rtgs_supabase_pipeline.py`: schema creation + CSV bulk load into Supabase Postgres.
- `rtgs_neo4j_pipeline.py`: Aura connectivity validation + graph schema + edge loading.
- `frontend/`: lightweight control-tower UI.
- `docker-compose.agentic.yml`: one-file local deployment stack.
- `.env.agentic.example`: environment variable template (no secrets committed).


## Quick fix for "localhost refused to connect" (Windows)
Run this file from the project folder:
```bat
launch_agentic_local.bat
```
This opens 2 terminal windows and starts:
- Frontend on `http://localhost:3000`
- API on `http://localhost:8000`

If port 3000 is busy, close old Python server windows and retry.

Linux/macOS quick launch:
```bash
./launch_agentic_local.sh
```

## Run locally
```bash
python -m pip install fastapi uvicorn pydantic scikit-learn psycopg[binary] neo4j
uvicorn rtgs_fastapi_app:app --host 0.0.0.0 --port 8000
```

Frontend:
```bash
python -m http.server 3000 --directory frontend
```
Then open `http://localhost:3000`.

## Run full local stack (Frontend:3000 + API:8000 + Postgres + Neo4j)
```bash
docker compose -f docker-compose.agentic.yml up
```
Ports:
- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`

## Supabase deployment (direct)
Use env vars (recommended):
```bash
export SUPABASE_PROJECT_REF=kyobidaobfnngvzrkvpx
export SUPABASE_REGION=aws-1-ap-southeast-2
export SUPABASE_DB_PASSWORD='<your password>'
python rtgs_supabase_pipeline.py --project-ref "$SUPABASE_PROJECT_REF" --password "$SUPABASE_DB_PASSWORD" --region "$SUPABASE_REGION"
```

Or with full URL:
```bash
export SUPABASE_DB_URL='postgresql://postgres.<project_ref>:<password>@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres'
python rtgs_supabase_pipeline.py --db-url "$SUPABASE_DB_URL"
```

## Neo4j Aura deployment (wait + validate + load)
```bash
export NEO4J_URI='neo4j+s://<instance>.databases.neo4j.io'
export NEO4J_USERNAME='<username>'
export NEO4J_PASSWORD='<password>'
export NEO4J_DATABASE='<database>'
python rtgs_neo4j_pipeline.py --wait-seconds 60
```

Validate only:
```bash
python rtgs_neo4j_pipeline.py --wait-seconds 60 --validate-only
```

## FastAPI deployment endpoints
If env vars are set in API environment:
- `POST /deploy/supabase` → applies schema + ensures/generates synthetic dataset + loads CSVs.
- `POST /deploy/neo4j?wait_seconds=60` → waits, validates Aura connectivity, applies graph schema, loads edges.

## API endpoints
- `GET /health`
- `GET /demo/reconcile`
- `POST /reconcile`
- `POST /generate/synthetic`
- `POST /deploy/supabase`
- `POST /deploy/neo4j`


## Unified extraction (Docling -> LLM)
Run the new unified system on a file or folder:
```bash
python unified_extraction_system.py <input_file_or_folder> --output-dir unified_extraction_output
```

Use OpenRouter key securely via env var (recommended):
```bash
export OPENROUTER_API_KEY='<your_openrouter_key>'
python unified_extraction_system.py <input_file_or_folder> --output-dir unified_extraction_output
```

Notes:
- Layer-1 always tries Docling first.
- If Docling is unavailable, native extraction is used.
- LLM enrichment uses free OpenRouter models with retry/backoff to reduce rate-limit hits.
