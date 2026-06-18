# EasyInsight

EasyInsight is an autonomous data analysis platform that enables users to upload datasets (CSV, JSON, Excel) or establish their SQL/Postgres connection, run natural language queries, and automatically generate code, statistical analysis, and visualizations in a secure execution sandbox.

---

## Architecture

The application is split into two main components:
1. **Frontend**: A React application built with TypeScript, Vite, and Tailwind CSS.
2. **Backend**: A FastAPI server running Python 3.11, integrated with Groq (Llama 3.3) for query processing, Supabase for persistent storage, and DuckDB for lightweight analytical execution.

---

## Features

- **Natural Language Data Queries**: Type questions in plain English to extract insights from uploaded datasets.
- **Secure Sandbox Execution**: Executes LLM-generated code in a isolated Docker sandbox container.
- **Static Code Validation**: Scans generated Python code against security policies (imports, attributes, and function call analysis) before execution.
- **Dynamic Chart Generation**: Automatically designs, saves, and serves data visualizations. Includes dynamic signed URL resolution to prevent image access expiration.
- **Database Connectivity**: Connect directly to external PostgreSQL or MySQL databases to ingest and profile tables.
- **Workspace Isolation**: Save and separate chat sessions, datasets, and message histories.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional, but required for secure sandbox execution)

---

## Setup and Running

### 1. Backend Setup

Navigate to the backend directory:
```bash
cd backend
```

Create a virtual environment and install the dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file based on `.env.example`:
```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
REQUIRE_DOCKER=false  # Set to true in production
```

Start the backend server:
```bash
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

Navigate to the frontend directory:
```bash
cd ../frontend
```

Install the dependencies:
```bash
npm install
```

Create a `.env` file based on `.env.example`:
```env
VITE_API_BASE=http://localhost:8000/api
```

Start the frontend development server:
```bash
npm run dev
```

---

## Production Deployment (Hugging Face Spaces)

The backend is configured to run on Hugging Face Spaces using the Docker SDK.

1. Ensure the Dockerfile listens on port `7860`.
2. Configure variables and secrets in your Hugging Face Space Settings:
   - `GROQ_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `REQUIRE_DOCKER` (Set to `true` to enforce sandbox isolation)
3. Set `VITE_API_BASE` in the frontend production build to point to your Hugging Face Space app URL (e.g., `https://<username>-<space-name>.hf.space/api`).

---