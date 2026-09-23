-- One row per research question; tracks the job from creation to answer.

CREATE TABLE research_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query text NOT NULL CHECK (length(trim(query)) > 0),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    answer text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz
);
