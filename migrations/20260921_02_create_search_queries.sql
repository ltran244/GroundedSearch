-- The search queries generated for each research job, in the order generated.
-- depends: 20260921_01_create_research_jobs

CREATE TABLE search_queries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id uuid NOT NULL REFERENCES research_jobs(id) ON DELETE CASCADE,
    query text NOT NULL CHECK (length(trim(query)) > 0),
    position integer NOT NULL CHECK (position >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (research_job_id, position),
    UNIQUE (research_job_id, query)
);
