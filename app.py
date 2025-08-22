from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
from download_transcripts import fetch_transcripts, save_transcript, update_report_csv, write_markdown, DATA_DIR, API_KEY
from datetime import datetime, timezone

app = FastAPI()
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")

@app.get("/", response_class=HTMLResponse)
def form_get():
    return """
    <html>
        <head><title>Transcript Downloader</title></head>
        <body>
            <h2>Transcript Downloader</h2>
            <form method='post'>
                <label>Stock Symbol (leave blank for today, or type RANGE for date range):</label><br>
                <input type='text' name='symbol'><br>
                <div id='range-fields' style='display:none;'>
                    <label>Start Date (YYYY-MM-DD):</label><br>
                    <input type='text' name='start_date'><br>
                    <label>End Date (YYYY-MM-DD):</label><br>
                    <input type='text' name='end_date'><br>
                </div>
                <input type='submit' value='Download'>
            </form>
            <script>
                const symbolInput = document.querySelector('input[name="symbol"]');
                const rangeFields = document.getElementById('range-fields');
                symbolInput.addEventListener('input', function() {
                    if (symbolInput.value === 'RANGE') {
                        rangeFields.style.display = 'block';
                    } else {
                        rangeFields.style.display = 'none';
                    }
                });
            </script>
        </body>
    </html>
    """

@app.post("/", response_class=HTMLResponse)
def form_post(symbol: str = Form(...), start_date: str = Form(None), end_date: str = Form(None)):
    if not API_KEY:
        return "<h3>API key not found in .env file.</h3>"
    if symbol == 'RANGE':
        user_input = {'mode': 'range', 'start_date': start_date, 'end_date': end_date}
    elif symbol:
        user_input = {'mode': 'symbol', 'symbol': symbol}
    else:
        today = datetime.now(timezone.utc).date().strftime('%Y-%m-%d')
        user_input = {'mode': 'today', 'date': today}
    transcripts = fetch_transcripts(user_input, user_input['mode'])
    filtered = transcripts
    if user_input['mode'] == 'symbol':
        pass
    elif user_input['mode'] == 'today':
        filtered = [t for t in transcripts if t.get('created_at', '')[:10] == user_input['date']]
    elif user_input['mode'] == 'range':
        start_dt = datetime.strptime(user_input['start_date'], '%Y-%m-%d').date()
        end_dt = datetime.strptime(user_input['end_date'], '%Y-%m-%d').date()
        filtered = []
        for transcript in transcripts:
            created_at = transcript.get('created_at', '')[:10]
            try:
                t_date = datetime.strptime(created_at, '%Y-%m-%d').date()
            except Exception:
                continue
            if start_dt <= t_date <= end_dt:
                filtered.append(transcript)
    if not filtered:
        return "<h3>No transcripts found for the specified input.</h3>"
    rows = []
    for transcript in filtered:
        filename, title, date = save_transcript(transcript)
        symbol_val = transcript.get('symbol', '')
        rows.append([filename, title, date, symbol_val])
    update_report_csv(rows)
    md_path = os.path.join(DATA_DIR, 'parsed_results.md')
    write_markdown(filtered, md_path)
    # Read markdown file for display
    md_content = ""
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
    except Exception:
        md_content = "<p>Could not read markdown file.</p>"
    return f"""
    <h3>Downloaded {len(rows)} transcripts.</h3>
    <a href='/data/parsed_results.md' target='_blank'>Download Markdown</a>
    <hr>
    <h3>Transcript Summary (Markdown):</h3>
    <pre style='white-space: pre-wrap; background: #f8f8f8; padding: 1em;'>{md_content}</pre>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
