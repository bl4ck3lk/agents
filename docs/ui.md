# Agents Web UI / API Guide

This UI is a thin layer over the existing CLI and processing engine. It runs locally via FastAPI and serves a static, no-build HTML page.

## Start the server

```bash
uv pip install -e .          # ensure fastapi/uvicorn/aiofiles are available
agents-api                   # starts uvicorn on 0.0.0.0:8000
# or
uvicorn agents.api.app:app --reload --port 8000
```

Then open http://localhost:8000 in your browser.

## Pages & features

### Home (/) – control panel
- **Start Run**: form that maps to `POST /runs`. Fields: input file, output file, prompt (or config path), model, API key, base URL, mode, batch size, max tokens, check-in interval, include_raw, no_post_process, no_merge. Starts a background job using the same adapters/engine as the CLI.
- **Runs table**: pulls `/runs` every 4s; shows job id, status, progress, model, started time. “View” populates the detail panel and pre-fills the results viewer with that job id.
- **Run detail**: summary of the selected run (status, progress, model/mode/batch, prompt preview).
- **Results viewer**: paginated slice from incremental JSONL via `/runs/{id}/results?offset&limit`. Useful for long-running jobs; defaults offset=0, limit=20.
- **Prompt Lab**: single prompt test via `/prompt-test`. Accepts API key, optional model, prompt, and variables JSON. Renders the prompt with variables and shows the model response.
- **Model Compare**: send the same sample to multiple models via `/compare`. Inputs: API key, comma-separated models, prompt template, sample JSON. Renders side-by-side outputs.

### Static assets
Served from `agents/api/static/` (no bundler). Files:
- `index.html` – markup and minimal JS (fetch-only, no framework).
- `style.css` – compact styling (dark theme, cards, tables, responsive grid).

## REST API
All responses are JSON; errors return HTTP 4xx/5xx with a message.

- `GET /health` → `{status:"ok"}`
- `GET /examples` → map of example config filenames to YAML contents (from `docs/examples`).
- `POST /runs` → start a run. Body (fields optional unless noted):
  - `input_file` (required), `output_file` (required), `prompt` or `config_path` (one required), `model`, `api_key` (required), `base_url`, `mode` (`sequential|async`), `batch_size`, `max_tokens`, `include_raw` (bool), `no_post_process` (bool), `no_merge` (bool), `checkin_interval`.
  - Returns `run` + `metadata`.
- `POST /runs/{job_id}/resume` → resume from checkpoint. Body: `api_key` (required), optional `checkin_interval` override.
- `GET /runs` → list runs (includes discovered checkpointed runs). Fields: job_id, status, processed/total, model, mode, batch size, timestamps, error.
- `GET /runs/{job_id}` → run detail + metadata.
- `GET /runs/{job_id}/results?offset=0&limit=50` → paginated JSONL slice; raw records include internal `_idx` and retry flags if present.
- `POST /prompt-test` → single prompt call. Body: `api_key` (required), `prompt`, `variables` (dict), optional `model`, `base_url`, `max_tokens`.
- `POST /compare` → call multiple models on the same sample. Body: `api_key` (required), `models` (list of strings), `prompt`, `sample` (dict), optional `base_url`, `max_tokens`.

## Data & storage model
- Jobs persist progress/results to `.checkpoints/` using the existing `ProgressTracker` and `IncrementalWriter`.
- The UI lists any `.progress_*.json` it finds on startup, so past CLI runs appear automatically.
- Results are stored incrementally in `.results_<job_id>.jsonl`; the results endpoint pages directly over this file.
- API keys are **not** stored in checkpoints; provide a key when starting or resuming.

## Usage tips
- For huge outputs, page with `offset/limit` instead of downloading the whole file.
- Use `checkin_interval` to enable pause prompts on long jobs; resuming requires the same job id.
- To retry failed-only rows, filter failures from the `failures_<job_id>.jsonl` that `IncrementalWriter.write_failures_file()` produces and feed them as a new input file.
- To customize styling or JS, edit `agents/api/static/index.html` and `style.css`; no build step needed.

## Troubleshooting
- 400 on `/runs`: ensure `api_key` and either `prompt` or `config_path` are provided.
- 404 on `/runs/{id}` or results: check that the job id matches the `.progress_*.json` / `.results_*.jsonl` filenames.
- Missing progress on a past run: verify `.checkpoints` exists in the current working directory; the API looks there by default.
