# MathMinds AI

## Prerequisites
- Python 3.10+
- Redis Server (running on localhost:6379)

## Installation
1. Create a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your configuration (GOOGLE_API_KEY, REDIS_URL, etc.).

## Running the System
To start both the API and the Worker, double-click `run_all.bat` or run:
```bash
run_all.bat
```

### Manual Startup
**API:**
```bash
run_api.bat
```

**Worker:**
```bash
run_worker.bat
```
