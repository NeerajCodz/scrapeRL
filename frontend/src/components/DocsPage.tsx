import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Book,
  Search,
  ExternalLink,
  Home,
  Cpu,
  Plug,
  Database,
  Terminal,
} from 'lucide-react';
import { classNames } from '@/utils/helpers';

interface DocsPageProps {
  className?: string;
}

interface DocSection {
  id: string;
  title: string;
  icon: React.ElementType;
  content: string;
}

// Documentation content
const userGuideContent = `
# ScrapeRL Documentation

Welcome to ScrapeRL - an advanced Reinforcement Learning-powered web scraping environment.

---

## Getting Started

### What is ScrapeRL?

ScrapeRL is an intelligent web scraping system that uses Reinforcement Learning (RL) to learn and adapt scraping strategies. Unlike traditional scrapers, ScrapeRL can:

- **Learn from experience** - Improve scraping strategies over time
- **Adapt to changes** - Handle website structure changes automatically
- **Multi-agent coordination** - Use specialized agents for different tasks
- **Memory-enhanced** - Remember patterns and optimize future runs

### Quick Start

1. **Enter a Target URL** - Provide the webpage you want to scrape
2. **Write an Instruction** - Describe what data you want to extract
3. **Configure Options** - Select model, agents, and plugins
4. **Start Episode** - Click Start and watch the magic happen!

### Example Task

\`\`\`
URL: https://example.com/products
Instruction: Extract all product names, prices, and descriptions
Task Type: Medium
\`\`\`

---

## Dashboard Overview

The dashboard is your command center for monitoring and controlling scraping operations.

### Layout Structure

| Section | Description |
|---------|-------------|
| **Input Bar** | Enter URL, instruction, and configure task |
| **Left Sidebar** | View active agents, MCPs, skills, and tools |
| **Center Area** | Main visualization and current observation |
| **Right Sidebar** | Memory stats, extracted data, recent actions |
| **Bottom Logs** | Real-time terminal-style log output |

### Task Types

| Type | Description | Use Case |
|------|-------------|----------|
| 🟢 **Low** | Simple single-page scraping | Product page, article text |
| 🟡 **Medium** | Multi-page with navigation | Search results, listings |
| 🔴 **High** | Complex interactive tasks | Login-required, forms |

---

## Agents

ScrapeRL uses a multi-agent architecture where specialized agents handle different aspects of scraping.

### Available Agents

| Agent | Role | Description |
|-------|------|-------------|
| **Coordinator** | 🎯 Orchestrator | Manages all other agents |
| **Scraper** | 📄 Extractor | Extracts data from content |
| **Navigator** | 🧭 Navigation | Handles page navigation |
| **Analyzer** | 🔍 Analysis | Analyzes data patterns |
| **Validator** | ✅ Validation | Validates data quality |

---

## Plugins

Extend ScrapeRL's capabilities with plugins.

### Categories

- **MCPs** - Browser automation (Browser Use, Puppeteer, Playwright)
- **Skills** - Task capabilities (Web Scraping, Data Extraction)
- **APIs** - External services (Firecrawl, Jina Reader, Serper)
- **Vision** - Visual AI (GPT-4V, Gemini Vision, Claude Vision)

---

## Memory System

| Layer | Purpose | Retention |
|-------|---------|-----------|
| **Working** | Current task | Session |
| **Episodic** | Experiences | Persistent |
| **Semantic** | Patterns | Persistent |
| **Procedural** | Actions | Persistent |

---

## API Keys

Configure in **Settings > API Keys**:

| Provider | Models |
|----------|--------|
| Groq | GPT-OSS 120B (Default) |
| Google | Gemini 2.5 Flash |
| OpenAI | GPT-4 Turbo |
| Anthropic | Claude 3 Opus |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| \`Ctrl + Enter\` | Start/Stop episode |
| \`Ctrl + L\` | Clear logs |
| \`Escape\` | Close popups |
`;

