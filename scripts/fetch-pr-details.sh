#!/bin/bash
# fetch-pr-details.sh - Comprehensive PR details fetcher
# Fetches PR summary, all comments, and checks in well-structured format.
# Reports are stored under .reports/pr-reviews by default (override with PR_REVIEW_OUTPUT_ROOT).
# Usage: ./scripts/fetch-pr-details.sh <PR_NUMBER> [--json] [--markdown] [--output-dir <DIR>]

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <PR_NUMBER> [--json] [--markdown] [--output-dir <DIR>]"
    echo "  --json: Output only JSON (default: combined)"
    echo "  --markdown: Output only Markdown (default: combined)"
    echo "  --output-dir: Directory to save output (default: ./pr-review-<PR_NUMBER>)"
    exit 1
fi

PR_NUMBER=$1

# Validate PR_NUMBER is a positive integer (prevent path traversal)
if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "Error: PR_NUMBER must be a positive integer, got: '$PR_NUMBER'"
    exit 1
fi

shift
OUTPUT_FORMAT="combined"
DEFAULT_OUTPUT_ROOT="${PR_REVIEW_OUTPUT_ROOT:-.reports/pr-reviews}"
OUTPUT_DIR="$DEFAULT_OUTPUT_ROOT/pr-$PR_NUMBER"
CUSTOM_OUTPUT_DIR=false
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "current-repo")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --markdown)
            OUTPUT_FORMAT="markdown"
            shift
            ;;
        --output-dir)
            if [ -z "${2:-}" ]; then
                echo "Error: --output-dir requires a directory path."
                exit 1
            fi
            CUSTOM_OUTPUT_DIR=true
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Ensure gh is available
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is required but not installed."
    exit 1
fi

# Ensure jq is available
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed."
    echo "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

# Create output directory (ensure base folder exists for default path)
mkdir -p "$OUTPUT_DIR"

echo "Fetching details for PR #$PR_NUMBER in $REPO..."
echo "Saving report to: $OUTPUT_DIR"

# 1. Fetch PR summary
echo "Fetching PR summary..."
PR_SUMMARY_FIELDS="number,title,body,author,state,url,createdAt,updatedAt,mergedAt,closedAt,labels,assignees,reviewRequests,reviews,milestone,projectCards,additions,deletions,changedFiles,mergeable,isDraft,headRefName,headRefOid,baseRefName,baseRefOid,headRepository,headRepositoryOwner,files,commits,statusCheckRollup"
gh pr view "$PR_NUMBER" --json "$PR_SUMMARY_FIELDS" \
    > "$OUTPUT_DIR/pr-summary.json" 2>/dev/null || {
        echo "Error fetching PR summary. Ensure PR #$PR_NUMBER exists and you have access."
        exit 1
    }

# 2. Fetch all comments (issue comments, review comments, inline comments)
echo "Fetching all comments..."
# Issue comments
gh api --paginate "repos/$REPO/issues/$PR_NUMBER/comments" \
    | jq -s 'map(select(type == "array")) | (if length == 0 then [] else add end) | map(select(type == "object")) | map({
        id: .id,
        body: (.body // ""),
        user: .user.login,
        created_at: .created_at,
        updated_at: .updated_at,
        type: "issue_comment",
        html_url: .html_url
    })' > "$OUTPUT_DIR/issue-comments.json"

# Review comments (review bodies)
gh api --paginate "repos/$REPO/pulls/$PR_NUMBER/reviews" \
    | jq -s 'map(select(type == "array")) | (if length == 0 then [] else add end) | map(select(type == "object")) | map({
        id: .id,
        body: (.body // ""),
        user: .user.login,
        state: .state,
        submitted_at: .submitted_at,
        type: "review_comment",
        commit_id: .commit_id,
        html_url: .html_url
    })' > "$OUTPUT_DIR/review-comments.json"

# Inline review comments
gh api --paginate "repos/$REPO/pulls/$PR_NUMBER/comments" \
    | jq -s 'map(select(type == "array")) | (if length == 0 then [] else add end) | map(select(type == "object")) | map({
        id: .id,
        body: (.body // ""),
        path: .path,
        position: .position,
        line: .original_line,
        user: .user.login,
        created_at: .created_at,
        updated_at: .updated_at,
        type: "inline_comment",
        html_url: .html_url
    })' > "$OUTPUT_DIR/inline-comments.json"

# 3. Fetch comment threads with GraphQL IDs for resolution capability
echo "Fetching comment threads with GraphQL IDs..."
# Extract owner and repo name from REPO variable
OWNER=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)

