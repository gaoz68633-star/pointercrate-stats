"""Match GDDL ratings by Geometry Dash level ID to the fixed Pointercrate snapshot.

Usage: python scripts/fetch_gddl_tiers.py /path/to/levels.json
Uses the public GDDL levels endpoint; caches each response before resuming.
"""
import argparse
import csv
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data' / 'gddl'


def get_level(level_id):
    path = CACHE / f'{level_id}.json'
    if path.exists():
        return json.loads(path.read_text())
    url = f'https://gdladder.com/api/levels/{level_id}'
    for attempt in range(5):
        try:
            # Proxy handling can mutate Request objects; each retry needs a fresh one.
            request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'Pointercrate-Stats/1.0 (public statistical visualization)'})
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
            break
        except HTTPError as error:
            if error.code == 404:
                data = {'missing': True, 'reason': 'HTTP 404', 'level_id': level_id}
                break
            if error.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 4:
                raise
        time.sleep(min(30, 2 ** (attempt + 1)))
    assert isinstance(data, dict), f'Unexpected GDDL response for {level_id}'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    time.sleep(.35)
    return data


def main(levels_path):
    levels = json.loads(levels_path.read_text())
    assert [r['position'] for r in levels] == list(range(1, 151))
    CACHE.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')
    rows = []
    for d in levels:
        response = get_level(d['level_id'])
        # GDDL returns an empty object with HTTP 200 for some unlisted IDs.
        if response and not response.get('missing'):
            assert response.get('ID') == d['level_id'], f"GDDL level ID mismatch for rank {d['position']}"
        # The public response uses Rating and DefaultRating (same interpretation
        # as the open-source Geode GDDL integration).
        value = response.get('Rating')
        default = response.get('DefaultRating')
        if isinstance(value, (float, int)) and value >= 1:
            tier, source = math.floor(value+.5), 'rounded_rating'
        elif isinstance(default, (float, int)) and default >= 1:
            tier, source = int(default), 'default_rating'
        else:
            tier, source = '', 'missing'
        rows.append({'rank': d['position'], 'level_name': d['name'], 'level_id': d['level_id'], 'rating': value if value is not None else '', 'tier': tier, 'tier_source': source, 'rating_count': response.get('RatingCount', ''), 'source_url': f"https://gdladder.com/level/{d['level_id']}"})
        if d['position']%25==0:
            print(f"GDDL: {d['position']}/150 levels", flush=True)
    with (ROOT/'gddl_tiers.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    cache_times = [(CACHE / f"{d['level_id']}.json").stat().st_mtime for d in levels]
    metadata={'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'source_response_cached_at_min_utc': datetime.fromtimestamp(min(cache_times),timezone.utc).isoformat(timespec='seconds'), 'source_response_cached_at_max_utc': datetime.fromtimestamp(max(cache_times),timezone.utc).isoformat(timespec='seconds'), 'source': 'https://gdladder.com/api/levels/{level_id}', 'match_key': 'Geometry Dash level ID from the original Pointercrate rank snapshot', 'coverage': sum(r['tier']!='' for r in rows), 'tier_rule': 'round Rating to nearest integer, halves upwards; fall back to DefaultRating only if Rating is unavailable', 'not_a_rank_conversion': True}
    (ROOT/'gddl_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('levels_json',type=Path,nargs='?',default=ROOT/'data'/'levels.json')
    main(parser.parse_args().levels_json)
