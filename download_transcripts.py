import os
import requests
import csv
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
API_KEY = os.getenv('KSCOPE_API_KEY')

DATA_DIR = 'data'
REPORT_PATH = os.path.join(DATA_DIR, 'report.csv')
API_URL = 'https://api.kscope.io/v2/transcripts/historical'

def prompt_days_back():
    while True:
        try:
            days = int(input('How many days back should transcripts be pulled? '))
            if days > 0:
                return days
        except ValueError:
            pass
        print('Please enter a valid positive integer.')

def fetch_transcripts(start_date, end_date):
    transcripts = []
    offset = 0
    limit = 10
    import time
    while True:
        params = {
            'key': API_KEY,
            'limit': limit,
            'offset': offset
        }
        from urllib.parse import urlencode
        full_url = f"{API_URL}?{urlencode(params)}"
        print(f"Requesting: {full_url}")
        try:
            resp = requests.get(API_URL, params=params)
            resp.raise_for_status()
            data = resp.json().get('data', [])
        except requests.exceptions.HTTPError as e:
            print(f"API error: {e}\nResponse: {resp.text}")
            break
        if not data:
            break
        transcripts.extend(data)
        # Stop if last transcript is older than start_date
        last_date = data[-1].get('created_at', '')[:10]
        try:
            last_dt = datetime.strptime(last_date, '%Y-%m-%d').date()
        except Exception:
            last_dt = None
        if last_dt and last_dt < start_date:
            break
        offset += limit
        time.sleep(20)  # Add a 2 second delay between requests
    return transcripts

def save_transcript(transcript):
    call_id = transcript.get('call_id')
    title = transcript.get('call_title', 'untitled')
    date = transcript.get('created_at', '')[:10]
    filename = f"{date}_{call_id}.txt"
    path = os.path.join(DATA_DIR, filename)
    text = ''
    for t in transcript.get('transcripts', []):
        text += t.get('text', '') + '\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return filename, title, date

def update_report_csv(rows):
    file_exists = os.path.isfile(REPORT_PATH)
    with open(REPORT_PATH, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(['filename', 'title', 'date', 'symbol'])
        for row in rows:
            writer.writerow(row)

def main():
    if not API_KEY:
        print('API key not found in .env file.')
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    days_back = prompt_days_back()
    # Use timezone-aware UTC date
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days_back)
    import json
    transcripts = fetch_transcripts(start_date, end_date)
    # Save full raw API response
    raw_path = os.path.join(DATA_DIR, 'raw_results.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(transcripts, f, indent=2)

    # Filter transcripts by date range
    filtered = []
    for transcript in transcripts:
        created_at = transcript.get('created_at', '')[:10]
        try:
            t_date = datetime.strptime(created_at, '%Y-%m-%d').date()
        except Exception:
            continue
        if start_date <= t_date <= end_date:
            filtered.append(transcript)
    if not filtered:
        print('No transcripts found in the specified date range.')
        return
    rows = []
    parsed_lines = []
    for transcript in filtered:
        filename, title, date = save_transcript(transcript)
        symbol = transcript.get('symbol', '')
        rows.append([filename, title, date, symbol])
        # Build human-readable summary
        summary = [
            f"Date: {date}",
            f"Title: {title}",
            f"Symbol: {symbol}",
            f"Call ID: {transcript.get('call_id')}",
            f"Exchange: {transcript.get('exchange', '')}",
            f"Headline: {transcript.get('headline', '')}",
            f"Description: {transcript.get('description', '')}",
            "Transcript:",
            "--------------------------------------------------"
        ]
        # Compile transcript content
        for t in transcript.get('transcripts', []):
            for seg in t.get('segments', []):
                speaker = seg.get('speaker', '').strip()
                text = seg.get('text', '').strip()
                if speaker:
                    summary.append(f"{speaker}: {text}")
                else:
                    summary.append(f"[Unknown Speaker]: {text}")
        summary.append("--------------------------------------------------\n")
        parsed_lines.append('\n'.join(summary))
    update_report_csv(rows)
    # Save parsed summary
    parsed_path = os.path.join(DATA_DIR, 'parsed_results.txt')
    with open(parsed_path, 'w', encoding='utf-8') as f:
        f.writelines(parsed_lines)
    print(f"Downloaded {len(rows)} transcripts in the specified date range, updated report.csv, and saved raw_results.json and parsed_results.txt.")

if __name__ == '__main__':
    main()