# GraphQL query to get comment threads with their GraphQL IDs
GRAPHQL_QUERY='
query($owner: String!, $name: String!, $prNumber: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $prNumber) {
      reviewThreads(last: 100) {
        nodes {
          id
          isResolved
          comments(first: 10) {
            nodes {
              id
              databaseId
              body
              author {
                login
              }
              createdAt
              url
            }
          }
        }
      }
    }
  }
}
'

# Execute GraphQL query
gh api graphql -F owner="$OWNER" -F name="$REPO_NAME" -F prNumber="$PR_NUMBER" -f query="$GRAPHQL_QUERY" \
    > "$OUTPUT_DIR/comment-threads.json" 2>/dev/null || {
        echo "Note: Could not fetch comment threads with GraphQL IDs."
        echo '{"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": []}}}}}' > "$OUTPUT_DIR/comment-threads.json"
    }

# Process comment threads to create a mapping of database IDs to GraphQL IDs
jq -r '.data.repository.pullRequest.reviewThreads.nodes[] |
    select(.comments.nodes | length > 0) |
    .comments.nodes[] |
    select(.databaseId != null) |
    "\(.databaseId):\(.id)"' "$OUTPUT_DIR/comment-threads.json" > "$OUTPUT_DIR/id-mapping.txt" 2>/dev/null || {
        echo "" > "$OUTPUT_DIR/id-mapping.txt"
    }

# Create a lookup function for GraphQL IDs
create_comments_with_graphql_ids() {
    local input_file="$1"
    local output_file="$2"
    local comment_type="$3"

    # Add GraphQL IDs to comments where possible
    jq --rawfile id_map "$OUTPUT_DIR/id-mapping.txt" '
        map(. as $comment |
            . + {
                graphql_id: (
                    if ($comment.id and ($comment.id | type == "number")) then
                        ($id_map | split("\n") | map(select(length > 0) | split(":")) | map({key: .[0], value: .[1]}) | from_entries | .[$comment.id|tostring])
                    else
                        null
                    end
                ),
                comment_type: $comment_type
            }
        )
    ' "$input_file" --arg comment_type "$comment_type" > "$output_file"
}

# Add GraphQL IDs to all comment types
create_comments_with_graphql_ids "$OUTPUT_DIR/issue-comments.json" "$OUTPUT_DIR/issue-comments-with-graphql.json" "issue_comment"
create_comments_with_graphql_ids "$OUTPUT_DIR/review-comments.json" "$OUTPUT_DIR/review-comments-with-graphql.json" "review_comment"
create_comments_with_graphql_ids "$OUTPUT_DIR/inline-comments.json" "$OUTPUT_DIR/inline-comments-with-graphql.json" "inline_comment"

# Combine comments with GraphQL IDs
jq -s 'add | sort_by(.created_at // .submitted_at // "")' \
    "$OUTPUT_DIR"/issue-comments-with-graphql.json \
    "$OUTPUT_DIR"/review-comments-with-graphql.json \
    "$OUTPUT_DIR"/inline-comments-with-graphql.json \
    > "$OUTPUT_DIR/all-comments-with-graphql.json"

# Combine comments (original format for backward compatibility)
jq -s 'add | sort_by(.created_at // .submitted_at // "")' \
    "$OUTPUT_DIR"/issue-comments.json \
    "$OUTPUT_DIR"/review-comments.json \
    "$OUTPUT_DIR"/inline-comments.json \
    > "$OUTPUT_DIR/all-comments.json"

# 4. Fetch checks and status
echo "Fetching checks and status..."
gh pr checks "$PR_NUMBER" --json checkRuns,statusCheckRollup,statuses > "$OUTPUT_DIR/checks.json" 2>/dev/null || {
    echo "Note: Could not fetch checks (may require additional permissions)."
    echo '{}' > "$OUTPUT_DIR/checks.json"
}

# 5. Generate statistics
echo "Generating statistics..."

# Comment statistics
COMMENT_STATS=$(jq -n \
    --argjson comments "$(cat "$OUTPUT_DIR/all-comments.json")" \
    '{
        total: ($comments | length),
        by_type: ($comments | group_by(.type) | map({type: .[0].type, count: length})),
        by_user: ($comments | group_by(.user) | map({user: .[0].user, count: length}) | sort_by(-.count) | .[0:10]),
        recent: ($comments | sort_by(.created_at) | reverse | .[0:5])
    }')

