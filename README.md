# mad-onis (shipped build)

1. Edit `config.toml`: set `base_url` and, in `[browser]`, `channel = "chrome"`
   (or point `executable_path` at a browser binary).
2. Install deps:  `uv sync`
3. Dry run (capture + build URLs, no download):  `uv run python -m src.main --dry-run`
4. Full run:  `uv run python -m src.main`

Downloads land in the configured `output_dir`; every run also writes a log to `logs/`.
