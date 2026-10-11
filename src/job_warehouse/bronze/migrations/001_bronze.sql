CREATE SCHEMA bronze;

CREATE TABLE bronze.dataset_file (
    file_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_name text NOT NULL CHECK (btrim(dataset_name) <> ''),
    revision text NOT NULL CHECK (revision ~ '^[0-9a-f]{40}$'),
    artifact_path text NOT NULL CHECK (btrim(artifact_path) <> ''),
    relative_path text NOT NULL CHECK (
        relative_path <> '' AND relative_path !~ '^/'
        AND relative_path !~ '(^|/)\.\.(/|$)'
    ),
    sha256 char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    row_count bigint NOT NULL CHECK (row_count >= 0),
    schema_json jsonb NOT NULL CHECK (jsonb_typeof(schema_json) = 'object'),
    source_url text NOT NULL CHECK (btrim(source_url) <> ''),
    artifact_url text NOT NULL CHECK (btrim(artifact_url) <> ''),
    license_id text NOT NULL CHECK (btrim(license_id) <> ''),
    attribution text NOT NULL CHECK (btrim(attribution) <> ''),
    ingested_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    validation_version text NOT NULL CHECK (btrim(validation_version) <> ''),
    CONSTRAINT dataset_file_artifact_unique UNIQUE (dataset_name, revision, artifact_path)
);

COMMENT ON TABLE bronze.dataset_file IS
    'Registry of immutable historical files; no Parquet record contents are stored here.';
COMMENT ON COLUMN bronze.dataset_file.ingested_at IS
    'First successful registry reception time, not job posting time.';
