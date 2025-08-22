import os
import requests
import csv
import json
import time
import re
from datetime import datetime, timezone
from dotenv import load_dotenv
from urllib.parse import urlencode

# Load API key from .env
load_dotenv()
API_KEY = os.getenv('KSCOPE_API_KEY')

DATA_DIR = 'data'
REPORT_PATH = os.path.join(DATA_DIR, 'report.csv')
API_URL = 'https://api.kscope.io/v2/transcripts/historical'


def prompt_user():
    """Interactive prompt for CLI use only.

    Returns a dict with 'mode' and related keys:
      - {'mode': 'symbol', 'symbol': 'AAPL'}
      - {'mode': 'today', 'date': 'YYYY-MM-DD'}
      - {'mode': 'range', 'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD'}
    """
    symbol = input('Enter stock symbol (leave blank for today, or type RANGE for date range): ').strip()
    if symbol.upper() == 'RANGE':
        start_date = input('Enter start date (YYYY-MM-DD): ').strip()
        end_date = input('Enter end date (YYYY-MM-DD): ').strip()
        return {'mode': 'range', 'start_date': start_date, 'end_date': end_date}
    elif symbol:
        return {'mode': 'symbol', 'symbol': symbol}
    else:
        today = datetime.now(timezone.utc).date().strftime('%Y-%m-%d')
        return {'mode': 'today', 'date': today}


def fetch_transcripts(params, mode):
    """Fetch transcripts from API for the given mode and params.

    - mode 'symbol' expects params['symbol'] and will paginate.
    - mode 'today' expects params['date'] (YYYY-MM-DD).
    - mode 'range' expects params['start_date'] and params['end_date'].

    Returns a list of transcript dicts (possibly empty).
    """
    if not API_KEY:
        raise RuntimeError('API key not configured in environment')

    transcripts = []
    offset = 0
    limit = 50  # larger page size to reduce requests

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
        else:
            raise ValueError('Unknown mode')

        try:
            resp = requests.get(API_URL, params=req_params, timeout=30)
            resp.raise_for_status()
            data = resp.json().get('data', [])
        except requests.exceptions.RequestException as e:
            # Return what we have so caller can handle partial results
            print(f'API request failed: {e}')
            return transcripts

        if not data:
            break

        transcripts.extend(data)

        if mode == 'symbol':
            if len(data) < limit:
                break
            offset += limit
            time.sleep(0.5)
        else:
            break

    return transcripts


def save_transcript(transcript):
    os.makedirs(DATA_DIR, exist_ok=True)
    call_id = transcript.get('call_id') or 'unknown'
    title = transcript.get('call_title', 'untitled')
    date = transcript.get('created_at', '')[:10] or datetime.now().date().isoformat()
    filename = f"{date}_{call_id}.txt"
    path = os.path.join(DATA_DIR, filename)

    # Attempt to extract readable text
    text_parts = []
    for block in transcript.get('transcripts', []):
        # API shapes differ; try multiple keys
        if isinstance(block, dict):
            if 'text' in block:
                text_parts.append(block.get('text', ''))
            elif 'segments' in block:
                for seg in block.get('segments', []):
                    text_parts.append(seg.get('text', ''))
        elif isinstance(block, str):
            text_parts.append(block)

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(text_parts))

    return filename, title, date


