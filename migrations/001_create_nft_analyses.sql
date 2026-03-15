-- NFT Inspector: Supabase storage backend
-- Run this migration in the Supabase SQL Editor or via CLI.

CREATE TABLE IF NOT EXISTS nft_analyses (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chain_id INTEGER NOT NULL,
    contract_address TEXT NOT NULL,
    token_id INTEGER NOT NULL,
    collection_name TEXT,
    overall_score INTEGER NOT NULL,
    permanence_score INTEGER NOT NULL,
    trustlessness_score INTEGER NOT NULL,
    overall_level TEXT NOT NULL,
    permanence_level TEXT,
    trustlessness_level TEXT,
    analysis_version TEXT NOT NULL DEFAULT '1.1',
    stored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    token_info JSONB NOT NULL,

    CONSTRAINT uq_nft UNIQUE (chain_id, contract_address, token_id)
);

CREATE INDEX IF NOT EXISTS idx_nft_score ON nft_analyses (overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_nft_chain ON nft_analyses (chain_id);
CREATE INDEX IF NOT EXISTS idx_nft_chain_contract ON nft_analyses (chain_id, contract_address);
