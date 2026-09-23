CREATE TABLE sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    research_job_id uuid NOT NULL REFERENCES research_jobs(id) ON DELETE CASCADE,
    search_query_id uuid NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    rank integer NOT NULL CHECK (rank >= 0),
    url text NOT NULL CHECK (length(trim(url)) > 0),
    title text NOT NULL,
    snippet text NOT NULL DEFAULT '',
    -- NULL until the page is fetched and its text extracted. Stays NULL if the
    -- fetch fails (paywall, 404, blocked) or the page has no readable text.
    content text,
    citation_number integer,
    retrieved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (research_job_id, url)
);