def update_report_csv(rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    file_exists = os.path.isfile(REPORT_PATH)
    with open(REPORT_PATH, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(['filename', 'title', 'date', 'symbol'])
        for row in rows:
            writer.writerow(row)


def write_markdown(transcripts, path):
    os.makedirs(os.path.dirname(path) or DATA_DIR, exist_ok=True)
    lines = []
    for transcript in transcripts:
        date = transcript.get('created_at', '')[:10]
        title = transcript.get('call_title', 'untitled')
        symbol = transcript.get('symbol', '')
        call_id = transcript.get('call_id', '')
        exchange = transcript.get('exchange', '')
        headline = transcript.get('headline', '')
        description = transcript.get('description', '')

        lines.append(f'# {title} ({symbol})')
        lines.append('')
        lines.append(f'**Date:** {date}')
        lines.append(f'**Call ID:** {call_id}')
        lines.append(f'**Exchange:** {exchange}')
        lines.append(f'**Headline:** {headline}')
        lines.append(f'**Description:** {description}')
        lines.append('')
        lines.append('## Transcript')
        # Collect speaker names from available fields (segments, block-level speaker,
        # or from leading "Name:" patterns in text) so we can list them up front.
        speakers = set()
        for block in transcript.get('transcripts', []):
            if isinstance(block, dict):
                # block may carry a speaker or contain segments with speakers
                if 'speaker' in block and block.get('speaker'):
                    speakers.add(block.get('speaker').strip())
                if 'segments' in block:
                    for seg in block.get('segments', []):
                        sp = seg.get('speaker') if isinstance(seg, dict) else None
                        if sp:
                            speakers.add(sp.strip())
                        # some APIs use different keys
                        elif isinstance(seg, dict):
                            sp2 = seg.get('speaker_name') or seg.get('speakerName') or seg.get('speakerId')
                            if sp2:
                                speakers.add(str(sp2).strip())
            elif isinstance(block, str):
                # try to extract leading 'Name:' style speaker tokens from raw text
                m = re.match(r"^([A-Z][A-Za-z .'\-]{1,60}):", block)
                if m:
                    speakers.add(m.group(1).strip())

        # Fallback: try scanning segment texts for leading "Name:" patterns if no speakers found
        if not speakers:
            for block in transcript.get('transcripts', []):
                if isinstance(block, dict) and 'segments' in block:
                    for seg in block.get('segments', []):
                        text = (seg.get('text') or '').strip() if isinstance(seg, dict) else ''
                        m = re.match(r"^([A-Z][A-Za-z .'\-]{1,60}):", text)
                        if m:
                            speakers.add(m.group(1).strip())
                elif isinstance(block, str):
                    text = block.strip()
                    m = re.match(r"^([A-Z][A-Za-z .'\-]{1,60}):", text)
                    if m:
                        speakers.add(m.group(1).strip())

        speaker_line = '**Speakers:** ' + (', '.join(sorted(speakers)) if speakers else 'Unknown')
        lines.append(speaker_line)

        for block in transcript.get('transcripts', []):
            if isinstance(block, dict) and 'segments' in block:
                for seg in block.get('segments', []):
                    speaker = seg.get('speaker', '').strip()
                    text = seg.get('text', '').strip()
                    if speaker:
                        lines.append(f'**{speaker}:** {text}')
                    else:
                        # If no explicit speaker field, try to parse a leading "Name: text" pattern
                        m = re.match(r"^([A-Z][A-Za-z .'\-]{1,60}):\s*(.*)$", text)
                        if m:
                            lines.append(f'**{m.group(1)}:** {m.group(2)}')
                        else:
                            lines.append(text)
            elif isinstance(block, dict) and 'text' in block:
                lines.append(block.get('text', ''))
            elif isinstance(block, str):
                lines.append(block)

        lines.append('\n---\n')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def cli_run():
    if not API_KEY:
        print('API key not found in .env file.')
        return

    user_input = prompt_user()
    transcripts = fetch_transcripts(user_input, user_input['mode'])

    # Save raw JSON
    os.makedirs(DATA_DIR, exist_ok=True)
    raw_path = os.path.join(DATA_DIR, 'raw_results.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(transcripts, f, indent=2)

    # Filter according to mode
    filtered = transcripts
    if user_input['mode'] == 'today':
        filtered = [t for t in transcripts if t.get('created_at', '')[:10] == user_input['date']]
    elif user_input['mode'] == 'range':
        try:
            start_date = datetime.fromisoformat(user_input['start_date']).date()
            end_date = datetime.fromisoformat(user_input['end_date']).date()
        except Exception:
            print('Invalid date format for range; expected YYYY-MM-DD')
            return
        filtered = []
        for t in transcripts:
            created = t.get('created_at', '')[:10]
            try:
                cd = datetime.fromisoformat(created).date()
            except Exception:
                continue
            if start_date <= cd <= end_date:
                filtered.append(t)

    if not filtered:
        print('No transcripts found for the specified input.')
        return

    rows = []
    for t in filtered:
        filename, title, date = save_transcript(t)
        rows.append([filename, title, date, t.get('symbol', '')])

    update_report_csv(rows)

    parsed_path = os.path.join(DATA_DIR, 'parsed_results.txt')
    parsed_lines = []
    for t in filtered:
        date = t.get('created_at', '')[:10]
        title = t.get('call_title', 'untitled')
        symbol = t.get('symbol', '')
        parsed_lines.append(f'Date: {date}')
        parsed_lines.append(f'Title: {title}')
        parsed_lines.append(f'Symbol: {symbol}')
        parsed_lines.append(f'Call ID: {t.get("call_id")}')
        parsed_lines.append('')
        # Add transcript text
        for block in t.get('transcripts', []):
            if isinstance(block, dict) and 'segments' in block:
                for seg in block.get('segments', []):
                    speaker = seg.get('speaker', '').strip()
                    text = seg.get('text', '').strip()
                    if speaker:
                        parsed_lines.append(f'{speaker}: {text}')
                    else:
                        parsed_lines.append(text)
            elif isinstance(block, dict) and 'text' in block:
                parsed_lines.append(block.get('text', ''))
            elif isinstance(block, str):
                parsed_lines.append(block)
        parsed_lines.append('\n' + '-' * 50 + '\n')

    with open(parsed_path, 'w', encoding='utf-8') as f:
        f.writelines([line + '\n' for line in parsed_lines])

    md_path = os.path.join(DATA_DIR, 'parsed_results.md')
    write_markdown(filtered, md_path)

    print(f"Downloaded {len(rows)} transcripts, updated report.csv, saved raw_results.json, parsed_results.txt, and parsed_results.md.")


if __name__ == '__main__':
    cli_run()
