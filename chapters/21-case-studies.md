# Chapter 21: Building Production MCP Servers — Case Studies

---

## 21.1 Case Study: A Database Explorer Server

### The Challenge

Build an MCP server that provides safe, read-only access to SQL databases — enabling AI models to explore schemas, query data, and generate insights without risking data integrity.

### Architecture

```python
"""
Database Explorer MCP Server
Provides safe, read-only SQL access with query validation,
result formatting, and schema exploration.
"""

from mcp.server.fastmcp import FastMCP, Context
import asyncpg
import os

mcp = FastMCP("db-explorer")
DB_URL = os.environ["DATABASE_URL"]

# Connection pool for efficiency
pool = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)
    return pool

@mcp.tool()
async def query(sql: str, limit: int = 100, ctx: Context) -> str:
    """Execute a read-only SQL query.

    Args:
        sql: SQL SELECT query to execute
        limit: Maximum rows to return (default: 100, max: 10000)
    """
    # Security: only allow SELECT
    normalized = sql.strip().upper()
    if not normalized.startswith("SELECT") and not normalized.startswith("WITH"):
        return "Error: Only SELECT and WITH (CTE) queries are allowed."

    # Enforce limit
    limit = min(limit, 10000)
    if "LIMIT" not in normalized:
        sql = f"{sql.rstrip(';')} LIMIT {limit}"

    await ctx.info(f"Executing: {sql[:200]}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Use read-only transaction
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(sql)

    if not rows:
        return "Query returned no results."

    # Format as markdown table
    columns = list(rows[0].keys())
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(v) for v in row.values()) + " |")

    return "\n".join(lines) + f"\n\n{len(rows)} row(s) returned."

@mcp.tool()
async def explain_query(sql: str) -> str:
    """Get the execution plan for a SQL query."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"EXPLAIN ANALYZE {sql}")
    return "\n".join(row["QUERY PLAN"] for row in rows)

@mcp.resource("db://schema")
async def full_schema() -> str:
    """Complete database schema."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        schema = {}
        for table in tables:
            cols = await conn.fetch("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = $1 ORDER BY ordinal_position
            """, table["table_name"])
            schema[table["table_name"]] = [dict(c) for c in cols]
    import json
    return json.dumps(schema, indent=2, default=str)
```

### Key Design Decisions

- **Read-only transactions** prevent accidental data modification
- **Query validation** rejects non-SELECT queries at the application level
- **Result limiting** prevents runaway queries from returning millions of rows
- **Connection pooling** handles concurrent queries efficiently
- **Schema as a resource** allows the AI to understand the database structure before querying

---

## 21.2 Case Study: A Git/GitHub Integration Server

### Architecture

```python
"""GitHub MCP Server — manage repositories, issues, and pull requests."""

from mcp.server.fastmcp import FastMCP
import httpx
import os

mcp = FastMCP("github")
TOKEN = os.environ["GITHUB_TOKEN"]
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
BASE = "https://api.github.com"

@mcp.tool()
async def list_issues(owner: str, repo: str, state: str = "open", labels: str = "") -> str:
    """List issues in a GitHub repository.

    Args:
        owner: Repository owner
        repo: Repository name
        state: Issue state - "open", "closed", or "all"
        labels: Comma-separated label names to filter by
    """
    params = {"state": state, "per_page": 30}
    if labels:
        params["labels"] = labels

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/repos/{owner}/{repo}/issues",
                               headers=HEADERS, params=params)
        resp.raise_for_status()

    issues = resp.json()
    lines = [f"# Issues in {owner}/{repo} ({state})\n"]
    for issue in issues:
        labels_str = ", ".join(l["name"] for l in issue.get("labels", []))
        lines.append(f"- #{issue['number']}: {issue['title']} [{labels_str}]")
    return "\n".join(lines)

@mcp.tool()
async def create_issue(owner: str, repo: str, title: str, body: str = "",
                       labels: list[str] = []) -> str:
    """Create a new GitHub issue.

    Args:
        owner: Repository owner
        repo: Repository name
        title: Issue title
        body: Issue body (Markdown)
        labels: Labels to apply
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE}/repos/{owner}/{repo}/issues",
            headers=HEADERS,
            json={"title": title, "body": body, "labels": labels}
        )
        resp.raise_for_status()

    issue = resp.json()
    return f"Created issue #{issue['number']}: {issue['html_url']}"

@mcp.tool()
async def get_pull_request(owner: str, repo: str, number: int) -> str:
    """Get details of a pull request including diff stats."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE}/repos/{owner}/{repo}/pulls/{number}",
                               headers=HEADERS)
        resp.raise_for_status()

    pr = resp.json()
    return f"""# PR #{pr['number']}: {pr['title']}
State: {pr['state']}
Author: {pr['user']['login']}
Base: {pr['base']['ref']} ← {pr['head']['ref']}
Changed files: {pr['changed_files']}
Additions: +{pr['additions']}, Deletions: -{pr['deletions']}

{pr['body'] or 'No description.'}"""
```

