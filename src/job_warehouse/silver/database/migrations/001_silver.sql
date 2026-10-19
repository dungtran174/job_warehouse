CREATE SCHEMA silver;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE silver.jobs (
    id bigint PRIMARY KEY CHECK (id > 0),
    job_title varchar NOT NULL CHECK (btrim(job_title) <> ''),
    company_name varchar,
    salary_min numeric(18,2) CHECK (salary_min >= 0 AND salary_min <> 'NaN'),
    salary_max numeric(18,2) CHECK (salary_max >= 0 AND salary_max <> 'NaN'),
    location varchar[] NOT NULL CHECK (
        cardinality(location) > 0 AND array_ndims(location) = 1
        AND array_position(location, NULL) IS NULL
        AND array_position(location, '') IS NULL
    ),
    job_type varchar,
    job_industry varchar NOT NULL CHECK (btrim(job_industry) <> ''),
    experience_min_years numeric(6,2)
        CHECK (experience_min_years >= 0 AND experience_min_years <> 'NaN'),
    experience_max_years numeric(6,2)
        CHECK (experience_max_years >= 0 AND experience_max_years <> 'NaN'),
    education_level varchar,
    job_position varchar,
    requirements text,
    year smallint NOT NULL CHECK (year BETWEEN 2022 AND 2026),
    CHECK (salary_min <= salary_max),
    CHECK (experience_min_years <= experience_max_years)
);
CREATE TABLE silver.job_skill_match (
    job_id bigint NOT NULL REFERENCES silver.jobs(id),
    skill_code varchar NOT NULL CHECK (btrim(skill_code) <> ''),
    skill_name varchar NOT NULL CHECK (btrim(skill_name) <> ''),
    PRIMARY KEY (job_id, skill_code)
);
CREATE TABLE ops.silver_load_run (
    run_id uuid PRIMARY KEY,
    input_fingerprint varchar NOT NULL CHECK (input_fingerprint ~ '^[0-9a-f]{64}$'),
    input_manifest jsonb NOT NULL CHECK (jsonb_typeof(input_manifest) = 'object'),
    loader_version varchar NOT NULL CHECK (btrim(loader_version) <> ''),
    status varchar NOT NULL CHECK (status IN ('running', 'published', 'failed')),
    expected_counts jsonb NOT NULL CHECK (jsonb_typeof(expected_counts) = 'object'),
    actual_counts jsonb CHECK (jsonb_typeof(actual_counts) = 'object'),
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz,
    is_current boolean NOT NULL DEFAULT false,
    CHECK (NOT is_current OR status = 'published'),
    CHECK ((status = 'running') = (finished_at IS NULL)),
    CHECK (finished_at IS NULL OR finished_at >= started_at),
    CHECK (status <> 'published' OR actual_counts IS NOT NULL)
);
CREATE UNIQUE INDEX silver_one_current_load ON ops.silver_load_run (is_current)
    WHERE is_current;
