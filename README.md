---
title: ScrapeRL
emoji: 🌖
colorFrom: blue
colorTo: gray
sdk: docker
pinned: false
---

# ScrapeRL 🌖

**AI-Powered Web Scraping with Reinforcement Learning** 

A next-generation web scraping system that uses reinforcement learning and multi-agent coordination to intelligently extract data from websites. Features multiple AI provider support (OpenAI, Anthropic, Google Gemini, Groq, NVIDIA), embeddings, real-time WebSocket updates, and a modern navy blue/cyan themed UI.

## ✨ Key Features

### 🤖 AI & Machine Learning
- **Multi-LLM Support** - OpenAI, Anthropic (Claude), Google (Gemini 2.5/2.0/3.0), Groq (Llama 3.3, Mixtral, Gemma2), NVIDIA (DeepSeek, Nemotron, Llama 3.3)
- **Smart Model Router** - Automatic selection of optimal model based on task type (code, reasoning, extraction, etc.)
- **Embeddings Service** - Semantic search with OpenAI and Google embeddings, in-memory caching
- **RL-Powered Scraping** - Reinforcement learning agents that learn optimal extraction strategies
- **Multi-Agent System** - Coordinated planner, extractor, and navigator agents

### ⚡ Real-Time Features
- **WebSocket Support** - Live progress updates during scraping episodes
- **Session-Based** - Clean slate on each session, no persistent rewards
- **Real-Time Metrics** - Track rewards, progress, and extraction in real-time

### 🎨 Modern UI/UX
- **Navy Blue & Cyan Theme** - Beautiful gradient design with glow effects
- **Fullscreen Layout** - Optimized for productivity
- **React + TailwindCSS** - Responsive and modern interface
- **Live Episode Monitoring** - Watch scraper progress in real-time

### 🔧 Developer Experience
- **FastAPI Backend** - High-performance async Python API
- **TypeScript Frontend** - Type-safe React application
- **Docker Ready** - Multi-stage builds with optimized images
- **Comprehensive Testing** - End-to-end test scripts included
- **Plugin System** - Extensible architecture with plugin support

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker (optional, but recommended)
- At least one AI provider API key (OpenAI, Anthropic, Google, Groq, or NVIDIA)

### Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/NeerajCodz/scrapeRL.git
cd scrapeRL

# Copy and configure environment
cp .env.example .env
# Edit .env and add your API keys

