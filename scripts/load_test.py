#!/usr/bin/env python3
"""
Load testing script for LLM Council.

Tests API performance under concurrent load.

Usage:
    python scripts/load_test.py [--users N] [--duration S] [--endpoint URL]
"""

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional

import aiohttp


@dataclass
class RequestResult:
    """Result of a single request."""
    status: int
    duration_ms: float
    error: Optional[str] = None


@dataclass
class LoadTestResults:
    """Aggregate results of load test."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)

    @property
    def p50_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)

    @property
    def p95_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx] if idx < len(sorted_times) else sorted_times[-1]

    @property
    def p99_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx] if idx < len(sorted_times) else sorted_times[-1]

    @property
    def requests_per_second(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return self.total_requests / self.duration_seconds


async def make_request(
    session: aiohttp.ClientSession,
    url: str,
    method: str = "GET",
    data: dict = None,
) -> RequestResult:
    """Make a single HTTP request and measure timing."""
    start = time.time()
    try:
        async with session.request(method, url, json=data) as response:
            await response.text()
            duration = (time.time() - start) * 1000
            return RequestResult(
                status=response.status,
                duration_ms=duration,
                error=None if response.status < 400 else f"HTTP {response.status}",
            )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return RequestResult(
            status=0,
            duration_ms=duration,
            error=str(e),
        )


async def run_user(
    session: aiohttp.ClientSession,
    base_url: str,
    duration: float,
    results: LoadTestResults,
):
    """Simulate a single user making requests."""
    end_time = time.time() + duration

    while time.time() < end_time:
        # Health check endpoint
        result = await make_request(session, f"{base_url}/health")
        results.total_requests += 1

        if result.error:
            results.failed_requests += 1
            results.errors.append(result.error)
        else:
            results.successful_requests += 1
            results.response_times.append(result.duration_ms)

        # Small delay between requests
        await asyncio.sleep(0.1)


async def run_load_test(
    base_url: str,
    concurrent_users: int,
    duration_seconds: float,
) -> LoadTestResults:
    """Run load test with specified parameters."""
    results = LoadTestResults()

    print(f"\nStarting load test...")
    print(f"  URL: {base_url}")
    print(f"  Concurrent users: {concurrent_users}")
    print(f"  Duration: {duration_seconds}s")
    print()

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = [
            run_user(session, base_url, duration_seconds, results)
            for _ in range(concurrent_users)
        ]
        await asyncio.gather(*tasks)

    results.duration_seconds = time.time() - start_time

    return results


def print_results(results: LoadTestResults):
    """Print load test results."""
    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)

    print(f"\nRequests:")
    print(f"  Total: {results.total_requests}")
    print(f"  Successful: {results.successful_requests}")
    print(f"  Failed: {results.failed_requests}")
    print(f"  Success Rate: {results.success_rate:.1f}%")

    print(f"\nPerformance:")
    print(f"  Duration: {results.duration_seconds:.1f}s")
    print(f"  Throughput: {results.requests_per_second:.1f} req/s")

    print(f"\nResponse Times (ms):")
    print(f"  Average: {results.avg_response_time:.1f}")
    print(f"  P50: {results.p50_response_time:.1f}")
    print(f"  P95: {results.p95_response_time:.1f}")
    print(f"  P99: {results.p99_response_time:.1f}")

    if results.errors:
        unique_errors = set(results.errors[:10])  # Show first 10 unique errors
        print(f"\nErrors ({len(results.errors)} total, showing first 10 unique):")
        for error in unique_errors:
            print(f"  - {error}")

    print("\n" + "=" * 60)

    # Assessment
    if results.success_rate >= 99 and results.p95_response_time < 500:
        print("✅ PASSED: Service is performing well under load")
    elif results.success_rate >= 95:
        print("⚠️ WARNING: Some degradation under load")
    else:
        print("❌ FAILED: Service is not handling load well")

    print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="Load test for LLM Council")
    parser.add_argument(
        "--users", "-u",
        type=int,
        default=10,
        help="Number of concurrent users (default: 10)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=30,
        help="Duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Base URL (default: http://localhost:8001)"
    )

    args = parser.parse_args()

    # Run load test
    results = await run_load_test(
        base_url=args.url,
        concurrent_users=args.users,
        duration_seconds=args.duration,
    )

    # Print results
    print_results(results)

    # Exit code based on results
    if results.success_rate < 95:
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
