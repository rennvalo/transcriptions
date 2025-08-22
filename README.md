SmallCapSignal — Transcript Downloader

Overview

This repository provides a small service that downloads company transcripts from the KScope API, saves raw and parsed copies, and exposes a simple web UI so non-technical users can request transcripts by stock symbol, by single date (today) or by date range.

This README explains how the pieces fit together and gives step-by-step instructions so someone with zero prior experience can reproduce a fully working environment locally or using Docker.

Project layout

- `app.py` — FastAPI web wrapper: GET `/` serves a simple HTML form; POST `/` handles the form, calls the downloader functions, writes `data/parsed_results.md`, and returns the parsed markdown in the browser. The folder `data/` is mounted as static at `/data`.
- `download_transcripts.py` — Core logic for communicating with the API: `fetch_transcripts(params, mode)`, `save_transcript()`, `update_report_csv()`, `write_markdown()`, and a CLI entry `cli_run()` (guarded so it does not run on import).
- `data/` — Persistent directory where raw JSON, parsed Markdown, and individual transcript `.txt` files are written. This folder is served by FastAPI at `/data`.
- `Dockerfile`, `docker-compose.yml` — Containerization artifacts to run the service in Docker.

Requirements

- OS: Windows / macOS / Linux (examples below use PowerShell but Linux/macOS terminals are easily adapted).
- Python 3.10+ (3.11 recommended)
- Docker & Docker Compose (optional, for containerized deployment)

Files to add (one-time)

Create a `.env` file in the repo root containing the KScope API key (the service expects an environment variable named `KSCOPE_API_KEY`):

```
KSCOPE_API_KEY=your_kscope_api_key_here
```

Quick environment & dependencies

A `requirements.txt` is provided. From a PowerShell prompt in the repo directory:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run locally (development)

1. Ensure the `.env` file contains your API key (see above).
2. Start the app using Uvicorn:

```powershell
# from repository root
$env:KSCOPE_API_KEY = 'your_api_key_here' # or rely on .env loader
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

3. Open a browser and visit: http://127.0.0.1:8000

Using the web form

- Enter a stock symbol (e.g. AAPL) to download transcripts for that ticker (paginated by API).
- Leave the symbol blank to request transcripts for today.
- Type `RANGE` (exactly) in the symbol field to reveal Start/End date fields; supply `YYYY-MM-DD` values and submit to fetch transcripts within that date range.

What the service does on submission

- Calls `fetch_transcripts(user_input, mode)` in `download_transcripts.py` to query the API.
- Saves the full raw JSON to `data/raw_results.json`.
- Writes individual transcript text files to `data/<YYYY-MM-DD>_<call_id>.txt`.
- Appends metadata rows to `data/report.csv`.
- Writes a human-readable `data/parsed_results.md` (and `parsed_results.txt`) and renders the markdown in the browser.

Endpoints

- GET `/` — Returns the HTML form.
- POST `/` — Form submission. Accepts `symbol`, `start_date`, `end_date` form fields. When successful, returns a page showing the Markdown summary and link to `/data/parsed_results.md`.
- Static files: `/data/*` — Serves the files under the `data` folder (download transcript .txt, parsed markdown, raw JSON).

requirements.txt

A minimal `requirements.txt` is provided with the project. Install with `pip install -r requirements.txt`.

Docker (containerized run)

A `Dockerfile` and `docker-compose.yml` are included to run the service in a container.

1. Create a `.env` file with `KSCOPE_API_KEY` as above.
2. Build and run with Docker Compose (PowerShell):

```powershell
docker-compose up --build
```

This will map port 8000 on the host to the container and mount the local `data/` folder so outputs persist on the host.

Troubleshooting

- API key missing or invalid
  - Symptom: The web UI returns "API key not found in .env file." or the logs show authentication errors from the API.
  - Fix: Ensure `.env` is present at repo root with `KSCOPE_API_KEY=...` and that the running process has access to it. For Docker, you can add `env_file: .env` in the `docker-compose.yml` service section or pass an environment variable.

- Import-time prompts / EOFError when running under FastAPI
  - Symptom: When the FastAPI app imports `download_transcripts`, it triggers `input()` resulting in EOFError.
  - Fix: The project places interactive `input()` calls inside `cli_run()` and `prompt_user()` which are only invoked when `download_transcripts.py` is executed directly (the `if __name__ == '__main__'` guard). If you still see interactive prompts at import, ensure `download_transcripts.py` in your working tree matches the repository version (no stray top-level code). Use `git status`/`git diff` to verify.

- Docker build/network/timeouts
  - Symptom: Docker container fails to reach the API, or requests time out.
  - Fix: Ensure the host has outbound network access from the container. Increase request timeouts in `download_transcripts.py` (the code sets a 30-second timeout). Also increase retries or verify API key/quota with KScope.

- File permission issues writing `data/`
  - Symptom: Exceptions when writing files (permission denied).
  - Fix: Ensure your user (or the container user) has write access to the `data/` directory. For Docker, the host folder ownership may need adjustment or configure a volume with proper permissions.

Developer notes: How it fits together

- `app.py` imports helper functions from `download_transcripts.py` and exposes a small HTML form. It uses FastAPI's StaticFiles to serve `data/` at `/data` so output files are directly downloadable.
- `download_transcripts.py` contains pure functions:
  - `fetch_transcripts(params, mode)` — builds the API query according to `mode` (symbol/today/range). For symbols it paginates; for date/range it requests by date parameters.
  - `save_transcript(transcript)` — writes a minimal cleaned transcript `.txt` file to `data/` and returns metadata for the CSV.
  - `update_report_csv(rows)` — appends rows to `data/report.csv` adding headers when the file is first created.
  - `write_markdown(transcripts, path)` — creates a human-readable markdown summary at `data/parsed_results.md`.
  - `cli_run()` — a convenience entry point that wraps the CLI prompt flow and calls the above functions.

Security

- Keep your `KSCOPE_API_KEY` secret. Do not commit `.env` to source control. Use `.gitignore` to prevent committing the `.env` file.
- If deploying publicly, restrict access to the service (add auth) or run behind a VPN / internal network.

Next steps & improvements

- Add small unit tests for `fetch_transcripts` (mocking requests) and for `write_markdown`.
- Improve error handling and retry logic for transient API failures.
- Add rate-limit handling and exponential backoff when paginating large symbol result sets.
- Add a richer UI to show progress and let users download individual transcripts directly.

Contact

If you want, I can also add a `README` section with example requests, or create a `Makefile` / PowerShell script to automate environment setup. Tell me which you'd prefer and I'll add it.
