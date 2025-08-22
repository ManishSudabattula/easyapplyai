# Job Application Automation System

A sophisticated, local-first job application automation system with cryptographic audit trails, web automation, and AI-powered job extraction. This system can process job postings from various platforms (LinkedIn, Lever, Greenhouse, etc.) and extract structured data with full traceability.

## 🚀 Features

- **🔍 Multi-Platform Support**: LinkedIn, Lever, Greenhouse, and generic job sites
- **🔗 Cryptographic Audit Trail**: Immutable, hash-chained audit logs for all operations
- **🤖 AI-Powered Extraction**: LLM-assisted field extraction using Claude 3.5 Sonnet
- **🌐 Web Automation**: Playwright-based browser automation with session persistence
- **📁 Artifact Management**: Screenshots, HTML snapshots, and structured data storage
- **🗄️ Database Persistence**: SQLite storage with idempotent job records
- **🔐 Authentication**: LinkedIn login support with session management
- **🧪 Comprehensive Testing**: Test suite with fixtures for all platforms

## 📋 Prerequisites

- **Python 3.8+**
- **Git Bash** (Windows) or standard shell
- **OpenRouter API Key** (for LLM features)
- **Playwright browsers** (installed automatically)

## 🛠️ Installation & Setup

### 1. Clone and Navigate
```bash
cd /path/to/Agents
```

### 2. Activate Virtual Environment
```bash
# Git Bash (Windows) - Recommended
source .venv/Scripts/activate

# Command Prompt (Windows)
.venv\Scripts\activate

# PowerShell (Windows)
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers
```bash
playwright install chromium
```

### 5. Set Up Environment Variables
```bash
# Create .env file
echo "OPENROUTER_API_KEY=your_api_key_here" > .env
```

## 🚀 Quick Start

### Basic Job Processing
```bash
# Process a LinkedIn job
python -m app.cli_navigator --url "https://linkedin.com/jobs/view/123456"

# Process a Lever job
python -m app.cli_navigator --url "https://jobs.lever.co/company/123"