const agentsContent = `
# Agents Documentation

## Multi-Agent Architecture

ScrapeRL employs a sophisticated multi-agent system where each agent specializes in specific tasks.

### Coordinator Agent

The brain of the operation. It:
- Decides which agents to activate
- Plans the scraping strategy
- Handles error recovery
- Optimizes resource usage

### Scraper Agent

Responsible for data extraction:
- HTML parsing and element selection
- Text content extraction
- Structured data identification
- Pattern recognition

### Navigator Agent

Handles all page interactions:
- URL navigation
- Link clicking
- Form submissions
- Pagination handling

### Analyzer Agent

Processes and analyzes data:
- Data validation
- Pattern detection
- Quality assessment
- Anomaly detection

### Validator Agent

Ensures data quality:
- Schema validation
- Completeness checks
- Duplicate detection
- Format verification

## Agent Communication

Agents communicate through a shared memory system:

\`\`\`
Coordinator -> Scraper: "Extract product data"
Scraper -> Memory: "Store extracted items"
Memory -> Analyzer: "New data available"
Analyzer -> Validator: "Validate these records"
Validator -> Coordinator: "Validation complete"
\`\`\`
`;

const pluginsContent = `
# Plugins Documentation

## Plugin Categories

### MCPs (Model Context Protocols)

Browser automation tools that integrate with AI models.

#### Browser Use
- AI-powered browser control
- Natural language commands
- Visual understanding
- Automatic element detection

#### Puppeteer MCP
- Headless Chrome automation
- Screenshot capture
- PDF generation
- Network interception

#### Playwright MCP
- Cross-browser support
- Mobile emulation
- Video recording
- Trace viewer

### Skills

Specialized capabilities for specific tasks.

#### Web Scraping
- CSS/XPath selectors
- Data extraction patterns
- Pagination handling
- Rate limiting

#### Data Extraction
- JSON/XML parsing
- Table extraction
- List processing
- Content classification

### APIs

External service integrations.

#### Firecrawl
- High-performance crawling
- JavaScript rendering
- Proxy rotation
- Rate limiting

#### Jina Reader
- Content extraction API
- Clean text output
- Structured data
- Multi-format support

### Vision Models

Visual understanding capabilities.

#### GPT-4 Vision
- Image analysis
- Screenshot understanding
- UI element detection
- Text extraction from images

## Installing Plugins

1. Navigate to Plugins page
2. Browse categories
3. Click Install on desired plugin
4. Configure API keys if required
`;

const memoryContent = `
# Memory System Documentation

## Hierarchical Memory Architecture

ScrapeRL uses a four-layer memory system inspired by human cognitive architecture.

### Working Memory

**Purpose:** Active task context

- Current URL and page state
- Active extraction targets
- Temporary calculations
- Session-specific data

**Retention:** Cleared after each episode

### Episodic Memory

**Purpose:** Experience records

- Past scraping sessions
- Success/failure patterns
- Timing data
- Action sequences

**Retention:** Persistent across sessions

### Semantic Memory

**Purpose:** Learned knowledge

- Website patterns
- Extraction rules
- Domain knowledge
- Best practices

**Retention:** Long-term persistent

### Procedural Memory

**Purpose:** Action sequences

- Navigation patterns
- Interaction sequences
- Recovery procedures
- Optimization strategies

**Retention:** Long-term persistent

## Memory Operations

### Store
\`\`\`json
{
  "content": "Product prices on example.com follow pattern...",
  "memory_type": "semantic",
  "metadata": {
    "domain": "example.com",
    "confidence": 0.95
  }
}
\`\`\`

### Query
\`\`\`json
{
  "query": "price extraction patterns",
  "memory_type": "semantic",
  "limit": 10
}
\`\`\`

### Consolidation

Automatic promotion of important memories:
- Working → Episodic: At episode end
- Episodic → Semantic: Pattern detection
- Episodic → Procedural: Action sequences
`;

const apiContent = `
# API Reference

## Base URL

\`\`\`
http://localhost:7860/api
\`\`\`

## Health Check

### GET /health

Check system status.

**Response:**
\`\`\`json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-03-28T00:00:00Z"
}
\`\`\`

## Episode Endpoints

### POST /episode/reset

Start a new episode.

**Request:**
\`\`\`json
{
  "task_id": "scrape-products"
}
\`\`\`

### POST /episode/step

Execute an action.

**Request:**
\`\`\`json
{
  "action": "navigate",
  "params": { "url": "https://example.com" }
}
\`\`\`

### GET /episode/state

Get current state.

## Memory Endpoints

### POST /memory/store

Store a memory entry.

### POST /memory/query

Query memories.

### GET /memory/stats/overview

Get memory statistics.

## Plugin Endpoints

### GET /plugins/

List all plugins.

### POST /plugins/install

Install a plugin.

### POST /plugins/uninstall

Uninstall a plugin.

## Settings Endpoints

### GET /settings/

Get current settings.

### POST /settings/api-key

Update API key.

### POST /settings/model

Select active model.
`;