# Checks statistics
CHECKS_STATS=$(jq -r '.statusCheckRollup | {
    overall_state: .state,
    conclusion: .conclusion,
    contexts: (.contexts | length),
    passing: (.contexts | map(select(.state == "success")) | length),
    failing: (.contexts | map(select(.state == "failure")) | length),
    pending: (.contexts | map(select(.state == "pending")) | length)
}' "$OUTPUT_DIR/checks.json" 2>/dev/null || echo '{"overall_state": "unknown"}')

# 6. Create combined JSON
echo "Creating combined JSON..."
jq -n \
    --argjson summary "$(<"$OUTPUT_DIR/pr-summary.json")" \
    --argjson comments "$(<"$OUTPUT_DIR/all-comments-with-graphql.json")" \
    --argjson checks "$(<"$OUTPUT_DIR/checks.json")" \
    --argjson comment_stats "$COMMENT_STATS" \
    --argjson checks_stats "$CHECKS_STATS" \
    --argjson comment_threads "$(<"$OUTPUT_DIR/comment-threads.json")" \
    --arg timestamp "$TIMESTAMP" \
    --arg repo "$REPO" \
    '{
        metadata: {
            generated_at: $timestamp,
            repository: $repo,
            pr_number: ($summary.number | tonumber)
        },
        pr: $summary,
        comments: $comments,
        comment_threads: $comment_threads,
        checks: $checks,
        statistics: {
            comments: $comment_stats,
            checks: $checks_stats
        },
        files: {
            raw: {
                summary: "./pr-summary.json",
                all_comments: "./all-comments.json",
                all_comments_with_graphql: "./all-comments-with-graphql.json",
                comment_threads: "./comment-threads.json",
                checks: "./checks.json",
                issue_comments: "./issue-comments.json",
                review_comments: "./review-comments.json",
                inline_comments: "./inline-comments.json"
            }
        }
    }' > "$OUTPUT_DIR/combined-data.json"

# 7. Create Markdown report
echo "Creating Markdown report..."
cat > "$OUTPUT_DIR/comprehensive-report.md" << EOF
# Comprehensive PR Review Report: #$PR_NUMBER

**Repository:** $REPO
**Generated:** $TIMESTAMP
**PR URL:** $(jq -r '.url' "$OUTPUT_DIR/pr-summary.json")

## 📋 PR Summary

**Title:** $(jq -r '.title' "$OUTPUT_DIR/pr-summary.json")
**Author:** $(jq -r '.author.login' "$OUTPUT_DIR/pr-summary.json")
**State:** $(jq -r '.state' "$OUTPUT_DIR/pr-summary.json")
**Created:** $(jq -r '.createdAt' "$OUTPUT_DIR/pr-summary.json")
**Updated:** $(jq -r '.updatedAt' "$OUTPUT_DIR/pr-summary.json")
**Mergeable:** $(jq -r '.mergeable' "$OUTPUT_DIR/pr-summary.json")
**Draft:** $(jq -r '.isDraft' "$OUTPUT_DIR/pr-summary.json")

**Changes:**
- Files: $(jq -r '.changedFiles' "$OUTPUT_DIR/pr-summary.json")
- Additions: $(jq -r '.additions' "$OUTPUT_DIR/pr-summary.json")
- Deletions: $(jq -r '.deletions' "$OUTPUT_DIR/pr-summary.json")

**Labels:** $(jq -r '.labels[]?.name // empty' "$OUTPUT_DIR/pr-summary.json" | tr '\n' ', ' | sed 's/,$//')
**Assignees:** $(jq -r '.assignees[]?.login // empty' "$OUTPUT_DIR/pr-summary.json" | tr '\n' ', ' | sed 's/,$//')
**Reviewers:** $(jq -r '.requestedReviewers[]?.login // empty' "$OUTPUT_DIR/pr-summary.json" | tr '\n' ', ' | sed 's/,$//')

### Files Changed
$(jq -r '.files[] | "- **\(.path)** (+\(.additions) / -\(.deletions))"' "$OUTPUT_DIR/pr-summary.json")

## ✅ Checks & Status

**Overall State:** $(jq -r '.statusCheckRollup.state // "unknown"' "$OUTPUT_DIR/checks.json")
**Conclusion:** $(jq -r '.statusCheckRollup.conclusion // "N/A"' "$OUTPUT_DIR/checks.json")

### Individual Checks
$(jq -r '.statusCheckRollup.contexts[] | "### \(.context)\n**State:** \(.state)\n**Description:** \(.description // "N/A")\n**Target URL:** \(.targetUrl // "N/A")\n\n"' "$OUTPUT_DIR/checks.json" 2>/dev/null || echo "No check details available.")