# Process a Greenhouse job
python -m app.cli_navigator --url "https://boards.greenhouse.io/company/jobs/123"
```

### Expected Output
```json
{
  "artifacts_dir": "/path/to/artifacts/uuid-here",
  "job_record": "/path/to/artifacts/uuid-here/job_record.json",
  "run_id": "uuid-here",
  "platform": "linkedin",
  "url_final": "https://linkedin.com/jobs/view/123456",
  "content_hash": "sha256-hash-here",
  "status": "ok"
}
```

## 📖 Detailed Walkthrough

### 1. Project Architecture

The system is built with a modular architecture:

```
app/
├── navigator.py          # Main automation orchestrator
├── cli_navigator.py      # CLI interface for job processing
├── browser.py           # Playwright browser management
├── detectors.py         # Platform detection logic
├── extractors.py        # Field extraction with LLM support
├── auth.py             # Authentication and session management
├── audit.py            # Cryptographic audit trail system
├── storage.py          # Database operations
├── settings.py         # Configuration management
└── schemas.py          # Pydantic data models
```

### 2. Core Components

#### Navigator Agent (`navigator.py`)
The main orchestrator that:
- Canonicalizes URLs
- Manages browser sessions
- Detects job platforms
- Extracts job data
- Creates audit trails
- Persists artifacts

#### Audit Trail System (`audit.py`)
Implements cryptographically secure audit chains:
- Each event links to the previous one via hash
- Immutable logs stored in `audit.jsonl`
- Database persistence for querying
- Full traceability of all operations

#### Platform Detection (`detectors.py`)
Automatically detects job platforms:
- **LinkedIn**: URL patterns and DOM selectors
- **Lever**: Specific selectors and structure
- **Greenhouse**: Board-specific patterns
- **Generic**: Fallback for unknown platforms

#### Field Extraction (`extractors.py`)
AI-powered job data extraction:
- Uses Claude 3.5 Sonnet via OpenRouter
- Extracts title, company, location, description
- Handles missing or malformed data
- Configurable extraction strategies

### 3. Execution Flow

#### Step-by-Step Process

1. **URL Canonicalization**
   ```python
   canon = canonicalize(url)  # Remove tracking params, normalize
   ```

2. **Session Management**
   ```python
   sess = SessionManager()
   state = sess.load_state(host)  # Load existing login session
   ```

3. **Browser Launch**
   ```python
   pw, browser, context, page = open_persistent(
       headless=True, 
       storage_state=state
   )
   ```

4. **Authentication Check**
   ```python
   gate = auth.is_login_gate(page, host)
   if gate:
       # Handle manual login if needed
   ```

5. **Platform Detection**
   ```python
   guess = url_guess(canon)      # URL-based detection
   probe = probe_platform(page)  # DOM-based detection
   ```

6. **Content Expansion**
   ```python
   expand_description(page, platform, desc_roots)
   scroll_lazy(page)  # Load lazy content
   ```

7. **Screenshot Capture**
   ```python
   screenshot(page, ss_path)
   storage.persist_artifact(run_id, "screenshot", ss_path)
   ```

8. **Field Extraction**
   ```python
   fields, audit = extract_fields(
       page, platform, url, 
       llm_enabled=True, agent=self
   )
   ```

9. **Data Normalization**
   ```python
   norm = normalize_fields(fields)
   content_hash = norm["content_hash"]
   ```

10. **Persistence**
    ```python
    storage.upsert_job(run_id, url, content_hash)
    ```

### 4. Configuration

#### Main Configuration (`config/config.json`)
```json
{
  "artifacts": {
    "base_dir": "artifacts",
    "keep_raw_before_after": true
  },
  "retries": {
    "max_attempts": 3,
    "backoff_initial_ms": 300,
    "backoff_max_ms": 3000
  },
  "llm": {
    "provider": "openrouter",
    "model_primary": "openrouter/anthropic/claude-3.5-sonnet",
    "temperature": 0.1,
    "top_p": 0.95,
    "max_tokens": 1200,
    "request_timeout_s": 20,
    "enabled": true
  },
  "playwright": {
    "headless": true,
    "nav_timeout_ms": 15000,
    "wait_timeout_ms": 15000,
    "screenshot_full_page": true,
    "block_resources": ["image", "media", "font"]
  },
  "auth": {
    "sessions_dir": "sessions",
    "allow_manual_login": true,
    "manual_login_timeout_s": 420
  }
}
```

#### Environment Variables (`.env`)
```bash
OPENROUTER_API_KEY=your_api_key_here
```

### 5. CLI Commands

#### Navigator CLI (`cli_navigator.py`)
```bash
# Basic usage
python -m app.cli_navigator --url "https://linkedin.com/jobs/view/123"

# With options
python -m app.cli_navigator \
  --url "https://linkedin.com/jobs/view/123" \
  --headful \
  --no-llm \
  --no-screenshot \
  --timeout 30000

# Use fixture for testing
python -m app.cli_navigator \
  --url "https://linkedin.com/jobs/view/123" \
  --fixture "tests/fixtures/linkedin.html"
```

#### Bootstrap CLI (`cli_bootstrap.py`)
```bash
# Basic bootstrap (creates placeholder artifacts)
python -m app.cli_bootstrap --url "https://example.com/job"
```

#### Auth CLI (`cli_auth.py`)
```bash
# Manage authentication sessions
python -m app.cli_auth --help
```

### 6. Database Schema

#### Runs Table
```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    error_message TEXT
);
```

#### Artifacts Table
```sql
CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