const docs: DocSection[] = [
  { id: 'guide', title: 'User Guide', icon: Home, content: userGuideContent },
  { id: 'agents', title: 'Agents', icon: Cpu, content: agentsContent },
  { id: 'plugins', title: 'Plugins', icon: Plug, content: pluginsContent },
  { id: 'memory', title: 'Memory System', icon: Database, content: memoryContent },
  { id: 'api', title: 'API Reference', icon: Terminal, content: apiContent },
];

export const DocsPage: React.FC<DocsPageProps> = ({ className }) => {
  const [activeDoc, setActiveDoc] = useState<string>('guide');
  const [searchQuery, setSearchQuery] = useState('');

  const currentDoc = docs.find((d) => d.id === activeDoc) || docs[0];

  return (
    <div className={classNames('flex h-[calc(100vh-120px)]', className)}>
      {/* Left Sidebar - Navigation */}
      <div className="w-64 flex-shrink-0 bg-gray-800/30 border-r border-gray-700/50 flex flex-col">
        <div className="p-4 border-b border-gray-700/50">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Book className="w-5 h-5 text-cyan-400" />
            Documentation
          </h2>
          <p className="text-xs text-gray-500 mt-1">Learn how to use ScrapeRL</p>
        </div>

        {/* Search */}
        <div className="p-3 border-b border-gray-700/50">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search docs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-gray-900/50 border border-gray-700/50 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50"
            />
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {docs.map((doc) => {
            const Icon = doc.icon;
            const isActive = activeDoc === doc.id;
            return (
              <button
                key={doc.id}
                onClick={() => setActiveDoc(doc.id)}
                className={classNames(
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all',
                  isActive
                    ? 'bg-cyan-500/20 border border-cyan-500/30 text-cyan-400'
                    : 'hover:bg-gray-700/50 text-gray-400 hover:text-gray-200'
                )}
              >
                <Icon className={classNames('w-4 h-4', isActive ? 'text-cyan-400' : 'text-gray-500')} />
                <span className="text-sm font-medium">{doc.title}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-gray-700/50">
          <a
            href="https://github.com/NeerajCodz/scrapeRL"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            View on GitHub
          </a>
        </div>
      </div>

      {/* Main Content - Markdown Viewer */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto p-8">
          <article className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => (
                  <h1 className="text-3xl font-bold text-white mb-6 pb-4 border-b border-gray-700/50">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-2xl font-semibold text-white mt-8 mb-4">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-xl font-semibold text-gray-200 mt-6 mb-3">{children}</h3>
                ),
                h4: ({ children }) => (
                  <h4 className="text-lg font-medium text-gray-300 mt-4 mb-2">{children}</h4>
                ),
                p: ({ children }) => <p className="text-gray-400 mb-4 leading-relaxed">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside text-gray-400 mb-4 space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside text-gray-400 mb-4 space-y-1">{children}</ol>,
                li: ({ children }) => <li className="text-gray-400">{children}</li>,
                strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                em: ({ children }) => <em className="text-gray-300">{children}</em>,
                code: ({ children, className }) => {
                  const isBlock = className?.includes('language-');
                  if (isBlock) {
                    return (
                      <code className="block bg-gray-900 rounded-lg p-4 text-sm font-mono text-gray-300 overflow-x-auto">
                        {children}
                      </code>
                    );
                  }
                  return (
                    <code className="bg-gray-800 text-cyan-400 px-1.5 py-0.5 rounded text-sm font-mono">
                      {children}
                    </code>
                  );
                },
                pre: ({ children }) => <pre className="mb-4">{children}</pre>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-cyan-500/50 pl-4 italic text-gray-400 my-4">
                    {children}
                  </blockquote>
                ),
                table: ({ children }) => (
                  <div className="overflow-x-auto mb-4">
                    <table className="w-full border-collapse">{children}</table>
                  </div>
                ),
                thead: ({ children }) => <thead className="bg-gray-800/50">{children}</thead>,
                th: ({ children }) => (
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-300 border-b border-gray-700">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-4 py-2 text-sm text-gray-400 border-b border-gray-800">{children}</td>
                ),
                hr: () => <hr className="border-gray-700/50 my-8" />,
                a: ({ href, children }) => (
                  <a
                    href={href}
                    className="text-cyan-400 hover:text-cyan-300 underline underline-offset-2"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {currentDoc.content}
            </ReactMarkdown>
          </article>
        </div>
      </div>
    </div>
  );
};

export default DocsPage;