---

## 21.3 Case Study: A Web Search and Scraping Server

```python
"""Web Search MCP Server — search the web and extract content."""

from mcp.server.fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup

mcp = FastMCP("web")

@mcp.tool()
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web and return results.

    Args:
        query: Search query
        num_results: Number of results (max 10)
    """
    # Using a search API (example with SerpAPI)
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://serpapi.com/search", params={
            "q": query, "num": min(num_results, 10),
            "api_key": os.environ["SERPAPI_KEY"]
        })
    results = resp.json().get("organic_results", [])

    lines = [f"# Search results for: {query}\n"]
    for r in results:
        lines.append(f"**{r['title']}**\n{r['link']}\n{r.get('snippet', '')}\n")
    return "\n".join(lines)

@mcp.tool()
async def fetch_page(url: str, extract_text: bool = True) -> str:
    """Fetch a web page and optionally extract its text content.

    Args:
        url: URL to fetch
        extract_text: If true, extract clean text; if false, return raw HTML
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    if not extract_text:
        return resp.text[:50000]  # Limit raw HTML size

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    return text[:30000]  # Limit text size
```

---

## 21.4 Case Study: A Cloud Infrastructure Management Server

```python
"""AWS Infrastructure MCP Server — manage cloud resources safely."""

from mcp.server.fastmcp import FastMCP, Context
import boto3

mcp = FastMCP("aws-infra")

@mcp.tool()
async def list_ec2_instances(region: str = "us-east-1") -> str:
    """List EC2 instances with their status."""
    ec2 = boto3.client("ec2", region_name=region)
    response = ec2.describe_instances()

    instances = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            name = ""
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
            instances.append({
                "id": instance["InstanceId"],
                "name": name,
                "type": instance["InstanceType"],
                "state": instance["State"]["Name"],
                "ip": instance.get("PublicIpAddress", "N/A")
            })

    lines = ["| ID | Name | Type | State | IP |", "|---|---|---|---|---|"]
    for i in instances:
        lines.append(f"| {i['id']} | {i['name']} | {i['type']} | {i['state']} | {i['ip']} |")
    return "\n".join(lines)

@mcp.tool()
async def get_cloudwatch_metrics(
    instance_id: str,
    metric: str = "CPUUtilization",
    period_hours: int = 24
) -> str:
    """Get CloudWatch metrics for an EC2 instance.

    Args:
        instance_id: EC2 instance ID
        metric: Metric name (CPUUtilization, NetworkIn, DiskReadOps, etc.)
        period_hours: How many hours of data to retrieve
    """
    from datetime import datetime, timedelta
    cw = boto3.client("cloudwatch")

    response = cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName=metric,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=datetime.utcnow() - timedelta(hours=period_hours),
        EndTime=datetime.utcnow(),
        Period=3600,
        Statistics=["Average", "Maximum"]
    )

    points = sorted(response["Datapoints"], key=lambda p: p["Timestamp"])
    lines = [f"# {metric} for {instance_id} (last {period_hours}h)\n"]
    for p in points:
        lines.append(f"  {p['Timestamp'].strftime('%H:%M')}: avg={p['Average']:.1f}, max={p['Maximum']:.1f}")
    return "\n".join(lines)
```

---

## 21.5 Case Study: A Monitoring and Alerting Server

```python
"""Monitoring MCP Server — check system health and alerts."""

from mcp.server.fastmcp import FastMCP
import psutil
import json

mcp = FastMCP("monitor")

@mcp.tool()
async def system_health() -> str:
    """Get current system health metrics."""
    return json.dumps({
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory": {
            "total_gb": round(psutil.virtual_memory().total / 1e9, 1),
            "used_percent": psutil.virtual_memory().percent
        },
        "disk": {
            "total_gb": round(psutil.disk_usage("/").total / 1e9, 1),
            "used_percent": psutil.disk_usage("/").percent
        },
        "load_average": list(os.getloadavg())
    }, indent=2)

@mcp.resource("metrics://system/current")
async def current_metrics() -> str:
    """Live system metrics."""
    return json.dumps({
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent
    })
```

---

## 21.6 Lessons Learned and Common Pitfalls

1. **Always validate inputs** — especially SQL, file paths, and URLs
2. **Implement timeouts** for external API calls
3. **Limit result sizes** — large results waste context window tokens
4. **Use connection pooling** for database and HTTP connections
5. **Handle rate limits** from external APIs gracefully
6. **Log operations** for debugging and auditing
7. **Test with the MCP Inspector** before integrating with AI hosts
8. **Keep tools focused** — one tool per action, not Swiss-army-knife tools
9. **Write good descriptions** — the AI model depends on them
10. **Set accurate annotations** — especially `destructiveHint` for write operations

---

## Summary

Real-world MCP servers follow consistent patterns: validate inputs, connect to external services, format results for AI consumption, and handle errors gracefully. The case studies in this chapter demonstrate these patterns across databases, version control, web access, cloud infrastructure, and monitoring.
