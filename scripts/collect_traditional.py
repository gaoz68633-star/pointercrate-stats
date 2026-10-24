"""Collect and analyze the traditional, rated-only Pointercrate Top 150.

Use rated_position for ranks. Never assume the API's position field or an
unverified query parameter means traditional Demonlist rank.
"""
import argparse
import csv
import gzip
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)


def fetch(endpoint, params):
    url = 'https://pointercrate.com' + endpoint + '?' + urlencode(params)
    for attempt in range(5):
        try:
            request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Pointercrate-Stats/2.0 (public statistics)'})
            with urlopen(request, timeout=25) as response:
                rows = json.load(response)
            assert isinstance(rows, list), f'Unexpected response from {url}'
            time.sleep(.35)
            return rows
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 4:
                raise
        time.sleep(min(30, 2 ** (attempt + 1)))


def get_traditional_levels():
    all_rows, after = [], 0
    while True:
        batch = fetch('/api/v2/demons/listed/', {'limit': 100, 'after': after})
        assert batch, 'Could not obtain all 150 traditional ranks'
        assert min(d['position'] for d in batch) > after
        all_rows.extend(batch)
        selected = [d for d in all_rows if d['rated'] is True and isinstance(d.get('rated_position'), int) and 1 <= d['rated_position'] <= 150]
        if {d['rated_position'] for d in selected} == set(range(1, 151)):
            break
        after = max(d['position'] for d in batch)
    selected.sort(key=lambda d: d['rated_position'])
    assert [d['rated_position'] for d in selected] == list(range(1, 151))
    assert len({d['id'] for d in selected}) == 150
    assert all(d['rated'] and d['verifier'].get('id') is not None for d in selected)
    return selected


def signature(levels):
    return [(d['id'], d['position'], d['rated_position'], d['verifier']['id']) for d in levels]


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def collect():
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')
    levels = get_traditional_levels()
    by_id = {d['id']: d for d in levels}
    upper_global_position = max(d['position'] for d in levels)
    print(f'Confirmed 150 rated levels, rated_position 1-150; global position ceiling {upper_global_position}', flush=True)
    after, records, seen, downloaded, skipped = None, [], set(), 0, 0
    while True:
        # This is a verified global-position filter. Client-side ID membership
        # then excludes all unrated levels inside that global range.
        params = {'limit': 100, 'progress': 100, 'status': 'approved', 'demon_position__lt': upper_global_position+1}
        if after is not None:
            params['after'] = after
        batch = fetch('/api/v1/records/', params)
        if not batch:
            break
        ids = [int(r['id']) for r in batch]
        assert len(set(ids)) == len(ids) and not seen.intersection(ids), 'Repeated record IDs'
        assert after is None or min(ids) > after, 'Pagination did not advance'
        for r in batch:
            assert r['progress'] == 100 and r['status'] == 'approved'
            demon = r['demon']
            assert 1 <= demon['position'] <= upper_global_position, 'Server ignored global position filter'
            if demon['id'] not in by_id:
                # Confirm that rejected rows do not belong to the traditional Top 150.
                assert demon.get('rated_position') is None or not 1 <= demon['rated_position'] <= 150
                skipped += 1
                continue
            expected = by_id[demon['id']]
            assert demon['position'] == expected['position']
            assert demon.get('rated_position') == expected['rated_position']
            records.append(r)
        downloaded += len(batch)
        seen.update(ids)
        after = max(ids)
        if downloaded % 1000 == 0 or len(batch) < 100:
            print(f'Downloaded {downloaded:,}; traditional records {len(records):,}; excluded unrated records {skipped}', flush=True)
    assert signature(get_traditional_levels()) == signature(levels), 'Ranks/verifiers changed during collection; rerun'
    finished = datetime.now(timezone.utc).isoformat(timespec='seconds')
    payload = json.dumps(records, ensure_ascii=False, separators=(',', ':')).encode()
    with (DATA/'records.json.gz').open('wb') as file:
        with gzip.GzipFile(filename='', mode='wb', fileobj=file, mtime=0) as zipped:
            zipped.write(payload)
    save_json(DATA/'levels.json', levels)
    metadata = {'started_at_utc': started, 'finished_at_utc': finished, 'rankings_and_verifiers_unchanged': True, 'list_type': 'traditional_demonlist', 'rank_field': 'rated_position', 'all_selected_levels_rated': True, 'selected_level_count': 150, 'maximum_global_position_used_for_fetch': upper_global_position, 'downloaded_record_rows': downloaded, 'excluded_unrated_record_rows': skipped, 'records_uncompressed_sha256': hashlib.sha256(payload).hexdigest()}
    save_json(DATA/'collection.json', metadata)
    return levels, records, metadata