#### Audit Table
```sql
CREATE TABLE audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step TEXT NOT NULL,
    status TEXT NOT NULL,
    ts_iso TEXT NOT NULL,
    ts_ns INTEGER NOT NULL,
    input_digest TEXT,
    output_digest TEXT,
    prev_event_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    details_json TEXT NOT NULL
);
```

#### Jobs Table
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    url TEXT NOT NULL,
    content_hash TEXT,
    extracted_at TEXT
);
```

### 7. Artifact Structure

For each job processing run, the system creates:

```
artifacts/{run_id}/
├── audit.jsonl              # Audit trail (JSONL format)
├── job_record.json          # Extracted job data
├── screenshot.png           # Full-page screenshot
├── raw.before.html         # HTML before expansion
├── raw.after.html          # HTML after expansion
└── placeholder.txt         # Bootstrap placeholder
```

### 8. Testing

#### Run All Tests
```bash
python -m pytest tests/
```

#### Run Specific Test Categories
```bash
# Audit trail tests
python -m pytest tests/test_audit_chain.py

# Navigator tests
python -m pytest tests/test_navigator_mvp.py

# Persistence tests
python -m pytest tests/test_persistence.py
```

#### Test with Fixtures
The system includes HTML fixtures for testing:
- `tests/fixtures/linkedin.html`
- `tests/fixtures/lever.html`
- `tests/fixtures/greenhouse.html`
- `tests/fixtures/other.html`

### 9. Advanced Usage

#### Custom Platform Detection
Add new platforms in `detectors.py`:
```python
def probe_platform(page) -> PlatformProbe:
    # Add your platform detection logic
    pass
```

#### Custom Field Extraction
Extend `extractors.py` for new fields:
```python
def extract_fields(page, platform: str, url: str, **kwargs):
    # Add custom extraction logic
    pass
```

#### Audit Trail Analysis
```python
from app.audit import AuditTrailAgent
from app import storage

# Get audit events for a run
run_id = "your-run-id"
audit_path = settings.artifacts_dir_for(run_id) / "audit.jsonl"
events = [json.loads(line) for line in audit_path.read_text().splitlines()]
```

#### Database Queries
```python
from app import storage

# Get all runs
runs = storage.get_all_runs()

# Get artifacts for a run
artifacts = storage.get_artifacts_for_run(run_id)

# Get job records
jobs = storage.get_all_jobs()
```

### 10. Troubleshooting

#### Common Issues

1. **Missing API Key**
   ```bash
   # Ensure .env file exists with API key
   echo "OPENROUTER_API_KEY=your_key" > .env
   ```

2. **Playwright Installation**
   ```bash
   # Reinstall Playwright browsers
   playwright install chromium
   ```

3. **Database Issues**
   ```bash
   # Reset database (WARNING: loses all data)
   rm automation.db
   ```

4. **Permission Errors**
   ```bash
   # Check write permissions
   ls -la artifacts/
   chmod 755 artifacts/
   ```

#### Debug Mode

Enable verbose logging:
```python
# In storage.py
engine = create_engine(f"sqlite:///{_DB_PATH}", echo=True, future=True)
```

#### Manual Login

When authentication is required:
1. Browser window opens automatically
2. Complete login manually
3. Press Enter in terminal to continue
4. Session is saved for future use

### 11. Security Features

- **Hash Chaining**: Each audit event cryptographically links to the previous
- **Content Integrity**: All artifacts have SHA256 verification
- **Immutable Logs**: Audit trails cannot be modified without detection
- **Local Storage**: All data stays on your machine
- **Session Isolation**: Browser sessions are isolated per domain

### 12. Performance Optimization

- **Resource Blocking**: Images, fonts, and media can be blocked for speed
- **Headless Mode**: Default browser mode for faster execution
- **Retry Logic**: Automatic retries with exponential backoff
- **Idempotent Operations**: Duplicate jobs are handled efficiently

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

[Add your license information here]

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the audit logs for error details
3. Open an issue with run_id and error details

---

**Happy Job Hunting! 🎯**
