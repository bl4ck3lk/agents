#!/usr/bin/env python3
# resolve-pr-comment-graphql.py - Resolve a PR comment thread using GraphQL API
"""
Script to resolve GitHub PR comment threads using the GraphQL API.

This script properly marks comment threads as "resolved" in GitHub's UI.

Usage:
    python resolve-pr-comment-graphql.py <PR_NUMBER> <GRAPHQL_THREAD_ID>

Example:
    python scripts/resolve-pr-comment-graphql.py 151 PR_review_thread_abc123
"""

import json
import subprocess
import sys


def run_command(command:list[str]):
    """Run a command (list form) and return the output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        print(f"stderr: {e.stderr}")
        raise


def check_gh_cli():
    """Check if GitHub CLI is installed and authenticated."""
    try:
        run_command(["gh", "--version"])
        return True
    except subprocess.CalledProcessError:
        return False


def resolve_comment_thread(thread_id):
    """Resolve a comment thread using GitHub's GraphQL API."""
    # GraphQL mutation to resolve a pull request review thread
    graphql_query = f'''
mutation ResolveThread {{
  resolveReviewThread(input: {{
    threadId: "{thread_id}"
  }}) {{
    thread {{
      id
      isResolved
    }}
    clientMutationId
  }}
}}
'''

    try:
        # Execute the GraphQL mutation using gh CLI
        command = ["gh", "api", "graphql", "-f", f"query={graphql_query}"]
        result = run_command(command)
        response = json.loads(result)

        return response

    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to resolve comment thread: {e.stderr}")


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python resolve-pr-comment-graphql.py <PR_NUMBER> <GRAPHQL_THREAD_ID>"
        )
        print("  PR_NUMBER: The GitHub PR number (for reference)")
        print("  GRAPHQL_THREAD_ID: The GraphQL ID of the comment thread to resolve")
        print("\nExample:")
        print(
            "  python scripts/resolve-pr-comment-graphql.py 151 PR_review_thread_abc123"
        )
        print("\nTo find GraphQL thread IDs, first run:")
        print("  python scripts/find-comment-thread.py 151")
        sys.exit(1)

    pr_number = sys.argv[1]
    thread_id = sys.argv[2]

    # Check if gh CLI is available
    if not check_gh_cli():
        print(
            "Error: GitHub CLI (gh) is required but not installed or not authenticated."
        )
        print("Please install and authenticate with: gh auth login")
        sys.exit(1)

    print(f"Resolving comment thread on PR #{pr_number}...")
    print(f"Thread ID: {thread_id}")

    # Resolve the comment thread
    try:
        response = resolve_comment_thread(thread_id)

        if response.get("data") and response["data"].get("resolveReviewThread"):
            thread_data = response["data"]["resolveReviewThread"]["thread"]
            if thread_data.get("isResolved"):
                print("✅ Comment thread marked as resolved successfully!")
            else:
                print("⚠️  API response received but thread may not be resolved.")
                print(f"Response: {json.dumps(response, indent=2)}")
        else:
            print("❌ Failed to resolve comment thread.")
            print(f"Response: {json.dumps(response, indent=2)}")
            # Check for errors in the response
            errors = response.get("errors", [])
            if errors:
                print("Errors:")
                for error in errors:
                    print(f"  - {error.get('message', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        print(f"Error resolving comment thread: {e}")
        print("\n💡 Troubleshooting tips:")
        print("1. Ensure the THREAD_ID is a GraphQL ID, not a database ID")
        print("2. Verify you have permission to resolve threads on this PR")
        print("3. Check that the thread exists and is not already resolved")
        sys.exit(1)


if __name__ == "__main__":
    main()
