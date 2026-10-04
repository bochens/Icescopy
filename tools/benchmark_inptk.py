"""Time the external INP CLI on generated counts without leaving run files.

Example: python tools/benchmark_inptk.py /path/to/inptk --method average --rows 6000
Add --individual to include the two sample overlays, or --table-reads to measure
the former table-per-request loading cost. These are synthetic timings, not an
accuracy assessment or a reproduction of a particular user's recording.
"""
import argparse
import csv
import datetime
import io
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time


def counts_csv(count):
    text = io.StringIO()
    text.write("# format_name: icescopy_freeze_count_timeseries\n# file_version: 1\n")
    for key, values in {
        'sample_id': '0,1,2', 'sample_name': 'A,B,Water', 'cell_number': '10,10,10',
        'sample_type': 'air,air,air', 'well_volume_uL': '50,50,50', 'dilution': '1,10,1',
        'air_volume_L': '100,100,100', 'suspension_volume_mL': '10,10,10',
        'filter_fraction_used': '1,1,1',
    }.items():
        text.write(f'# {key},{values}\n')
    writer = csv.writer(text)
    writer.writerow(['timestamp', 'temperature_C', 'cycle', 'picture',
                     'A number total', 'A number frozen', 'B number total', 'B number frozen',
                     'Water number total', 'Water number frozen'])
    for index in range(count):
        fraction = index / (count - 1)
        timestamp = datetime.datetime(2026, 1, 1, 12) + datetime.timedelta(seconds=index)
        writer.writerow([timestamp, -5 - 20*fraction, 0, '', 10, int(9*fraction),
                         10, int(7*fraction), 10, int(2*fraction)])
    return text.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('--rows', type=int, default=480)
    parser.add_argument('--method', choices=['average', 'mle'], default='average')
    parser.add_argument('--individual', action='store_true')
    parser.add_argument('--table-reads', action='store_true')
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if args.rows < 2 or args.timeout <= 0:
        parser.error('Use at least two rows and a positive timeout.')
    with tempfile.TemporaryDirectory(prefix='icescopy-inptk-benchmark-') as tmp:
        source = Path(tmp) / 'counts.csv'
        source.write_text(counts_csv(args.rows), encoding='utf-8')
        output = Path(tmp) / 'result.inptk'
        with (Path(tmp) / 'stderr.txt').open('w+', encoding='utf-8') as errors:
            process = subprocess.Popen([str(args.executable.expanduser()), 'serve'], text=True,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
            replies = queue.Queue()
            def read_replies():
                for line in process.stdout:
                    replies.put(line)
                replies.put(None)
            threading.Thread(target=read_replies, daemon=True).start()
            ident = 0
            def request(command):
                nonlocal ident
                ident += 1
                started = time.perf_counter()
                process.stdin.write(json.dumps({'id': ident, 'args': command}) + '\n')
                process.stdin.flush()
                try:
                    line = replies.get(timeout=args.timeout)
                except queue.Empty:
                    raise TimeoutError(f'Toolkit exceeded {args.timeout:g} seconds: {command[0]}') from None
                if line is None:
                    errors.seek(0)
                    raise RuntimeError(f'Toolkit exited: {errors.read()[-2000:]}')
                reply = json.loads(line)
                if reply.get('id') != ident or reply.get('status') != 'ok':
                    raise RuntimeError(reply)
                return reply, time.perf_counter() - started
            try:
                capabilities, _ = request(['capabilities'])
                curves = {'Combined': {'inputs': ['A', 'B'], 'cycle': '0'}}
                if args.individual:
                    curves.update({name: {'inputs': [name], 'cycle': '0'} for name in ('A', 'B')})
                reply, elapsed = request([
                    'analyze', str(source), '--format', 'icescopy', '--method', args.method,
                    '--sample-map', json.dumps({'A': 'Sample', 'B': 'Sample', 'Water': 'Water'}),
                    '--water-blank-map', json.dumps({'A': ['Water'], 'B': ['Water']}),
                    '--curves', json.dumps(curves), '--out', str(output)])
                result = {'toolkit_version': capabilities['toolkit_version'], 'method': args.method,
                          'rows_per_sample': args.rows, 'curves': len(curves), 'analyze_s': elapsed}
                if args.table_reads:
                    seconds = 0
                    for name, curve in reply['curves'].items():
                        for kind in curve['tables']:
                            _, duration = request(['table', str(output), '--curve', name, '--table', kind])
                            seconds += duration
                    result['table_reads_s'] = seconds
                started = time.perf_counter()
                saved = json.loads((output / 'analysis.json').read_text(encoding='utf-8'))
                result['direct_read_s'] = time.perf_counter() - started
                assert set(saved['curves']) == set(curves)
                print(json.dumps(result, indent=2))
            finally:
                process.stdin.close()
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()
