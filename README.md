# github-project-reporter
Tools for generating github reports

## Setup

```bash
pip install requests
```

## Usage

```bash
python github_project_report.py --owner <owner> --repo <repo> --token <token> --pdf <output_pdf_path> --start-date <start_date> --end-date <end_date> [--closed-only] [--include-card-details]
```

## Example

```bash
python github_project_report.py --owner himwho --repo "github-project-reporter" --token "ghp_1234567890" --start-date 2024-10-01 --end-date 2025-01-10 --closed-only --pdf "report.pdf"
```