def write_csv(name, rows, fields=None):
    with (ROOT/name).open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=fields or list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def analyze(levels, records, metadata):
    assert [d['rated_position'] for d in levels] == list(range(1,151))
    assert all(d['rated'] for d in levels)
    rank_by_id = {d['id']: d['rated_position'] for d in levels}
    approved, combined, on_level, names = defaultdict(set), defaultdict(set), defaultdict(set), {}
    for r in records:
        assert r['progress'] == 100 and r['status'] == 'approved'
        rank, pid = rank_by_id[r['demon']['id']], r['player']['id']
        approved[pid].add(rank)
        combined[pid].add(rank)
        on_level[rank].add(pid)
        names[pid] = r['player']['name']
    for d in levels:
        verifier = d['verifier']
        combined[verifier['id']].add(d['rated_position'])
        names[verifier['id']] = verifier['name']
    record_hardest = {pid: min(ranks) for pid, ranks in approved.items()}
    hardest = {pid: min(ranks) for pid, ranks in combined.items()}
    histogram, record_histogram = Counter(hardest.values()), Counter(record_hardest.values())
    rows, cumulative, record_cumulative, zero_audit = [], 0, 0, []
    for d in levels:
        n = d['rated_position']
        cumulative += histogram[n]
        record_cumulative += record_histogram[n]
        # Independent player-set check for each threshold, including #75/#150.
        assert cumulative == sum(any(rank <= n for rank in ranks) for ranks in combined.values())
        assert record_cumulative == sum(any(rank <= n for rank in ranks) for ranks in approved.values())
        rows.append({'rank': n, 'level_name': d['name'], 'hardest_players_including_verifiers': histogram[n], 'cumulative_including_verifiers': cumulative, 'hardest_players_approved_records_only': record_histogram[n], 'cumulative_approved_records_only': record_cumulative})
        if not histogram[n]:
            verifier = d['verifier']
            vhardest = hardest[verifier['id']]
            assert vhardest < n
            zero_audit.append({'rank': n, 'level_name': d['name'], 'hardest_players_including_verifiers': 0, 'level_clearers_including_verifier': len(on_level[n] | {verifier['id']}), 'verifier_id': verifier['id'], 'verifier_name': verifier['name'], 'verifier_hardest_rank': vhardest, 'verifier_hardest_level': levels[vhardest-1]['name']})
    assert cumulative == len(combined) and record_cumulative == len(approved)
    write_csv('hardest_by_rank.csv', rows)
    write_csv('zero_bin_audit.csv', zero_audit)
    player_rows = [{'player_id': pid, 'player_name': names[pid], 'hardest_traditional_rank': hardest[pid], 'hardest_level': levels[hardest[pid]-1]['name'], 'hardest_rank_approved_records_only': record_hardest.get(pid, ''), 'verifier_only': pid not in approved} for pid in sorted(combined, key=lambda pid: (hardest[pid], pid))]
    write_csv('players.csv', player_rows)
    summary = {**metadata, 'rank_range': [1,150], 'approved_record_rows': len(records), 'unique_players_approved_records_only': len(approved), 'additional_verifier_only_players': len(set(combined)-set(approved)), 'unique_players_including_verifiers': len(combined), 'players_with_harder_rank_due_to_verification': sum(hardest[pid]<record_hardest[pid] for pid in approved), 'zero_hardest_bins': len(zero_audit), 'cumulative_checkpoints': {str(n): {'including_verifiers': rows[n-1]['cumulative_including_verifiers'], 'approved_records_only': rows[n-1]['cumulative_approved_records_only']} for n in [1,10,30,50,75,100,125,150]}, 'definition': 'Traditional Pointercrate Demonlist: rated=true and rated_position 1-150. Hardest is the minimum rated_position among each unique player ID\'s approved 100% records and listed verifier credits. Every player appears in one bin. Cumulative N sums bins 1-N.', 'limitation': 'Public approved records and verifier credits collected over an interval, not all real-life completions or an atomic database snapshot.'}
    save_json(ROOT/'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse-data', action='store_true')
    args = parser.parse_args()
    if args.reuse_data:
        levels = json.loads((DATA/'levels.json').read_text())
        metadata = json.loads((DATA/'collection.json').read_text())
        with gzip.open(DATA/'records.json.gz', 'rb') as file:
            payload = file.read()
        assert hashlib.sha256(payload).hexdigest() == metadata['records_uncompressed_sha256'], 'Raw-record snapshot checksum mismatch'
        assert metadata['list_type'] == 'traditional_demonlist' and metadata['rank_field'] == 'rated_position'
        records = json.loads(payload)
    else:
        levels, records, metadata = collect()
    analyze(levels, records, metadata)
