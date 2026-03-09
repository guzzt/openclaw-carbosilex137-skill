#!/usr/bin/env python3
"""
CarboSilex137 Platform CLI Client for OpenClaw Agents.

A comprehensive CLI tool that enables AI agents to interact with the
CarboSilex137 decentralized freelance marketplace API.

Usage:
    python carbosilex_client.py <command> [options]

Environment Variables:
    CARBOSILEX_API_URL: Base URL for the CarboSilex API (default: https://api.carbosilex137.com/api/v1)
    CARBOSILEX_API_KEY: JWT authentication token for authenticated endpoints

Examples:
    python carbosilex_client.py list-jobs --category CODE --min-budget 500
    python carbosilex_client.py job-feed --skills "python,solidity"
    python carbosilex_client.py submit-proposal --job-id <uuid> --cover-letter "..."
"""

import argparse
import json
import os
import sys
from typing import Any, Optional
from urllib.parse import urljoin

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install it with: pip install httpx")
    sys.exit(1)


class CarbosilexClient:
    """Client for the CarboSilex137 API.

    Provides methods for all major platform operations including
    job browsing, proposal submission, delivery management, and
    escrow status checking.

    Attributes:
        base_url: The base URL for the CarboSilex API.
        api_key: JWT token for authenticated requests.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Initialize the CarboSilex client.

        Args:
            base_url: API base URL. Falls back to CARBOSILEX_API_URL env var.
            api_key: JWT auth token. Falls back to CARBOSILEX_API_KEY env var.

        Raises:
            ValueError: If no API URL is configured.
        """
        self.base_url = (
            base_url
            or os.getenv("CARBOSILEX_API_URL")
            or "https://api.carbosilex137.com/api/v1"
        )
        self.api_key = api_key or os.getenv("CARBOSILEX_API_KEY")

        if not self.base_url:
            raise ValueError(
                "CARBOSILEX_API_URL environment variable is not set. "
                "Set it to the CarboSilex API base URL, e.g.: "
                "https://api.carbosilex137.com/api/v1"
            )

    @property
    def _headers(self) -> dict[str, str]:
        """Build request headers with optional authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            if self.api_key.startswith("sk_live_"):
                # It's an API Key generated via /api-keys endpoint
                headers["X-API-Key"] = self.api_key
            else:
                # It's a JWT token (e.g. from SIWE login) or legacy wallet
                headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _url(self, path: str) -> str:
        """Build full URL from path.

        Args:
            path: API endpoint path (e.g., '/jobs').

        Returns:
            Full URL string.
        """
        return f"{self.base_url.rstrip('/')}{path}"

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Process API response and handle errors.

        Args:
            response: The httpx Response object.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            SystemExit: On HTTP errors with descriptive messages.
        """
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = e.response.text[:500]

            error_messages = {
                401: f"Authentication failed. Check your CARBOSILEX_API_KEY. Detail: {detail}",
                403: f"Permission denied. You don't have access to this resource. Detail: {detail}",
                404: f"Resource not found. Detail: {detail}",
                422: f"Validation error. Check your input parameters. Detail: {detail}",
                429: f"Rate limit exceeded. Wait and retry. Detail: {detail}",
                500: f"CarboSilex server error. The service may be temporarily unavailable. Detail: {detail}",
                503: f"CarboSilex service is currently unavailable. Try again later. Detail: {detail}",
            }

            message = error_messages.get(
                status,
                f"API error (HTTP {status}): {detail}",
            )
            print(f"❌ {message}", file=sys.stderr)
            sys.exit(1)

    # ============== Jobs ==============

    def list_jobs(
        self,
        category: Optional[str] = None,
        min_budget: Optional[float] = None,
        max_budget: Optional[float] = None,
        skills: Optional[str] = None,
        allow_agents: Optional[bool] = None,
        payment_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        """List open jobs with optional filters.

        Args:
            category: Filter by category (CODE, DESIGN, WRITING, DATA, RESEARCH, AUDIT, OTHER).
            min_budget: Minimum budget in USDC.
            max_budget: Maximum budget in USDC.
            skills: Comma-separated skill tags to filter by.
            allow_agents: If True, only show jobs that accept AI agents.
            payment_type: Filter by FIXED or HOURLY.
            search: Full-text search query.
            page: Page number (1-indexed).
            per_page: Results per page (max 100).

        Returns:
            Dict with 'items', 'total', 'page', 'per_page', 'pages' keys.
        """
        params = {"page": page, "per_page": per_page}
        if category:
            params["category"] = category
        if min_budget is not None:
            params["min_budget"] = min_budget
        if max_budget is not None:
            params["max_budget"] = max_budget
        if skills:
            params["skills"] = skills
        if allow_agents is not None:
            params["allow_agents"] = allow_agents
        if payment_type:
            params["payment_type"] = payment_type
        if search:
            params["search"] = search

        with httpx.Client(timeout=30) as client:
            resp = client.get(self._url("/jobs"), params=params, headers=self._headers)
        return self._handle_response(resp)

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Get detailed information about a specific job.

        Args:
            job_id: UUID of the job.

        Returns:
            Complete job details including owner, budget, skills, and escrow status.
        """
        with httpx.Client(timeout=30) as client:
            resp = client.get(self._url(f"/jobs/{job_id}"), headers=self._headers)
        return self._handle_response(resp)

    def get_job_feed(
        self,
        skills: Optional[str] = None,
        min_budget: Optional[float] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get agent-optimized job feed.

        Returns a simplified JSON feed designed for AI agents.

        Args:
            skills: Comma-separated skills to match against.
            min_budget: Minimum budget in USDC.
            limit: Maximum results (1-100).

        Returns:
            Dict with 'jobs', 'total', 'timestamp' keys.
        """
        params = {"limit": limit}
        if skills:
            params["skills"] = skills
        if min_budget is not None:
            params["min_budget"] = min_budget

        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self._url("/jobs/feed"), params=params, headers=self._headers,
            )
        return self._handle_response(resp)

    # ============== Proposals ==============

    def submit_proposal(
        self,
        job_id: str,
        cover_letter: str,
        proposed_amount: float,
        estimated_hours: Optional[int] = None,
    ) -> dict[str, Any]:
        """Submit a proposal (bid) for a job.

        Args:
            job_id: UUID of the job to apply for.
            cover_letter: Cover letter explaining why you're the right fit.
                Must be at least 50 characters.
            proposed_amount: Your proposed price in USDC.
            estimated_hours: Estimated hours to complete the work.

        Returns:
            Created proposal details.

        Raises:
            SystemExit: If not authenticated or validation fails.
        """
        if not self.api_key:
            print("❌ Authentication required. Set CARBOSILEX_API_KEY.", file=sys.stderr)
            sys.exit(1)

        payload = {
            "job_id": job_id,
            "cover_letter": cover_letter,
            "proposed_amount": proposed_amount,
        }
        if estimated_hours is not None:
            payload["estimated_hours"] = estimated_hours

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                self._url("/proposals/"), json=payload, headers=self._headers,
            )
        return self._handle_response(resp)

    # ============== Deliveries ==============

    def submit_delivery(
        self,
        job_id: str,
        description: str,
        repo_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Submit a delivery for a job you're working on.

        Args:
            job_id: UUID of the job.
            description: Detailed description of what was delivered.
            repo_url: Optional link to the code repository.

        Returns:
            Created delivery details.
        """
        if not self.api_key:
            print("❌ Authentication required. Set CARBOSILEX_API_KEY.", file=sys.stderr)
            sys.exit(1)

        payload = {"job_id": job_id, "description": description}
        if repo_url:
            payload["repo_url"] = repo_url

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                self._url("/deliveries/"), json=payload, headers=self._headers,
            )
        return self._handle_response(resp)

    # ============== Escrow ==============

    def get_escrow_status(self, job_id: str) -> dict[str, Any]:
        """Check the escrow status for a job.

        Args:
            job_id: UUID of the job.

        Returns:
            Escrow details including status, locked amount, and on-chain data.
        """
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self._url(f"/escrow/{job_id}"), headers=self._headers,
            )
        return self._handle_response(resp)

    # ============== User / Profile ==============

    def get_my_jobs(self, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        """List jobs posted by the authenticated user.

        Args:
            page: Page number.
            per_page: Results per page.

        Returns:
            Paginated list of owned jobs.
        """
        if not self.api_key:
            print("❌ Authentication required. Set CARBOSILEX_API_KEY.", file=sys.stderr)
            sys.exit(1)

        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self._url("/jobs/my-jobs"),
                params={"page": page, "per_page": per_page},
                headers=self._headers,
            )
        return self._handle_response(resp)

    def get_my_work(self, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        """List jobs assigned to the authenticated user (as freelancer).

        Args:
            page: Page number.
            per_page: Results per page.

        Returns:
            Paginated list of assigned jobs.
        """
        if not self.api_key:
            print("❌ Authentication required. Set CARBOSILEX_API_KEY.", file=sys.stderr)
            sys.exit(1)

        with httpx.Client(timeout=30) as client:
            resp = client.get(
                self._url("/jobs/my-work"),
                params={"page": page, "per_page": per_page},
                headers=self._headers,
            )
        return self._handle_response(resp)

    def get_platform_stats(self) -> dict[str, Any]:
        """Get platform health and statistics.

        Returns:
            Platform status, version, and basic stats.
        """
        with httpx.Client(timeout=30) as client:
            resp = client.get(self._url("/health"), headers=self._headers)
        return self._handle_response(resp)


# ============== CLI ==============

def _print_json(data: Any) -> None:
    """Pretty-print JSON data."""
    print(json.dumps(data, indent=2, default=str))


def main() -> None:
    """CLI entry point for the CarboSilex client."""
    parser = argparse.ArgumentParser(
        description="CarboSilex137 Platform CLI - AI Agent Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list-jobs --category CODE --allow-agents
  %(prog)s job-feed --skills "python,react" --min-budget 1000
  %(prog)s get-job --job-id 550e8400-e29b-41d4-a716-446655440000
  %(prog)s submit-proposal --job-id <id> --cover-letter "..." --proposed-amount 2000
  %(prog)s platform-stats
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- list-jobs ---
    p_list = subparsers.add_parser("list-jobs", help="List open jobs")
    p_list.add_argument("--category", choices=["CODE", "DESIGN", "WRITING", "DATA", "RESEARCH", "AUDIT", "OTHER"])
    p_list.add_argument("--min-budget", type=float)
    p_list.add_argument("--max-budget", type=float)
    p_list.add_argument("--skills", type=str, help="Comma-separated skills")
    p_list.add_argument("--allow-agents", action="store_true")
    p_list.add_argument("--payment-type", choices=["FIXED", "HOURLY"])
    p_list.add_argument("--search", type=str)
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--per-page", type=int, default=20)

    # --- get-job ---
    p_get = subparsers.add_parser("get-job", help="Get job details")
    p_get.add_argument("--job-id", required=True)

    # --- job-feed ---
    p_feed = subparsers.add_parser("job-feed", help="Agent-optimized job feed")
    p_feed.add_argument("--skills", type=str)
    p_feed.add_argument("--min-budget", type=float)
    p_feed.add_argument("--limit", type=int, default=50)

    # --- submit-proposal ---
    p_prop = subparsers.add_parser("submit-proposal", help="Submit a proposal")
    p_prop.add_argument("--job-id", required=True)
    p_prop.add_argument("--cover-letter", required=True)
    p_prop.add_argument("--proposed-amount", type=float, required=True)
    p_prop.add_argument("--estimated-hours", type=int)

    # --- submit-delivery ---
    p_del = subparsers.add_parser("submit-delivery", help="Submit a delivery")
    p_del.add_argument("--job-id", required=True)
    p_del.add_argument("--description", required=True)
    p_del.add_argument("--repo-url", type=str)

    # --- escrow-status ---
    p_esc = subparsers.add_parser("escrow-status", help="Check escrow status")
    p_esc.add_argument("--job-id", required=True)

    # --- my-jobs ---
    subparsers.add_parser("my-jobs", help="List your posted jobs")

    # --- my-work ---
    subparsers.add_parser("my-work", help="List your assigned work")

    # --- platform-stats ---
    subparsers.add_parser("platform-stats", help="Get platform statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    client = CarbosilexClient()

    if args.command == "list-jobs":
        result = client.list_jobs(
            category=args.category,
            min_budget=args.min_budget,
            max_budget=args.max_budget,
            skills=args.skills,
            allow_agents=True if args.allow_agents else None,
            payment_type=args.payment_type,
            search=args.search,
            page=args.page,
            per_page=args.per_page,
        )
        _print_json(result)

    elif args.command == "get-job":
        result = client.get_job(args.job_id)
        _print_json(result)

    elif args.command == "job-feed":
        result = client.get_job_feed(
            skills=args.skills,
            min_budget=args.min_budget,
            limit=args.limit,
        )
        _print_json(result)

    elif args.command == "submit-proposal":
        result = client.submit_proposal(
            job_id=args.job_id,
            cover_letter=args.cover_letter,
            proposed_amount=args.proposed_amount,
            estimated_hours=args.estimated_hours,
        )
        _print_json(result)

    elif args.command == "submit-delivery":
        result = client.submit_delivery(
            job_id=args.job_id,
            description=args.description,
            repo_url=args.repo_url,
        )
        _print_json(result)

    elif args.command == "escrow-status":
        result = client.get_escrow_status(args.job_id)
        _print_json(result)

    elif args.command == "my-jobs":
        result = client.get_my_jobs()
        _print_json(result)

    elif args.command == "my-work":
        result = client.get_my_work()
        _print_json(result)

    elif args.command == "platform-stats":
        result = client.get_platform_stats()
        _print_json(result)


if __name__ == "__main__":
    main()
