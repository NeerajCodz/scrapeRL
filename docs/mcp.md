# 🔌 MCP Server Integration

## Table of Contents
1. [Overview](#overview)
2. [Available MCP Servers](#available-mcp-servers)
3. [Tool Registry & Discovery](#tool-registry--discovery)
4. [HTML Processing MCPs](#html-processing-mcps)
5. [Lazy Loading System](#lazy-loading-system)
6. [MCP Composition](#mcp-composition)
7. [Testing Panel](#testing-panel)
8. [Configuration](#configuration)

---

## Overview

The **Model Context Protocol (MCP)** enables the WebScraper agent to interact with external tools, databases, and services through a standardized interface. MCP servers expose **tools** that the agent can discover and use dynamically.

### Why MCP?

**Without MCP:**
- Agent limited to built-in capabilities
- Cannot access external databases, APIs, or specialized libraries
- Difficult to extend without code changes

**With MCP:**
- ✅ Dynamically discover and use 100+ community tools
- ✅ Access databases (PostgreSQL, MongoDB, etc.)
- ✅ Use specialized libraries (BeautifulSoup, Selenium, Playwright)
- ✅ Integrate with external APIs (Google, GitHub, etc.)
- ✅ Extend agent capabilities without code changes

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WebScraper Agent                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │            MCP Tool Registry                        │     │
│  │  - Discovers available tools from all MCP servers  │     │
│  │  - Provides tool metadata to agent                 │     │
│  │  - Routes tool calls to appropriate server         │     │
│  └────────────────┬───────────────────────────────────┘     │
│                   │                                          │
└───────────────────┼──────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┬──────────────┬─────────────┐
        │           │           │              │             │
        ▼           ▼           ▼              ▼             ▼
┌──────────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ HTML Parser  │ │Browser  │ │ Database │ │  File    │ │  Custom  │
│     MCP      │ │  MCP    │ │   MCP    │ │  System  │ │   MCP    │
│              │ │         │ │          │ │   MCP    │ │          │
│• BeautifulSoup││• Puppeteer││• Postgres││• Read    ││• Your    │
│• lxml        ││• Playwright││• MongoDB │││• Write   ││  tools   │
│• html5lib    ││• Selenium ││• Redis   │││• Search  ││          │
└──────────────┘ └─────────┘ └──────────┘ └──────────┘ └──────────┘
```

---

## Available MCP Servers

### 1. HTML Processing & Parsing

#### **beautifulsoup-mcp**
Advanced HTML parsing and extraction.

**Tools:**
- `parse_html(html: str, parser: str = "html.parser")` → Parse HTML into DOM tree
- `find_all(html: str, selector: str)` → CSS selector search
- `extract_text(html: str, selector: str)` → Extract text content
- `extract_attributes(html: str, selector: str, attrs: List[str])` → Get element attributes
- `clean_html(html: str)` → Remove scripts, styles, comments
- `extract_tables(html: str)` → Parse all tables into structured data

**Configuration:**
```json
{
  "mcpServers": {
    "beautifulsoup": {
      "command": "python",
      "args": ["-m", "mcp_beautifulsoup"],
      "enabled": true,
      "autoDownload": true,
      "config": {
        "default_parser": "lxml",  
        "encodings": ["utf-8", "latin-1"]
      }
    }
  }
}
```

**Example Usage:**
```python
# Agent action
action = Action(
    action_type="MCP_TOOL_CALL",
    tool_name="beautifulsoup.find_all",
    tool_params={
        "html": observation.page_html,
        "selector": "div.product-card"
    }
)

# Response
{
    "products": [
        {"name": "Widget", "price": "$49.99"},
        {"name": "Gadget", "price": "$39.99"}
    ]
}
```

#### **lxml-mcp**
Fast XML/HTML parsing with XPath support.

**Tools:**
- `xpath_query(html: str, xpath: str)` → XPath extraction
- `css_select(html: str, css: str)` → CSS selector (fast)
- `validate_html(html: str)` → Check well-formedness

#### **html5lib-mcp**
Standards-compliant HTML5 parsing.

**Tools:**
- `parse_html5(html: str)` → Parse like a browser would
- `sanitize_html(html: str, allowed_tags: List[str])` → Safe HTML cleaning

### 2. Browser Automation

#### **playwright-mcp**
Full browser automation with JavaScript rendering.

**Tools:**
- `navigate(url: str, wait_for: str = "networkidle")` → Load page with JS
- `click(selector: str)` → Click element
- `fill_form(selector: str, value: str)` → Fill input
- `screenshot(selector: str = None)` → Capture screenshot
- `wait_for_selector(selector: str, timeout: int = 5000)` → Wait for element
- `execute_script(script: str)` → Run custom JavaScript

**Use Cases:**
- Pages with client-side rendering (React, Vue, Angular)
- Infinite scroll / lazy loading
- Forms and interactions
- Captcha handling

**Configuration:**
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp-server"],
      "enabled": false,  // Only enable when needed (heavy)
      "autoDownload": true,
      "config": {
        "browser": "chromium",
        "headless": true,
        "viewport": {"width": 1920, "height": 1080}
      }
    }
  }
}
```

#### **puppeteer-mcp**
Lightweight browser automation (Chrome DevTools Protocol).

Similar to Playwright but lighter weight.

#### **selenium-mcp**
Legacy browser automation (more compatible, slower).

### 3. Database Access

#### **postgresql-mcp**
Access PostgreSQL databases.

**Tools:**
- `query(sql: str, params: List = [])` → Execute SELECT
- `execute(sql: str, params: List = [])` → Execute INSERT/UPDATE/DELETE
- `list_tables()` → Get schema

**Use Case:** Store scraped data directly to production database.

#### **mongodb-mcp**
Access MongoDB collections.

**Tools:**
- `find(collection: str, query: dict)` → Query documents
- `insert(collection: str, document: dict)` → Insert document
- `aggregate(collection: str, pipeline: List)` → Aggregation pipeline

#### **redis-mcp**
Fast cache and pub/sub.

**Tools:**
- `get(key: str)` → Retrieve cached value
- `set(key: str, value: str, ttl: int)` → Cache value
- `publish(channel: str, message: str)` → Pub/sub

**Use Case:** Cache parsed HTML, share state between agents.

### 4. File System

#### **filesystem-mcp**
Read/write local files.

**Tools:**
- `read_file(path: str)` → Read text/binary file
- `write_file(path: str, content: str)` → Write file
- `list_directory(path: str)` → List files
- `search_files(pattern: str)` → Glob search

**Use Case:** Save scraped data to CSV/JSON, read configuration files.

### 5. Search Engines

#### **google-search-mcp**
Google Search API integration.

**Tools:**
- `search(query: str, num: int = 10)` → Google Search results
- `search_images(query: str)` → Image search

**Configuration:**
```json
{
  "mcpServers": {
    "google-search": {
      "command": "python",
      "args": ["-m", "mcp_google_search"],
      "enabled": true,
      "autoDownload": true,
      "config": {
        "api_key": "YOUR_GOOGLE_API_KEY",
        "search_engine_id": "YOUR_SEARCH_ENGINE_ID"
      }
    }
  }
}
```

#### **bing-search-mcp**
Bing Search API.

#### **brave-search-mcp**
Privacy-focused search (Brave Search API).

#### **duckduckgo-mcp**
Free, no-API search.

**Tools:**
- `search(query: str, max_results: int = 10)` → DDG results

### 6. Data Extraction

#### **readability-mcp**
Extract main article content (removes ads, navigation, etc.).

**Tools:**
- `extract_article(html: str)` → Returns clean article text + metadata

**Use Case:** Extract blog posts, news articles, documentation.

#### **trafilatura-mcp**
Advanced web scraping and text extraction.

**Tools:**
- `extract(url: str)` → Extract main content
- `extract_metadata(html: str)` → Get title, author, date, etc.

#### **newspaper-mcp**
News article extraction and NLP.

**Tools:**
- `parse_article(url: str)` → Full article data
- `extract_keywords(text: str)` → Keyword extraction
- `summarize(text: str)` → Auto-summarization

### 7. Data Validation

#### **cerberus-mcp**
Schema validation for extracted data.

**Tools:**
- `validate(data: dict, schema: dict)` → Validate against schema

**Example:**
```python
# Define schema
schema = {
    "product_name": {"type": "string", "required": True, "minlength": 1},
    "price": {"type": "float", "required": True, "min": 0},
    "rating": {"type": "float", "min": 0, "max": 5}
}

# Validate extracted data
result = mcp.call("cerberus.validate", data=extracted_data, schema=schema)
if not result["valid"]:
    print("Validation errors:", result["errors"])
```

#### **pydantic-mcp**
Pydantic model validation.

### 8. Computer Vision

#### **ocr-mcp**
Extract text from images (Tesseract OCR).

**Tools:**
- `extract_text(image_path: str, lang: str = "eng")` → OCR text

**Use Case:** Extract prices from product images, read captchas (if legal).

#### **image-analysis-mcp**
Vision AI (GPT-4 Vision, Claude Vision).

**Tools:**
- `describe_image(image_path: str)` → Natural language description
- `extract_structured(image_path: str, schema: dict)` → Extract structured data from images

### 9. HTTP & Networking

#### **requests-mcp**
HTTP client with retry, session management.

**Tools:**
- `get(url: str, headers: dict = {})` → HTTP GET
- `post(url: str, data: dict = {})` → HTTP POST

#### **proxy-manager-mcp**
Manage proxy rotation, IP reputation.

**Tools:**
- `get_proxy()` → Get next proxy from pool
- `report_dead_proxy(proxy: str)` → Mark proxy as failed

### 10. Utility

#### **regex-mcp**
Advanced regex operations.

**Tools:**
- `find_all(pattern: str, text: str)` → Find all matches
- `replace(pattern: str, replacement: str, text: str)` → Regex replace
- `validate(pattern: str)` → Check if regex is valid

#### **datetime-mcp**
Parse and normalize dates.

**Tools:**
- `parse_date(text: str)` → Parse natural language dates
- `normalize_timezone(date: str, tz: str)` → Convert timezone

#### **currency-mcp**
Currency parsing and conversion.

**Tools:**
- `parse_price(text: str)` → Extract price and currency
- `convert(amount: float, from_currency: str, to_currency: str)` → Convert

---

## Tool Registry & Discovery

The **Tool Registry** automatically discovers all available tools from enabled MCP servers.

### Architecture

```python
class MCPToolRegistry:
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.tools: Dict[str, Tool] = {}  # tool_name → Tool
    
    def discover_servers(self, config: MCPConfig):
        """Load and connect to all enabled MCP servers."""
        for server_name, server_config in config.mcpServers.items():
            if not server_config.enabled:
                continue
            
            # Auto-download if needed
            if server_config.autoDownload and not self.is_installed(server_config):
                self.download_and_install(server_name, server_config)
            
            # Connect to server
            server = self.connect_server(server_name, server_config)
            self.servers[server_name] = server
            
            # Discover tools
            for tool in server.list_tools():
                full_name = f"{server_name}.{tool.name}"
                self.tools[full_name] = tool
    
    def get_tool(self, tool_name: str) -> Tool:
        """Get tool by fully qualified name (server.tool)."""
        return self.tools.get(tool_name)
    
    def search_tools(self, query: str, category: str = None) -> List[Tool]:
        """Search tools by natural language query."""
        # Semantic search using tool descriptions
        candidates = list(self.tools.values())
        
        if category:
            candidates = [t for t in candidates if t.category == category]
        
        # Embed query and tools, rank by similarity
        scored = []
        for tool in candidates:
            score = self.semantic_similarity(query, tool.description)
            scored.append((tool, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [tool for tool, score in scored[:10]]
```

### Tool Metadata

Each tool exposes rich metadata:

```python
class Tool(BaseModel):
    name: str                          # e.g., "find_all"
    full_name: str                     # e.g., "beautifulsoup.find_all"
    server: str                        # Server name
    description: str                   # Human-readable description
    category: str                      # "parsing" | "browser" | "database" | ...
    input_schema: Dict[str, Any]       # JSON Schema for parameters
    output_schema: Dict[str, Any]      # JSON Schema for return value
    examples: List[ToolExample]        # Usage examples
    cost: ToolCost                     # Time/resource cost estimate
    requires_auth: bool                # Needs API keys?
    rate_limit: Optional[RateLimit]    # Rate limiting info
```

**Example:**
```python
Tool(
    name="find_all",
    full_name="beautifulsoup.find_all",
    server="beautifulsoup",
    description="Find all HTML elements matching a CSS selector",
    category="parsing",
    input_schema={
        "type": "object",
        "properties": {
            "html": {"type": "string", "description": "HTML content to search"},
            "selector": {"type": "string", "description": "CSS selector"}
        },
        "required": ["html", "selector"]
    },
    output_schema={
        "type": "array",
        "items": {"type": "object"}
    },
    examples=[
        ToolExample(
            input={"html": "<div class='item'>A</div>", "selector": ".item"},
            output=[{"tag": "div", "text": "A", "class": "item"}]
        )
    ],
    cost=ToolCost(time_ms=10, cpu_intensive=False),
    requires_auth=False
)
```

### Auto Tool Discovery by Agent

The agent can query the registry to find relevant tools:

```python
# Agent needs to parse HTML
available_tools = tool_registry.search_tools(
    query="parse HTML and extract elements by CSS selector",
    category="parsing"
)

# Top result: beautifulsoup.find_all
tool = available_tools[0]

# Agent calls the tool
action = Action(
    action_type="MCP_TOOL_CALL",
    tool_name=tool.full_name,
    tool_params={
        "html": observation.page_html,
        "selector": "div.product-price"
    }
)
```

---

## HTML Processing MCPs

### BeautifulSoup MCP (Detailed)

**Installation:**
```bash
pip install mcp-beautifulsoup
```

**Tools:**

#### 1. `find_all(html, selector, limit=None)`
Find all elements matching CSS selector.

```python
result = mcp.call("beautifulsoup.find_all", {
    "html": "<div class='price'>$10</div><div class='price'>$20</div>",
    "selector": "div.price"
})
# Returns: [{"text": "$10"}, {"text": "$20"}]
```

#### 2. `find_one(html, selector)`
Find first matching element.

```python
result = mcp.call("beautifulsoup.find_one", {
    "html": obs.page_html,
    "selector": "h1.product-title"
})
# Returns: {"text": "Widget Pro", "tag": "h1"}
```

#### 3. `extract_tables(html)`
Parse all `<table>` elements into structured data.

```python
result = mcp.call("beautifulsoup.extract_tables", {"html": obs.page_html})
# Returns:
[
    {
        "headers": ["Product", "Price", "Stock"],
        "rows": [
            ["Widget", "$49.99", "In Stock"],
            ["Gadget", "$39.99", "Out of Stock"]
        ]
    }
]
```

#### 4. `extract_links(html, base_url=None)`
Extract all links from page.

```python
result = mcp.call("beautifulsoup.extract_links", {
    "html": obs.page_html,
    "base_url": "https://example.com"
})
# Returns:
[
    {"url": "https://example.com/product/123", "text": "View Product"},
    {"url": "https://example.com/category/widgets", "text": "Widgets"}
]
```

#### 5. `clean_html(html, remove=['script', 'style', 'noscript'])`
Remove unwanted elements.

```python
result = mcp.call("beautifulsoup.clean_html", {
    "html": obs.page_html,
    "remove": ["script", "style", "footer", "nav"]
})
# Returns: Clean HTML without ads, scripts, navigation
```

#### 6. `smart_extract(html, field_name)`
Intelligent extraction based on field name.

```python
# Agent wants to extract "price"
result = mcp.call("beautifulsoup.smart_extract", {
    "html": obs.page_html,
    "field_name": "price"
})
# MCP searches for:
#  - Elements with class/id containing "price"
#  - Text matching price patterns ($X.XX, €X,XX)
#  - Schema.org markup (itemprop="price")
# Returns: {"value": "$49.99", "confidence": 0.92, "selector": "span.product-price"}
```

### Batch Processing for Long Content

When HTML is too large (> 100KB), process in batches:

```python
class HTMLBatchProcessor:
    def __init__(self, mcp_client, chunk_size: int = 50000):
        self.mcp = mcp_client
        self.chunk_size = chunk_size
    
    def process_large_html(self, html: str, selector: str) -> List[Dict]:
        """Process large HTML in chunks."""
        # Split HTML into meaningful chunks (by sections, not mid-tag)
        chunks = self.split_html_intelligently(html)
        
        results = []
        for i, chunk in enumerate(chunks):
            # Process each chunk
            chunk_results = self.mcp.call("beautifulsoup.find_all", {
                "html": chunk,
                "selector": selector
            })
            
            # Deduplicate across chunk boundaries
            results.extend(self.deduplicate(chunk_results, results))
        
        return results
    
    def split_html_intelligently(self, html: str) -> List[str]:
        """Split HTML at section boundaries, not mid-tag."""
        soup = BeautifulSoup(html, 'lxml')
        
        # Split by major sections (article, section, div.container, etc.)
        sections = soup.find_all(['article', 'section', 'main'])
        
        chunks = []
        current_chunk = ""
        
        for section in sections:
            section_html = str(section)
            
            if len(current_chunk) + len(section_html) > self.chunk_size:
                chunks.append(current_chunk)
                current_chunk = section_html
            else:
                current_chunk += section_html
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
```

---

## Lazy Loading System

MCP servers are **NOT downloaded by default**. They are installed on-demand when first used.

### Download-on-Demand Flow

```
Agent wants to use a tool
         │
         ▼
Is MCP server installed?
         │
    ┌────┴────┐
   No        Yes
    │          │
    ▼          ▼
Show dialog   Execute tool
"Download     
 server X?"   
    │
┌───┴───┐
No     Yes
│       │
Skip    Download & Install
        │
        ▼
     Cache for future use
        │
        ▼
     Execute tool
```

### Implementation

```python
class LazyMCPLoader:
    def __init__(self):
        self.installed_servers: Set[str] = set()
        self.download_queue: Queue[str] = Queue()
    
    def ensure_server(self, server_name: str, config: MCPServerConfig) -> bool:
        """Ensure MCP server is installed, download if needed."""
        if server_name in self.installed_servers:
            return True
        
        if not config.autoDownload:
            # Prompt user
            if not self.prompt_user_download(server_name):
                return False
        
        # Download and install
        return self.download_server(server_name, config)
    
    def download_server(self, server_name: str, config: MCPServerConfig) -> bool:
        """Download and install MCP server."""
        try:
            logger.info(f"Downloading MCP server: {server_name}")
            
            if config.command == "npx":
                # NPM package
                subprocess.run([
                    "npm", "install", "-g", config.args[1]
                ], check=True)
            
            elif config.command == "python":
                # Python package
                package_name = config.args[1].replace("-m ", "")
                subprocess.run([
                    "pip", "install", package_name
                ], check=True)
            
            self.installed_servers.add(server_name)
            logger.info(f"✓ Installed {server_name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to install {server_name}: {e}")
            return False
    
    def prompt_user_download(self, server_name: str) -> bool:
        """Ask user if they want to download the server."""
        # In UI, show dialog:
        # "Tool X requires MCP server Y. Download and install? (50MB) [Yes] [No]"
        return self.show_download_dialog(server_name)
```

### UI Dialog

```
┌──────────────────────────────────────────────────────────┐
│ MCP Server Required                                       │
├──────────────────────────────────────────────────────────┤
│                                                           │
│ The tool "beautifulsoup.find_all" requires the MCP       │
│ server "beautifulsoup" which is not installed.           │
│                                                           │
│ Package: mcp-beautifulsoup                               │
│ Size:    ~5 MB                                           │
│                                                           │
│ Would you like to download and install it now?           │
│                                                           │
│        [Download & Install]     [Skip]                   │
│                                                           │
│ ☑ Remember my choice for this server                     │
└──────────────────────────────────────────────────────────┘
```

---

## MCP Composition

Combine multiple MCP tools to create powerful workflows.

### Example 1: Parse HTML → Extract Tables → Save to Database

```python
# Step 1: Clean HTML
cleaned = mcp.call("beautifulsoup.clean_html", {
    "html": observation.page_html
})

# Step 2: Extract tables
tables = mcp.call("beautifulsoup.extract_tables", {
    "html": cleaned["html"]
})

# Step 3: Save to PostgreSQL
for table in tables:
    mcp.call("postgresql.execute", {
        "sql": "INSERT INTO scraped_data (data) VALUES (%s)",
        "params": [json.dumps(table)]
    })
```

### Example 2: Search Google → Navigate → Parse Article → Summarize

```python
# Step 1: Search
results = mcp.call("google-search.search", {
    "query": "best widgets 2026",
    "num": 5
})

# Step 2: Navigate to top result
mcp.call("playwright.navigate", {
    "url": results[0]["url"]
})

# Step 3: Extract article
article = mcp.call("readability.extract_article", {
    "html": mcp.call("playwright.get_html", {})
})

# Step 4: Summarize
summary = mcp.call("llm.summarize", {
    "text": article["text"],
    "max_length": 200
})
```

### Composition DSL

Define reusable workflows:

```python
class MCPWorkflow:
    def __init__(self, name: str, steps: List[WorkflowStep]):
        self.name = name
        self.steps = steps
    
    async def execute(self, initial_input: Dict) -> Dict:
        """Execute workflow steps sequentially."""
        context = initial_input
        
        for step in self.steps:
            result = await mcp.call(step.tool, step.params(context))
            context[step.output_var] = result
        
        return context

# Define workflow
extract_and_save = MCPWorkflow(
    name="extract_and_save",
    steps=[
        WorkflowStep(
            tool="beautifulsoup.find_all",
            params=lambda ctx: {"html": ctx["html"], "selector": ctx["selector"]},
            output_var="extracted"
        ),
        WorkflowStep(
            tool="cerberus.validate",
            params=lambda ctx: {"data": ctx["extracted"], "schema": ctx["schema"]},
            output_var="validated"
        ),
        WorkflowStep(
            tool="postgresql.execute",
            params=lambda ctx: {"sql": "INSERT INTO items ...", "params": ctx["validated"]},
            output_var="saved"
        )
    ]
)

# Execute
result = await extract_and_save.execute({
    "html": obs.page_html,
    "selector": "div.product",
    "schema": PRODUCT_SCHEMA
})
```

---

## Testing Panel

Test MCP tools manually before using them in agent workflows.

### UI

```
┌─────────────────────────────────────────────────────────────┐
│ MCP Testing Panel                                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Server:  [beautifulsoup ▼]                                  │
│ Tool:    [find_all ▼]                                       │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ Input Parameters:                                     │    │
│ │                                                       │    │
│ │ html:                                                 │    │
│ │ ┌───────────────────────────────────────────────┐    │    │
│ │ │ <div class="item">Item 1</div>                │    │    │
│ │ │ <div class="item">Item 2</div>                │    │    │
│ │ └───────────────────────────────────────────────┘    │    │
│ │                                                       │    │
│ │ selector: [div.item                           ]      │    │
│ │                                                       │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                              │
│                  [Execute Tool]  [Clear]                     │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ Output:                                               │    │
│ │                                                       │    │
│ │ [                                                     │    │
│ │   {"tag": "div", "class": "item", "text": "Item 1"}, │    │
│ │   {"tag": "div", "class": "item", "text": "Item 2"}  │    │
│ │ ]                                                     │    │
│ │                                                       │    │
│ │ Execution time: 12ms                                  │    │
│ │ Status: ✓ Success                                     │    │
│ └──────────────────────────────────────────────────────┘    │
│                                                              │
│                       [Save as Example]                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Full MCP Configuration Example

```json
{
  "mcpServers": {
    "beautifulsoup": {
      "command": "python",
      "args": ["-m", "mcp_beautifulsoup"],
      "enabled": true,
      "autoDownload": true,
      "config": {
        "default_parser": "lxml"
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp-server"],
      "enabled": false,
      "autoDownload": false,
      "config": {
        "browser": "chromium",
        "headless": true
      }
    },
    "postgresql": {
      "command": "python",
      "args": ["-m", "mcp_postgresql"],
      "enabled": false,
      "autoDownload": false,
      "config": {
        "host": "localhost",
        "port": 5432,
        "database": "scraper_db",
        "user": "postgres",
        "password": "${PG_PASSWORD}"
      }
    },
    "google-search": {
      "command": "python",
      "args": ["-m", "mcp_google_search"],
      "enabled": true,
      "autoDownload": true,
      "config": {
        "api_key": "${GOOGLE_API_KEY}",
        "search_engine_id": "${GOOGLE_SE_ID}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./scraped_data"],
      "enabled": true,
      "autoDownload": true
    }
  },
  
  "mcpSettings": {
    "autoDiscoverTools": true,
    "toolTimeout": 30,
    "maxConcurrentCalls": 5,
    "retryFailedCalls": true,
    "cacheToolResults": true,
    "cacheTTL": 3600
  }
}
```

---

**Next:** See [settings.md](./settings.md) for complete dashboard settings.
