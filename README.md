---
title: ScrapeRL
emoji: 🌖
colorFrom: blue
colorTo: gray
sdk: docker
pinned: false
---

# ScrapeRL 🌖

A reinforcement learning-powered web scraping tool with a FastAPI backend and React frontend.

## Features

- 🤖 **RL-Powered Scraping** - Intelligent web scraping using reinforcement learning
- 🔌 **Multi-LLM Support** - Works with OpenAI, Anthropic, Google, and Groq
- ⚡ **FastAPI Backend** - High-performance async API
- 🎨 **React Frontend** - Modern, responsive UI
- 🐳 **Docker Ready** - Easy deployment with Docker
- 🤗 **HuggingFace Spaces** - One-click deployment

## Quick Start

### Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/scrapeRL.git
cd scrapeRL

# Copy environment file
cp .env.example .env

# Build and run
docker-compose up --build
```

Access the app at http://localhost:7860

### Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 7860
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/...` | API routes |
| GET | `/` | Serve frontend |

## Architecture

```
scrapeRL/
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app entry
│   │   ├── api/            # API routes
│   │   ├── core/           # Core logic
│   │   └── services/       # Business logic
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── package.json
├── Dockerfile              # Multi-stage build
├── docker-compose.yml      # Local development
└── .env.example
```

## Configuration

Set these environment variables (see `.env.example`):

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | No |
| `ANTHROPIC_API_KEY` | Anthropic API key | No |
| `GOOGLE_API_KEY` | Google AI API key | No |
| `GROQ_API_KEY` | Groq API key | No |
| `HF_TOKEN` | HuggingFace token | No |
| `DEBUG` | Enable debug mode | No |
| `LOG_LEVEL` | Logging level | No |

## Deployment

### HuggingFace Spaces

This app is configured for HuggingFace Spaces with Docker SDK:
- Port: 7860
- Health check: `/health`
- Auto-builds on push

### Manual Docker

```bash
docker build -t scraperl .
docker run -p 7860:7860 --env-file .env scraperl
```

## License

MIT License - see [LICENSE](LICENSE) for details.