## 💬 Comments Analysis

$(echo "$COMMENT_STATS" | jq -r '
def section(title; items):
  if (items | length) == 0 then
    title + "\n- None\n\n"
  else
    title + "\n" + (items | join("\n")) + "\n\n"
  end;

def truncate(limit):
  (.|tostring) as $s |
  if ($s | length) > limit then
    $s[:limit] + "..."
  else
    $s
  end;

"**Total Comments:** " + ((.total // 0) | tostring) + "\n\n" +
section("### By Type"; (.by_type // [] | map("- **" + (.type // "unknown") + ":** " + ((.count // 0) | tostring) + " comments"))) +
section("### Top Commenters (Top 10)"; (.by_user // [] | map("- **" + (.user // "unknown") + ":** " + ((.count // 0) | tostring) + " comments"))) +
section("### Most Recent Comments"; (.recent // [] | map(
  "- **" + (.user // "unknown") + "** (" + (.created_at // "n/a") + "): " +
  ((.body // "") | truncate(120))
)))
')

### All Comments (Detailed)
For detailed comments, see the individual JSON files or use the pretty-print command below.

**Command to pretty-print comments:**
\`\`\`bash
jq -r '.[] | "\\n---\\n**Type:** \(.type)\\n**User:** \(.user)\\n**Date:** \(.created_at)\\n**Body:** \n\(.body // "N/A")"' $OUTPUT_DIR/all-comments.json
\`\`\`

## 🧵 Comment Threads with GraphQL IDs

The comment threads with their GraphQL IDs are available in **[comment-threads.json](./comment-threads.json)**. This data enables you to resolve comment threads programmatically using the GitHub GraphQL API.

To resolve a comment thread, you can use a script like:
\`\`\`bash
python scripts/resolve-pr-comment-graphql.py $PR_NUMBER <GRAPHQL_THREAD_ID>
\`\`\`

## 📊 Raw Data Files

- **[pr-summary.json](./pr-summary.json)** - Complete PR metadata
- **[all-comments.json](./all-comments.json)** - Combined comments (issue + review + inline)
- **[all-comments-with-graphql.json](./all-comments-with-graphql.json)** - Combined comments with GraphQL IDs
- **[comment-threads.json](./comment-threads.json)** - Comment threads with GraphQL IDs for resolution
- **[checks.json](./checks.json)** - CI/CD checks and status
- **[issue-comments.json](./issue-comments.json)** - Top-level issue comments
- **[review-comments.json](./review-comments.json)** - Review body comments
- **[inline-comments.json](./inline-comments.json)** - Inline code review comments

## 🤖 Machine-Readable Data

The complete structured data is available in **[combined-data.json](./combined-data.json)**, which includes:

- PR metadata and summary
- All comments with full details and GraphQL IDs
- Comment threads data for resolution
- Checks and status information
- Computed statistics (comment counts by type/user, check summaries)
- File references

This JSON is designed for programmatic analysis, dashboards, or further processing.

---

*Report generated by fetch-pr-details.sh at $TIMESTAMP*
EOF

# Output based on format
case $OUTPUT_FORMAT in
    "json")
        echo "Outputting JSON..."
        cat "$OUTPUT_DIR/combined-data.json"
        ;;
    "markdown")
        echo "Outputting Markdown..."
        cat "$OUTPUT_DIR/comprehensive-report.md"
        ;;
    "combined")
        echo "✅ Report generated successfully!"
        echo "📁 Directory: $OUTPUT_DIR"
        echo "📊 Markdown: $OUTPUT_DIR/comprehensive-report.md"
        echo "🤖 JSON: $OUTPUT_DIR/combined-data.json"
        echo ""
        echo "To view pretty comments:"
        echo "  jq -r '.[] | \"\\n---\\n**Type:** \(.type)\\n**User:** \(.user)\\n**Date:** \(.created_at)\\n**Body:** \\n\(.body)\"' $OUTPUT_DIR/all-comments.json"
        echo ""
        echo "To find GraphQL IDs for comment resolution:"
        echo "  jq -r '.data.repository.pullRequest.reviewThreads.nodes[] | \"Thread ID: \" + .id + \" (Resolved: \" + (.isResolved | tostring) + \")\"' $OUTPUT_DIR/comment-threads.json"
        ;;
esac

# Optional: Open in default viewer if on macOS
if [[ "$OSTYPE" == "darwin"* ]] && [ "$OUTPUT_FORMAT" = "combined" ]; then
    echo "Opening Markdown report..."
    open "$OUTPUT_DIR/comprehensive-report.md"
fi