# Build and run
docker-compose up --build
```

Access the app at **http://localhost:7860**

### Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt

# Copy environment file
cp ../.env.example ../.env
# Add your API keys to .env

# Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Frontend will be at **http://localhost:5173**

## 🧪 OpenEnv Hackathon Inference Script

This repository now includes a root-level **`inference.py`** for OpenEnv-style evaluation.

### Required environment variables
- `API_BASE_URL` (defaulted in script)
- `MODEL_NAME` (defaulted in script)
- `HF_TOKEN` (**required**, no default)

### Run
```bash
python inference.py --task task_001 --benchmark openenv
```

### Output contract
`inference.py` emits strict structured stdout lines:
```text
[START] task=<task_name> env=<benchmark> model=<model_name>
[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
```

Notes:
- OpenAI client (`from openai import OpenAI`) is used as the default LLM caller.
- The script attempts OpenEnv SDK runtime first and falls back to `/api/episode/reset` + `/api/episode/step`.

## 📡 API Endpoints

### Core Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check and system status |
| POST | `/api/episode/reset` | Create a new scraping episode |
| POST | `/api/episode/step` | Execute an action in an episode |
| GET | `/api/episode/state/{episode_id}` | Get current episode state |

### Scrape Streaming Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scrape/stream` | Run scrape with SSE live events (`init`, `url_start`, `step`, `url_complete`, `complete`) |
| POST | `/api/scrape/` | Start scrape in background and return `session_id` |
| GET | `/api/scrape/{session_id}/status` | Session status, reward, steps, plugin info |
| GET | `/api/scrape/{session_id}/result` | Final formatted output (json/csv/markdown/text) |
| GET | `/api/scrape/sessions` | List active scrape sessions |
| DELETE | `/api/scrape/{session_id}` | Cancel running scrape session |

#### Scrape plugin capabilities
- Query assets can be discovered via `mcp-search` (non-URL asset text -> resolved links).
- Python sandbox analysis plugins:
  - `mcp-python-sandbox`
  - `proc-python`
  - `proc-pandas`
  - `proc-numpy`
  - `proc-bs4`
- Optional request field: `python_code` (sandboxed, validated code; must assign `result`).
- Sandbox execution is per-request isolated and cleaned after run.

### AI Provider Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/providers` | List all configured AI providers |
| GET | `/api/providers/{name}` | Get specific provider details |
| GET | `/api/providers/models/all` | List all available models |
| GET | `/api/providers/costs/summary` | Get cost tracking summary |

### WebSocket Endpoints
| Type | Endpoint | Description |
|------|----------|-------------|
| WS | `/ws/episode/{episode_id}` | Real-time episode/session updates |

### Other Endpoints
- `/api/tasks` - Task management
- `/api/agents` - Agent configuration
- `/api/tools` - MCP tools registry
- `/api/memory` - Memory management
- `/api/plugins` - Plugin system
- `/api/settings` - System settings

## 🏗️ Architecture

```
scrapeRL/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Configuration management
│   │   ├── api/
│   │   │   └── routes/          # API endpoints
│   │   │       ├── episode.py   # Episode management
│   │   │       ├── providers.py # AI provider APIs
│   │   │       ├── websocket.py # Real-time updates
│   │   │       └── ...
│   │   ├── core/
│   │   │   ├── env.py           # RL environment
│   │   │   ├── reward.py        # Reward engine
│   │   │   ├── embeddings.py   # Embeddings service
│   │   │   └── ...
│   │   ├── agents/
│   │   │   ├── coordinator.py   # Agent orchestration
│   │   │   ├── planner.py       # Planning agent
│   │   │   ├── extractor.py     # Extraction agent
│   │   │   └── navigator.py     # Navigation agent
│   │   ├── models/
│   │   │   ├── router.py        # Smart model router
│   │   │   └── providers/       # AI provider implementations
│   │   │       ├── openai.py    # OpenAI GPT-4
│   │   │       ├── anthropic.py # Claude 3.5 Sonnet
│   │   │       ├── google.py    # Gemini 2.5/2.0/3.0
│   │   │       ├── groq.py      # Llama 3.3, Mixtral
│   │   │       └── nvidia.py    # DeepSeek, Nemotron
│   │   ├── memory/              # Memory system
│   │   ├── tools/               # MCP tools
│   │   ├── plugins/             # Sandboxed plugin executors
│   │   └── types/               # Type definitions
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts  # WebSocket hook
│   │   │   └── useEpisodeProgress.ts # Episode tracking
│   │   ├── api/                 # API clients
│   │   ├── types/               # TypeScript types
│   │   └── index.css            # Navy/cyan theme
│   └── package.json
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml           # Local development
├── .env.example                 # Environment template
└── README.md
```

## ⚙️ Configuration

Create a `.env` file in the root directory (see `.env.example` for template):

### AI Provider API Keys (Optional - at least one recommended)
| Variable | Description | Provider |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | GPT-4o, GPT-4o-mini, O1 |
| `ANTHROPIC_API_KEY` | Anthropic API key | Claude 3.5 Sonnet, Haiku, Opus |
| `GOOGLE_API_KEY` | Google AI API key | Gemini 2.5 Pro/Flash, Gemini 2.0, Gemini 3.0 |
| `GROQ_API_KEY` | Groq API key | Llama 3.3 70B, Llama 3.2 Vision, Mixtral, Gemma2 |
| `NVIDIA_API_KEY` | NVIDIA API key | DeepSeek R1/V3.2, Nemotron 70B, Llama 3.3 70B |

### HuggingFace (Optional)
| Variable | Description |
|----------|-------------|
| `HF_TOKEN` | HuggingFace token for model access |

### App Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |

### CORS Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |

### Session & Memory
| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_TIMEOUT` | `3600` | Session timeout in seconds |
| `MEMORY_TTL` | `86400` | Memory TTL in seconds |

## 🧪 Testing

Run the end-to-end test script:

```bash
cd backend
python test_scraper.py
```

This will:
1. Create a scraping episode
2. Execute navigation and extraction actions
3. Track rewards and progress
4. Verify WebSocket connectivity
5. Display final results

Expected output:
```
✓ Episode created: <uuid>
✓ Action executed successfully
  Reward: 0.65
  Progress: 0.0%
✓ Final state retrieved
  Steps: 3
  Total reward: 2.26
```

## 🚀 Deployment

### HuggingFace Spaces

This app is configured for HuggingFace Spaces with Docker SDK:
- Port: 7860
- Health check: `/api/health`
- Auto-builds on push
- Multi-stage build for optimized image size

### Manual Docker

```bash
# Run frontend + backend together
docker compose up --build
```

After startup:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api`

### Environment Variables in Production

Set all required environment variables in your deployment platform:
- HuggingFace Spaces: Settings → Repository secrets
- Docker: Use `--env-file` or environment section in docker-compose
- Kubernetes: ConfigMaps and Secrets

## 🎯 Usage Examples

### Example 1: Simple Scraping Task

```bash
curl -X POST http://localhost:8000/api/episode/reset \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "scrape-quotes",
    "config": {
      "start_url": "http://quotes.toscrape.com",
      "target_fields": {
        "quotes": {"text": "quote text", "author": "author name"}
      },
      "max_steps": 20
    }
  }'
```

### Example 2: WebSocket Connection

```javascript
// Frontend JavaScript
const ws = new WebSocket('ws://localhost:8000/ws/episode/<episode_id>');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'progress') {
    console.log(`Step ${message.step}: ${message.action_type}`);
    console.log(`Reward: ${message.reward}, Progress: ${message.progress}%`);
  }
  
  if (message.type === 'completion') {
    console.log(`Episode completed! Success: ${message.success}`);
    console.log(`Total reward: ${message.total_reward}`);
  }
};
```

## 🤝 Contributing

Contributions welcome! This project follows conventional commit messages:
- `feat:` - New features
- `fix:` - Bug fixes
- `chore:` - Maintenance tasks
- `docs:` - Documentation updates
- `test:` - Test additions/updates

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Built with FastAPI, React, TailwindCSS
- Powered by OpenAI, Anthropic, Google, Groq, and NVIDIA AI models
- Inspired by reinforcement learning research in web automation
