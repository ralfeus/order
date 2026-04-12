#!/usr/bin/env python3
"""Measure CPU time consumed by the backend container during shipment creation.

Uses the Docker stats API to read total_usage (nanoseconds of CPU time) before
and after running create_test_shipments.py, then reports the delta.

Usage:
    python scripts/benchmark_shipments.py [--container NAME] [--url URL]
                                          [--carrier CODE] [--count N]

Examples:
    python scripts/benchmark_shipments.py
    python scripts/benchmark_shipments.py --container eurocargo-backend-1 --count 10
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request


# ---------------------------------------------------------------------------
# Docker stats via unix socket
# ---------------------------------------------------------------------------

def _docker_api(path: str) -> dict:
    """Call the Docker daemon API via the unix socket."""
    url = f'http+unix://%2Fvar%2Frun%2Fdocker.sock{path}'
    # urllib doesn't support unix sockets; use curl instead
    result = subprocess.run(
        ['curl', '-sf', '--unix-socket', '/var/run/docker.sock',
         f'http://localhost{path}'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f'Docker API error: {result.stderr.strip()}')
    return json.loads(result.stdout)


def resolve_container_id(name: str) -> str:
    """Return the full container ID for the given name or id prefix."""
    data = _docker_api(f'/containers/{name}/json')
    return data['Id']


def get_cpu_ns(container_id: str) -> int:
    """Return total CPU usage in nanoseconds for the container (one-shot snapshot)."""
    data = _docker_api(f'/containers/{container_id}/stats?stream=false')
    return data['cpu_stats']['cpu_usage']['total_usage']


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Benchmark backend CPU usage during shipment creation'
    )
    parser.add_argument('--container', default='eurocargo-backend-1',
                        help='Backend container name or ID (default: eurocargo-backend-1)')
    parser.add_argument('--url',      default='http://localhost:8000',
                        help='ECmgmt API base URL (default: http://localhost:8000)')
    parser.add_argument('--carrier',  default='GLS',
                        help='Carrier code (default: GLS)')
    parser.add_argument('--count',    type=int, default=3,
                        help='Number of shipments to create (default: 3)')
    args = parser.parse_args()

    # Resolve container
    try:
        container_id = resolve_container_id(args.container)
    except Exception as exc:
        sys.exit(f'Cannot find container "{args.container}": {exc}')
    print(f'Container : {args.container} ({container_id[:12]})')
    print(f'Shipments : {args.count} × {args.carrier} → {args.url}')
    print()

    # Snapshot BEFORE
    cpu_before = get_cpu_ns(container_id)
    wall_before = time.perf_counter()

    # Run shipment creation
    result = subprocess.run(
        [sys.executable, 'scripts/create_test_shipments.py',
         '--url', args.url,
         '--carrier', args.carrier,
         '--count', str(args.count)],
        text=True,
    )

    # Snapshot AFTER
    wall_after  = time.perf_counter()
    cpu_after   = get_cpu_ns(container_id)

    # Report
    cpu_delta_ns  = cpu_after - cpu_before
    cpu_delta_ms  = cpu_delta_ns / 1_000_000
    cpu_delta_s   = cpu_delta_ns / 1_000_000_000
    wall_s        = wall_after - wall_before
    cpu_pct       = (cpu_delta_s / wall_s * 100) if wall_s > 0 else 0

    print()
    print('─' * 45)
    print(f'Wall-clock time : {wall_s:.2f} s')
    print(f'CPU time (container) : {cpu_delta_ms:.1f} ms  ({cpu_delta_s:.3f} s)')
    print(f'Avg CPU utilisation  : {cpu_pct:.1f}%')
    if args.count > 0:
        print(f'CPU time per shipment: {cpu_delta_ms / args.count:.1f} ms')
    print('─' * 45)

    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
