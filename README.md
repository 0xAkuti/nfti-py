# NFT Inspector API

FastAPI service for NFT metadata inspection, interface/compliance checks, proxy and access-control detection, and trust/permanence scoring.

## What It Does

- Analyzes ERC-721 and ERC-1155 NFTs from on-chain token URIs
- Detects supported interfaces and runs optional compliance probes
- Inspects token and contract metadata hosting patterns
- Scores permanence and trustlessness with explicit assumptions
- Caches analysis results for fast reads and leaderboard queries

## Storage Backends

The API supports three persistence backends selected by `DATABASE_BACKEND`:

- `blob`: Vercel Blob
- `redis`: Redis / Vercel KV
- `supabase`: Supabase Postgres via PostgREST

Supabase setup also requires the SQL migration in `migrations/001_create_nft_analyses.sql`.

## Local Development

1. Install dependencies:
```bash
uv sync
```

2. Configure environment:
```bash
cp .env.example .env
```

3. Choose a storage backend in `.env` and set its credentials.

4. Start the API:
```bash
uv run python run_api.py
```

The API is available at `http://localhost:8000`, with docs at `http://localhost:8000/docs`.

## Key Endpoints

- `POST /api/v1/analyze`
- `GET /api/v1/analyze/{chain_id}/{contract_address}/{token_id}`
- `GET /api/v1/collection/{chain_id}/{contract_address}`
- `GET /api/v1/leaderboard`
- `GET /api/v1/stats`
- `GET /api/v1/health`

## Notes

- Fresh analyses return `TokenInfo`; cached reads return the stricter `NFTInspectionResult` shape.
- Cache reads now treat invalid stored payloads as cache misses instead of hard failures.
