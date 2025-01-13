import requests
import datetime
import argparse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Constants for GitHub API
GITHUB_API_BASE = "https://api.github.com"

# Function to fetch data from GitHub API
def fetch_github_data(url, token):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    print(f"Fetching: {url}")  # Debug line
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching {url}: {response.status_code}")
        print(f"Response: {response.text}")  # Debug line
    response.raise_for_status()
    return response.json()

def get_project_id(owner, repo, project_number, token):
    """Find the project ID by checking both org and repo projects."""
    print(f"\nLooking for project {project_number}")
    
    # Try V2 projects first (new API endpoint)
    graphql_url = "https://api.github.com/graphql"
    if repo:
        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            projectV2(number: $number) {
              id
              title
            }
          }
        }
        """
        variables = {
            "owner": owner,
            "repo": repo,
            "number": project_number
        }
    else:
        query = """
        query($owner: String!, $number: Int!) {
          organization(login: $owner) {
            projectV2(number: $number) {
              id
              title
            }
          }
        }
        """
        variables = {
            "owner": owner,
            "number": project_number
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.post(
        graphql_url,
        json={"query": query, "variables": variables},
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        if "errors" not in data:
            if repo:
                project = data.get("data", {}).get("repository", {}).get("projectV2")
            else:
                project = data.get("data", {}).get("organization", {}).get("projectV2")
            
            if project:
                return project["id"]

    # If V2 project not found, try classic projects
    # Try organization projects first
    org_projects_url = f"{GITHUB_API_BASE}/orgs/{owner}/projects"
    print(f"\nChecking organization projects at: {org_projects_url}")  # Debug line
    try:
        org_projects = fetch_github_data(org_projects_url, token)
        print(f"Found {len(org_projects)} organization projects")  # Debug line
        for project in org_projects:
            print(f"- Project #{project['number']}: {project['name']}")  # Debug line
            if project['number'] == project_number:
                return project['id']
    except requests.exceptions.HTTPError as e:
        print(f"Organization projects error: {str(e)}")  # Debug line
        pass

    # Try repository projects if repo is provided
    if repo:
        repo_projects_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/projects"
        try:
            repo_projects = fetch_github_data(repo_projects_url, token)
            for project in repo_projects:
                if project['number'] == project_number:
                    return project['id']
        except requests.exceptions.HTTPError:
            pass  # Repository might not exist or no access

    # Construct appropriate error message
    if repo:
        raise ValueError(
            f"Could not find project number {project_number}. Tried:\n"
            f"- Organization: {owner}\n"
            f"- Repository: {owner}/{repo}"
        )
    else:
        raise ValueError(
            f"Could not find project number {project_number} in organization {owner}.\n"
            "Note: If this is a repository project, please provide the --repo parameter."
        )

# Function to generate a report
def generate_report(owner, repo, project_number, token, start_date, end_date, include_card_details, closed_only=False):
    project_id = get_project_id(owner, repo, project_number, token)
    print(f"Found project ID: {project_id}")
    
    # Make start_date and end_date timezone-aware
    start_date = start_date.replace(tzinfo=datetime.timezone.utc)
    end_date = end_date.replace(tzinfo=datetime.timezone.utc)
    
    graphql_url = "https://api.github.com/graphql"
    query = """
    query($id: ID!) {
      node(id: $id) {
        ... on ProjectV2 {
          title
          number
          url
          fields(first: 20) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
                options {
                  id
                  name
                }
              }
            }
          }
          items(first: 50) {
            nodes {
              id
              fieldValues(first: 10) {
                nodes {
                  ... on ProjectV2ItemFieldTextValue {
                    text
                    field {
                      ... on ProjectV2FieldCommon {
                        name
                      }
                    }
                  }
                  ... on ProjectV2ItemFieldDateValue {
                    date
                    field {
                      ... on ProjectV2FieldCommon {
                        name
                      }
                    }
                  }
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field {
                      ... on ProjectV2FieldCommon {
                        name
                      }
                    }
                  }
                }
              }
              content {
                ... on Issue { 
                    title 
                    url 
                    state
                    createdAt
                    closedAt
                    number
                    updatedAt
                    comments(first: 20) {
                        nodes {
                            createdAt
                            author {
                                login
                            }
                            body
                        }
                    }
                    projectItems(first: 10) {
                        nodes {
                            fieldValues(first: 10) {
                                nodes {
                                    ... on ProjectV2ItemFieldSingleSelectValue {
                                        name
                                        field {
                                            ... on ProjectV2FieldCommon {
                                                name
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    timelineItems(first: 20) {
                        nodes {
                            __typename
                            ... on MovedColumnsInProjectEvent {
                                createdAt
                                previousProjectColumnName
                                projectColumnName
                            }
                        }
                    }
                }
                ... on PullRequest { 
                    title 
                    url 
                    state
                    createdAt
                    closedAt
                    number
                    updatedAt
                    comments(first: 20) {
                        nodes {
                            createdAt
                            author {
                                login
                            }
                            body
                        }
                    }
                    timelineItems(first: 20) {
                        nodes {
                            __typename
                            ... on MovedColumnsInProjectEvent {
                                createdAt
                                previousProjectColumnName
                                projectColumnName
                            }
                        }
                    }
                }
              }
            }
          }
        }
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.post(
        graphql_url,
        json={"query": query, "variables": {"id": project_id}},
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(f"Response: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    print("\nAPI Response:")
    print(f"Data received: {data}")
    
    project = data.get("data", {}).get("node", {})
    if not project:
        print("\nWarning: No project data found in response")
        return "No project data available"

    # Process items and sort by closed date
    processed_items = []
    items = project.get("items", {}).get("nodes", [])
    if not items:
        print("\nWarning: No items found in project")
        return "No items found in project"
    
    for item in items:
        content = item.get("content", {})
        if content:
            created_at = datetime.datetime.fromisoformat(content.get("createdAt").replace("Z", "+00:00"))
            closed_at = content.get("closedAt")
            if closed_at:
                closed_at = datetime.datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
            
            # Skip if we only want closed items and this one isn't closed
            if closed_only and content.get("state") != "CLOSED":  # GitHub API uses uppercase
                continue
                
            # Skip if outside date range
            if start_date <= created_at <= end_date:
                item_data = {
                    "content": content,
                    "closed_at": closed_at or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc),
                    "field_values": item.get("fieldValues", {}).get("nodes", [])
                }
                processed_items.append(item_data)
    
    # Sort items by closed date
    processed_items.sort(key=lambda x: x["closed_at"])
    
    # Generate report
    report = [
        "GitHub Project Report:",
        f"Project: {project.get('title')} (#{project.get('number')})",
        f"URL: {project.get('url')}",
        f"Report Period: {start_date.date()} to {end_date.date()}",
        f"Filter: {'Closed items only' if closed_only else 'All items'}",
        "",
        "Items in project:",
        ""
    ]
    
    if not processed_items:
        report.append("No items found matching the specified criteria.")
        report.append("")
        report.append("Note: This could be because:")
        report.append("- No items exist in the specified date range")
        if closed_only:
            report.append("- No closed items exist (--closed-only flag is set)")
        report.append("- Items exist but don't match the filter criteria")
        return "\n".join(report)
    
    for item in processed_items:
        content = item["content"]
        closed_at = item["closed_at"]
        
        # Format the basic item info
        status_date = f"(Closed: {closed_at.date()})" if closed_at != datetime.datetime.max.replace(tzinfo=datetime.timezone.utc) else "(Open)"
        report.append(f"- [{content.get('state')}] {content.get('title')} (#{content.get('number')}) {status_date}")
        report.append(f"  URL: {content.get('url')}")
        
        # Add field values
        for field_value in item["field_values"]:
            if field_value and field_value.get("field"):
                field_name = field_value["field"]["name"]
                value = None
                if "text" in field_value:
                    value = field_value["text"]
                elif "date" in field_value:
                    value = field_value["date"]
                elif "name" in field_value:
                    value = field_value["name"]
                    
                if value:
                    report.append(f"  {field_name}: {value}")
        
        # Add timeline of all events
        report.append("  Timeline:")
        timeline = []
        
        # Add creation date
        created_at = datetime.datetime.fromisoformat(content.get("createdAt").replace("Z", "+00:00"))
        timeline.append((
            created_at,
            "Task created"
        ))
        
        # Add comments
        for comment in content.get("comments", {}).get("nodes", []):
            comment_date = datetime.datetime.fromisoformat(comment["createdAt"].replace("Z", "+00:00"))
            timeline.append((
                comment_date,
                f"Comment by {comment['author']['login']}"
            ))
        
        # Add all timeline events (moves, labels, status changes)
        for event in content.get("timelineItems", {}).get("nodes", []):
            # Skip if event is None or doesn't have createdAt
            if not event or "createdAt" not in event:
                continue
            
            try:
                event_date = datetime.datetime.fromisoformat(event["createdAt"].replace("Z", "+00:00"))
                
                if event.get("__typename") == "MovedColumnsInProjectEvent":
                    prev_status = event.get("previousProjectColumnName")
                    new_status = event.get("projectColumnName")
                    if prev_status and new_status and prev_status != new_status:
                        timeline.append((
                            event_date,
                            f"Status changed from '{prev_status}' to '{new_status}'"
                        ))
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping event due to error: {e}")
                continue
        
        # Add closed date if closed
        if closed_at and closed_at != datetime.datetime.max.replace(tzinfo=datetime.timezone.utc):
            timeline.append((
                closed_at,
                "Task closed"
            ))
        
        # Sort and add timeline entries
        timeline.sort(key=lambda x: x[0])
        for date, event in timeline:
            report.append(f"    {date.date()}: {event}")
        
        report.append("")
    
    return "\n".join(report)

def generate_pdf(report_text, output_file):
    """Convert the report text to a PDF file."""
    doc = SimpleDocTemplate(
        output_file,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Create styles
    styles = getSampleStyleSheet()
    
    # Main title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#2B3137')
    )
    
    # Project info style
    project_info_style = ParagraphStyle(
        'ProjectInfo',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        textColor=colors.HexColor('#57606A')
    )
    
    # Section header style
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=18,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#2B3137')
    )
    
    # Task title style
    task_style = ParagraphStyle(
        'TaskTitle',
        parent=styles['Heading3'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#1F2328'),
        leftIndent=20
    )
    
    # Task details style
    details_style = ParagraphStyle(
        'TaskDetails',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=40,
        spaceAfter=3,
        textColor=colors.HexColor('#57606A')
    )
    
    # Timeline header style
    timeline_header_style = ParagraphStyle(
        'TimelineHeader',
        parent=styles['Normal'],
        fontSize=11,
        leftIndent=40,
        spaceBefore=6,
        spaceAfter=3,
        textColor=colors.HexColor('#1F2328'),
        fontName='Helvetica-Bold'
    )
    
    # Timeline entry style
    timeline_style = ParagraphStyle(
        'TimelineEntry',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=60,
        spaceAfter=2,
        textColor=colors.HexColor('#57606A')
    )
    
    # Build the PDF content
    story = []
    for line in report_text.split('\n'):
        if line.startswith('GitHub Project Report:'):
            story.append(Paragraph(line, title_style))
        elif line.startswith('Project:') or line.startswith('URL:') or line.startswith('Report Period:') or line.startswith('Filter:'):
            story.append(Paragraph(line, project_info_style))
        elif line.startswith('Items in project:'):
            story.append(Paragraph(line, section_style))
        elif line.startswith('- ['):
            # Clean up the task title line for better formatting
            clean_line = line.replace('- [', '').replace(']', ' -')
            story.append(Paragraph(clean_line, task_style))
        elif line.startswith('  Timeline:'):
            story.append(Paragraph(line.strip(), timeline_header_style))
        elif line.startswith('    '):
            # Timeline entries
            story.append(Paragraph(line.strip(), timeline_style))
        elif line.startswith('  '):
            # Task details
            story.append(Paragraph(line.strip(), details_style))
        elif line.strip():
            # Regular text
            story.append(Paragraph(line, project_info_style))
        else:
            # Empty lines
            story.append(Spacer(1, 12))
    
    doc.build(story)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a GitHub project report.")
    parser.add_argument("--owner", "-o", required=True, help="Owner of the organization or repository")
    parser.add_argument("--repo", "-r", help="Repository name (optional)")
    parser.add_argument("--project", "-p", type=int, required=True, help="Project board number")
    parser.add_argument("--token", "-t", required=True, help="GitHub personal access token")
    parser.add_argument("--start-date", "-s", type=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d"),
                        default=(datetime.datetime.now() - datetime.timedelta(days=30)),
                        help="Start date for the report (YYYY-MM-DD). Default: 1 month ago.")
    parser.add_argument("--end-date", "-e", type=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d"),
                        default=datetime.datetime.now(),
                        help="End date for the report (YYYY-MM-DD). Default: today.")
    parser.add_argument("--include-card-details", "-i", action="store_true",
                        help="Include changes to card details. Default: off.")
    parser.add_argument("--pdf", type=str, help="Generate PDF output to specified file (e.g., report.pdf)")
    parser.add_argument("--closed-only", "-c", action="store_true",
                        help="Only show closed items. Default: off.")

    args = parser.parse_args()

    report = generate_report(
        args.owner,
        args.repo,
        args.project,
        args.token,
        args.start_date,
        args.end_date,
        args.include_card_details,
        args.closed_only
    )

    # Print the report to console
    print(report)
    
    # Generate PDF if requested
    if args.pdf:
        print(f"\nGenerating PDF report: {args.pdf}")
        generate_pdf(report, args.pdf)
        print(f"PDF report generated: {args.pdf}")
