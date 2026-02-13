
### The AI Math Agent (Google ADK & Gemini)
The heart of the system, powered by the **Google Agent Development Kit (ADK)** and **Gemini API**. The agent acts as an intelligent orchestrator, analyzing the user's request and deciding which specialized tool (or combination of tools) is best suited for the task.

It has access to a powerful set of tools:

*   **Image Interpreter**: Takes an image of a handwritten or printed equation and converts it into a machine-readable LaTeX string.
*   **Mathematical Vision (Gemini & Ultralytics Tools)**: Applies mathematical reasoning to visual inputs.
    *   *Quantitative Analysis (YOLO)*: For probability/statistics (e.g., counting objects).
    *   *Qualitative Analysis (Gemini)*: For interpreting graphs, charts, or geometric diagrams.
*   **Web Data Scraper (Playwright/Selenium)**: Scrapes specific data from websites for word problems requiring real-world context (e.g., financial rates, weather data).
*   **Problem Solver & Concept Explainer**: The core reasoning engine that performs calculations and formulates clear, step-by-step explanations.
*   **Similar Problem Finder (Supabase VectorDB)**: Finds conceptually similar problems the user has solved in the past to aid in learning and retention.

###  User Management & Data
*   **Firebase Auth**: Secure API communication.
*   **MongoDB**: Stores user problem history.
*   **Scalable Backend**: **Celery** and **Redis** manage long-running AI and scraping tasks.

---

## Tech Stack

*   **Language**: Python 3.10+
*   **Core API**: FastAPI
*   **AI Engine**: Google Gemini Pro (via Google ADK)
*   **Computer Vision**: Ultralytics YOLOv8, TrOCR
*   **Web Scraping**: Playwright, Selenium
*   **Database**: MongoDB (History), Supabase (Vector Search), Redis (Cache/Queue)
*   **Orchestration**: Celery, Google ADK
*   **Frontend**: Streamlit, Gradio
*   **Deployment**: Docker, Google Cloud Run

---

## Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/mathminds-ai.git
    cd mathminds-ai
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment:**
    Create a `.env` file in the root directory with the following keys:
    ```env
    GOOGLE_API_KEY=your_key
    REDIS_URL=redis://localhost:6379/0
    MONGO_URI=mongodb://localhost:27017/mathminds
    SUPABASE_URL=your_url
    SUPABASE_KEY=your_key
    FIREBASE_CREDENTIALS_PATH=path/to/creds.json
    ```
### Run the Full Stack (API + Worker)
**Windows:**
```bash
run_all.bat
```

**Docker:**
```bash
docker-compose up --build
```