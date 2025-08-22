# Restore markdown export
def write_markdown(transcripts, path):
    lines = []
    for transcript in transcripts:
        date = transcript.get('created_at', '')[:10]
        title = transcript.get('call_title', 'untitled')
        symbol = transcript.get('symbol', '')
        call_id = transcript.get('call_id', '')
        exchange = transcript.get('exchange', '')
        headline = transcript.get('headline', '')
        description = transcript.get('description', '')
        lines.append(f"# {title} ({symbol})\n")
        lines.append(f"**Date:** {date}")
        lines.append(f"**Call ID:** {call_id}")
        lines.append(f"**Exchange:** {exchange}")
        lines.append(f"**Headline:** {headline}")
        lines.append(f"**Description:** {description}\n")
        lines.append("## Transcript\n")
        for t in transcript.get('transcripts', []):
            for seg in t.get('segments', []):
                speaker = seg.get('speaker', '').strip()
                text = seg.get('text', '').strip()
                if speaker:
                    lines.append(f"**{speaker}:** {text}")
                else:
                    lines.append(f"**[Unknown Speaker]:** {text}")
        lines.append("\n---\n")
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
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


def prompt_user():
    symbol = input('Enter stock symbol (leave blank for today, or type RANGE for date range): ').strip()
    if symbol == 'RANGE':
        start_date = input('Enter start date (YYYY-MM-DD): ').strip()
        end_date = input('Enter end date (YYYY-MM-DD): ').strip()
        return {'mode': 'range', 'start_date': start_date, 'end_date': end_date}
    elif symbol:
        return {'mode': 'symbol', 'symbol': symbol}
    else:
        today = datetime.now(timezone.utc).date().strftime('%Y-%m-%d')
        return {'mode': 'today', 'date': today}


def fetch_transcripts(params, mode):
    transcripts = []
    offset = 0
    limit = 10
    import time
    while True:
        req_params = {'key': API_KEY}
        if mode == 'symbol':
            req_params['ticker'] = params['symbol']
            req_params['limit'] = limit
            req_params['offset'] = offset
        elif mode == 'today':
            req_params['date'] = params['date']
        elif mode == 'range':
            req_params['start_date'] = params['start_date']
            req_params['end_date'] = params['end_date']
        from urllib.parse import urlencode
        full_url = f"{API_URL}?{urlencode(req_params)}"
        print(f"Requesting: {full_url}")
        try:
            resp = requests.get(API_URL, params=req_params)
            resp.raise_for_status()
            data = resp.json().get('data', [])
        except requests.exceptions.HTTPError as e:
            print(f"API error: {e}\nResponse: {resp.text}")
            break
        if not data:
            break
        transcripts.extend(data)
        if mode == 'symbol':
            offset += limit
            time.sleep(2)
            if len(data) < limit:
                break
        else:
            break
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



    if not API_KEY:
        print('API key not found in .env file.')
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    user_input = prompt_user()
    import json
    transcripts = fetch_transcripts(user_input, user_input['mode'])
    # Save full raw API response
    raw_path = os.path.join(DATA_DIR, 'raw_results.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(transcripts, f, indent=2)

    filtered = transcripts
    if user_input['mode'] == 'symbol':
        # No date filtering, just use all returned
        pass
    elif user_input['mode'] == 'today':
        # Only keep transcripts from today
        filtered = [t for t in transcripts if t.get('created_at', '')[:10] == user_input['date']]
    elif user_input['mode'] == 'range':
        start_date = datetime.strptime(user_input['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(user_input['end_date'], '%Y-%m-%d').date()
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
        print('No transcripts found for the specified input.')
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

    # Also write markdown file
    md_path = os.path.join(DATA_DIR, 'parsed_results.md')
    write_markdown(filtered, md_path)
    print(f"Downloaded {len(rows)} transcripts, updated report.csv, saved raw_results.json, parsed_results.txt, and parsed_results.md.")

def main():
    if not API_KEY:
        print('API key not found in .env file.')
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    user_input = prompt_user()
    import json
    transcripts = fetch_transcripts(user_input, user_input['mode'])
    # Save full raw API response
    raw_path = os.path.join(DATA_DIR, 'raw_results.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(transcripts, f, indent=2)

    filtered = transcripts
    if user_input['mode'] == 'symbol':
        # No date filtering, just use all returned
        pass
    elif user_input['mode'] == 'today':
        # Only keep transcripts from today
        filtered = [t for t in transcripts if t.get('created_at', '')[:10] == user_input['date']]
    elif user_input['mode'] == 'range':
        start_date = datetime.strptime(user_input['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(user_input['end_date'], '%Y-%m-%d').date()
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
        print('No transcripts found for the specified input.')
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
    print(f"Downloaded {len(rows)} transcripts, updated report.csv, and saved raw_results.json and parsed_results.txt.")

if __name__ == '__main__':
    main()
