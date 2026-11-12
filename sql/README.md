# SQL

The production SQL lives in the dbt project (`dbt_project/models/`, `dbt_project/tests/`) so that it runs unchanged on DuckDB and BigQuery.
`analysis_examples.sql` has ready-to-run exploration queries for the DuckDB file (use the DuckDB CLI, VS Code SQLTools, or `python -c "import duckdb; ..."`).
