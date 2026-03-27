# 🧠 Unified Memory System

## Table of Contents
1. [Overview](#overview)
2. [Memory Architecture](#memory-architecture)
3. [Memory Layers](#memory-layers)
4. [Memory Operations](#memory-operations)
5. [Implementation Details](#implementation-details)
6. [Configuration](#configuration)
7. [Best Practices](#best-practices)

---

## Overview

The **Unified Memory System** is the most critical upgrade for the WebScraper-OpenEnv agent. It provides persistent, contextual, and hierarchical memory across episodes, enabling the agent to learn from past experiences, maintain reasoning context, and share knowledge across multiple agents.

### Why Memory Matters

Without memory:
- Agents repeat the same mistakes across episodes
- No learning from successful extraction patterns
- Cannot maintain context across long scraping sessions
- Unable to share knowledge between multiple agents
- Limited by context window size

With unified memory:
- ✅ Learn successful extraction strategies
- ✅ Remember failed approaches to avoid repetition
- ✅ Maintain reasoning context across steps
- ✅ Share discoveries across agent instances
- ✅ Overcome context window limitations

---

## Memory Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Unified Memory System                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Short-Term    │  │   Working      │  │   Long-Term      │  │
│  │   Memory       │  │   Memory       │  │    Memory        │  │
│  │  (Episode)     │  │  (Reasoning)   │  │  (Persistent)    │  │
│  └────────┬───────┘  └───────┬────────┘  └────────┬─────────┘  │
│           │                  │                     │            │
│           └──────────────────┼─────────────────────┘            │
│                              │                                  │
│                    ┌─────────▼──────────┐                       │
│                    │   Memory Router    │                       │
│                    │  - Query planner   │                       │
│                    │  - Context builder │                       │
│                    │  - Summarizer      │                       │
│                    └─────────┬──────────┘                       │
│                              │                                  │
│           ┌──────────────────┼──────────────────┐               │
│           │                  │                  │               │
│  ┌────────▼────────┐  ┌──────▼─────────┐  ┌───▼──────────┐    │
│  │  Shared Memory  │  │  Vector Index  │  │  MCP Storage │    │
│  │  (Multi-Agent)  │  │  (FAISS/Qdrant)│  │  (File/DB)   │    │
│  └─────────────────┘  └────────────────┘  └──────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Memory Layers

### 1. 🟢 Short-Term Memory (Per Episode)

**Purpose:** Tracks the current scraping session state.

**Lifecycle:** Exists for one episode, cleared on `reset()`.

**Data Structure:**
```python
class EpisodeMemory(BaseModel):
    episode_id: str
    task_id: str
    visited_urls: List[str]                    # Navigation history
    extracted_data: Dict[str, Any]             # Field → value mappings
    actions_history: List[Action]              # All actions taken
    intermediate_notes: List[str]              # Agent's reasoning notes
    observations: List[Observation]            # All observations received
    page_summaries: Dict[str, str]             # URL → content summary
    extraction_attempts: Dict[str, List[Any]]  # Field → list of attempts
    timestamp_created: datetime
    timestamp_updated: datetime
```

**Use Cases:**
- Track which pages have been visited to avoid cycles
- Remember what data has been extracted
- Maintain action history for debugging
- Store intermediate reasoning

**Example:**
```python
# Agent navigating a multi-page catalog
episode_memory = {
    "visited_urls": [
        "/catalog/page/1",
        "/catalog/page/2",
        "/product/12345"
    ],
    "extracted_data": {
        "product_name": "Widget Pro",
        "price": "$49.99"
    },
    "intermediate_notes": [
        "Price found in span.product-price",
        "Next page link present, continuing pagination"
    ]
}
```

### 2. 🔵 Working Memory (Agent Thinking)

**Purpose:** Temporary reasoning buffer for active decision-making.

**Lifecycle:** Cleared after each action decision, or kept for multi-step reasoning.

**Data Structure:**
```python
class WorkingMemory(BaseModel):
    current_goal: str                          # Active objective
    reasoning_steps: List[str]                 # Chain of thought
    considered_actions: List[Action]           # Actions being evaluated
    scratchpad: Dict[str, Any]                 # Temporary calculations
    active_hypotheses: List[str]               # Predictions to test
    context_window: List[str]                  # Relevant memory chunks
    attention_focus: Optional[str]             # Current DOM element/area of focus
```

**Use Cases:**
- Chain-of-thought reasoning before action selection
- Evaluate multiple action candidates
- Maintain focus during complex extraction
- Store temporary parsing results

**Example:**
```python
working_memory = {
    "current_goal": "Extract product price from listing",
    "reasoning_steps": [
        "Step 1: Search HTML for price indicators ($, €, price)",
        "Step 2: Found 3 candidates: $49.99, $39.99 (strikethrough), $5.99 (shipping)",
        "Step 3: $49.99 is in <span class='product-price'>, most likely correct",
        "Step 4: Extract using selector span.product-price"
    ],
    "considered_actions": [
        Action(action_type="EXTRACT_FIELD", selector="span.price"),
        Action(action_type="EXTRACT_FIELD", selector="span.product-price"),
        Action(action_type="SEARCH_PAGE", query="price.*\\$\\d+")
    ],
    "attention_focus": "div.product-details"
}
```

### 3. 🟡 Long-Term Memory (Persistent)

**Purpose:** Store learned patterns, strategies, and historical data across all episodes.

**Lifecycle:** Persists indefinitely via MCP storage and vector database.

**Data Structure:**
```python
class LongTermMemory(BaseModel):
    # Vector embeddings for semantic search
    embeddings_index: VectorIndex              # FAISS, Qdrant, or Pinecone
    
    # Successful extraction patterns
    learned_patterns: List[ExtractionPattern]  
    
    # Historical performance data
    past_episodes: List[EpisodeSummary]
    
    # Failed attempts (to avoid repetition)
    failed_patterns: List[FailedPattern]
    
    # Domain knowledge
    website_schemas: Dict[str, WebsiteSchema]  # domain → common patterns
    
    # Selector library
    selector_success_rate: Dict[str, float]    # selector → success rate
```

**Extraction Pattern:**
```python
class ExtractionPattern(BaseModel):
    pattern_id: str
    field_name: str                            # e.g., "price"
    selector: str                              # e.g., "span.product-price"
    selector_type: str                         # "css" | "xpath" | "label"
    success_count: int                         # How many times it worked
    failure_count: int                         # How many times it failed
    domains: List[str]                         # Which websites it works on
    confidence: float                          # 0.0 to 1.0
    examples: List[str]                        # Sample extracted values
    created_at: datetime
    last_used: datetime
```

**Use Cases:**
- Retrieve successful selectors for similar tasks
- Avoid repeating failed extraction attempts
- Learn website-specific patterns
- Build a library of proven strategies

**Example Query:**
```python
# Agent needs to extract "price" from a new e-commerce page
similar_patterns = long_term_memory.search(
    query="price extraction e-commerce",
    filters={"field_name": "price", "confidence": ">0.8"},
    limit=5
)

# Returns:
[
    ExtractionPattern(
        selector="span.product-price",
        success_count=42,
        confidence=0.95,
        domains=["shop.example.com", "store.example.org"]
    ),
    ExtractionPattern(
        selector="div.price-box span[itemprop='price']",
        success_count=38,
        confidence=0.92,
        domains=["ecommerce.example.net"]
    ),
    ...
]
```

### 4. 🔴 Shared Memory (Multi-Agent)

**Purpose:** Enable knowledge sharing across multiple agent instances.

**Lifecycle:** Persistent, synchronized across all agents.

**Data Structure:**
```python
class SharedMemory(BaseModel):
    global_knowledge_base: Dict[str, Any]      # Shared facts and patterns
    agent_messages: List[AgentMessage]         # Inter-agent communication
    task_state: Dict[str, TaskState]           # Collaborative task status
    distributed_discoveries: List[Discovery]   # Findings from all agents
    consensus_data: Dict[str, ConsensusValue]  # Voted/validated facts
```

**Use Cases:**
- Multiple agents scraping different sections of a large site
- Collaborative fact verification
- Distributed catalog scraping
- Consensus-based data validation

**Example:**
```python
# Agent A discovers a pattern
agent_a.shared_memory.broadcast(
    AgentMessage(
        sender="agent_a",
        message_type="PATTERN_DISCOVERED",
        data={
            "pattern": "Product SKU always in span.sku-code",
            "confidence": 0.89,
            "domain": "shop.example.com"
        }
    )
)

# Agent B receives and applies the pattern
agent_b_discovers = agent_b.shared_memory.receive_messages(
    message_type="PATTERN_DISCOVERED"
)
# Agent B can now use this selector without rediscovering it
```

---

## Memory Operations

### Core Actions

The memory system exposes the following actions to the agent:

#### 1. WRITE_MEMORY
Store information in the appropriate memory layer.

```python
class WriteMemoryAction(Action):
    action_type: Literal["WRITE_MEMORY"]
    memory_layer: Literal["short_term", "working", "long_term", "shared"]
    key: str
    value: Any
    metadata: Optional[Dict[str, Any]] = None
    ttl: Optional[int] = None  # Time-to-live in seconds (for working memory)
```

**Example:**
```python
# Store a successful extraction pattern
Action(
    action_type="WRITE_MEMORY",
    memory_layer="long_term",
    key="pattern:price:span.product-price",
    value={
        "selector": "span.product-price",
        "field": "price",
        "success_count": 1,
        "domain": "shop.example.com"
    },
    metadata={"task_id": "task_medium", "episode_id": "ep_123"}
)
```

#### 2. READ_MEMORY
Retrieve information from memory.

```python
class ReadMemoryAction(Action):
    action_type: Literal["READ_MEMORY"]
    memory_layer: Literal["short_term", "working", "long_term", "shared"]
    key: Optional[str] = None          # Specific key (exact match)
    query: Optional[str] = None        # Semantic search query
    filters: Optional[Dict] = None     # Metadata filters
    limit: int = 10                    # Max results
```

**Example:**
```python
# Semantic search for price extraction patterns
Action(
    action_type="READ_MEMORY",
    memory_layer="long_term",
    query="how to extract price from e-commerce product page",
    filters={"field_name": "price", "confidence": ">0.7"},
    limit=5
)
```

#### 3. SEARCH_MEMORY
Advanced semantic search across memory layers.

```python
class SearchMemoryAction(Action):
    action_type: Literal["SEARCH_MEMORY"]
    query: str                         # Natural language query
    memory_layers: List[str]           # Which layers to search
    search_mode: Literal["semantic", "keyword", "hybrid"]
    time_range: Optional[TimeRange]    # Filter by recency
    min_relevance: float = 0.5         # Minimum similarity score
```

**Example:**
```python
# Find all successful pagination strategies
Action(
    action_type="SEARCH_MEMORY",
    query="successful pagination next page navigation strategies",
    memory_layers=["long_term", "shared"],
    search_mode="semantic",
    min_relevance=0.7
)
```

#### 4. SUMMARIZE_MEMORY
Compress and summarize memory to manage context window.

```python
class SummarizeMemoryAction(Action):
    action_type: Literal["SUMMARIZE_MEMORY"]
    memory_layer: str
    summarization_strategy: Literal["importance", "recency", "relevance"]
    target_size: int                   # Target summary size in tokens
    preserve_keys: List[str]           # Never summarize these
```

#### 5. PRUNE_MEMORY
Remove low-value or outdated memories.

```python
class PruneMemoryAction(Action):
    action_type: Literal["PRUNE_MEMORY"]
    memory_layer: str
    pruning_strategy: Literal["lru", "low_confidence", "old_age"]
    threshold: float                   # Confidence/age threshold
```

---

## Implementation Details

### Vector Database Integration

**Supported Backends:**
- **FAISS** (default, local, no external dependencies)
- **Qdrant** (distributed, production-ready)
- **Pinecone** (managed, cloud-based)
- **Weaviate** (open-source, GraphQL API)

**Configuration:**
```python
class VectorDBConfig(BaseModel):
    provider: Literal["faiss", "qdrant", "pinecone", "weaviate"]
    embedding_model: str = "text-embedding-3-small"  # OpenAI
    dimension: int = 1536
    similarity_metric: Literal["cosine", "euclidean", "dot_product"] = "cosine"
    index_type: str = "IVF"            # FAISS-specific
    connection_params: Dict[str, Any]  # Provider-specific
```

**Embedding Pipeline:**
```python
class MemoryEmbedder:
    def embed_pattern(self, pattern: ExtractionPattern) -> np.ndarray:
        """Convert extraction pattern to embedding."""
        text = f"""
        Field: {pattern.field_name}
        Selector: {pattern.selector}
        Type: {pattern.selector_type}
        Context: {' '.join(pattern.examples[:3])}
        """
        return self.embedding_model.encode(text)
    
    def embed_query(self, query: str) -> np.ndarray:
        """Convert search query to embedding."""
        return self.embedding_model.encode(query)
```

### MCP Storage Integration

**Storage Backends:**
- **File System MCP** (local JSON/SQLite files)
- **PostgreSQL MCP** (relational storage)
- **MongoDB MCP** (document storage)
- **Redis MCP** (fast cache + pub/sub for shared memory)

**Example MCP Configuration:**
```json
{
  "mcpServers": {
    "memory-storage": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./memory_data"],
      "enabled": true,
      "autoDownload": false
    },
    "memory-cache": {
      "command": "redis-mcp-server",
      "args": ["--host", "localhost", "--port", "6379"],
      "enabled": true,
      "autoDownload": true
    }
  }
}
```

### Memory Router

The **Memory Router** intelligently decides which memory layer to query based on the request:

```python
class MemoryRouter:
    def route_query(self, query: str, context: Dict) -> List[str]:
        """Determine which memory layers to search."""
        layers = []
        
        # Recent action history → short-term
        if "last few" in query or "current episode" in query:
            layers.append("short_term")
        
        # Active reasoning → working
        if "consider" in query or "evaluate" in query:
            layers.append("working")
        
        # Historical patterns → long-term
        if "similar" in query or "previously" in query or "learned" in query:
            layers.append("long_term")
        
        # Other agents' discoveries → shared
        if "other agents" in query or "consensus" in query:
            layers.append("shared")
        
        return layers if layers else ["long_term"]  # Default
```

### Context Window Optimization

**Problem:** LLMs have limited context windows. Memory must be compressed.

**Solutions:**

1. **Hierarchical Summarization:**
```python
class MemorySummarizer:
    def summarize_episode(self, episode_memory: EpisodeMemory) -> str:
        """Compress episode into key points."""
        summary = f"Episode {episode_memory.episode_id} ({episode_memory.task_id}):\n"
        summary += f"- Visited {len(episode_memory.visited_urls)} pages\n"
        summary += f"- Extracted {len(episode_memory.extracted_data)} fields\n"
        summary += f"- {len(episode_memory.actions_history)} actions taken\n"
        
        # Highlight key discoveries
        if episode_memory.intermediate_notes:
            summary += f"\nKey findings:\n"
            for note in episode_memory.intermediate_notes[-3:]:  # Last 3 notes
                summary += f"  • {note}\n"
        
        return summary
```

2. **Importance Scoring:**
```python
class MemoryImportanceScorer:
    def score(self, memory_item: Any) -> float:
        """Rate importance of memory (0.0 to 1.0)."""
        score = 0.0
        
        # Recency bonus
        age_days = (datetime.now() - memory_item.created_at).days
        score += max(0, 1.0 - age_days / 30) * 0.3
        
        # Success rate bonus
        if hasattr(memory_item, 'success_count'):
            score += memory_item.confidence * 0.4
        
        # Usage frequency bonus
        if hasattr(memory_item, 'last_used'):
            days_since_use = (datetime.now() - memory_item.last_used).days
            score += max(0, 1.0 - days_since_use / 7) * 0.3
        
        return min(score, 1.0)
```

3. **Automatic Pruning:**
```python
class MemoryPruner:
    def prune_low_value(self, memory_store: Dict, threshold: float = 0.3):
        """Remove memories below importance threshold."""
        scorer = MemoryImportanceScorer()
        to_remove = []
        
        for key, item in memory_store.items():
            if scorer.score(item) < threshold:
                to_remove.append(key)
        
        for key in to_remove:
            del memory_store[key]
        
        return len(to_remove)
```

---

## Configuration

### Settings Panel

**Memory Settings Tab:**
```python
class MemorySettings(BaseModel):
    # Enable/disable layers
    enable_short_term: bool = True
    enable_working: bool = True
    enable_long_term: bool = True
    enable_shared: bool = False          # Off by default (multi-agent)
    
    # Size limits
    max_episode_memory_mb: int = 10
    max_working_memory_items: int = 50
    max_long_term_patterns: int = 10000
    
    # Vector DB settings
    vector_db_provider: str = "faiss"
    embedding_model: str = "text-embedding-3-small"
    
    # MCP storage settings
    storage_backend: str = "filesystem"
    storage_path: str = "./memory_data"
    
    # Pruning settings
    auto_prune: bool = True
    prune_threshold: float = 0.3
    prune_interval_hours: int = 24
    
    # Context window optimization
    auto_summarize: bool = True
    max_context_tokens: int = 4000
```

**UI Example:**
```
┌─────────────────────────────────────────────────────────────┐
│ Memory Settings                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ☑ Enable Short-Term Memory (Episode)                        │
│ ☑ Enable Working Memory (Reasoning)                         │
│ ☑ Enable Long-Term Memory (Persistent)                      │
│ ☐ Enable Shared Memory (Multi-Agent)                        │
│                                                              │
│ Memory Size Limits:                                          │
│   Short-Term: [10] MB per episode                           │
│   Working:    [50] items max                                │
│   Long-Term:  [10000] patterns max                          │
│                                                              │
│ Vector Database:                                             │
│   Provider:   [FAISS ▼]                                     │
│   Embedding:  [text-embedding-3-small ▼]                    │
│                                                              │
│ Storage Backend:                                             │
│   Type:       [Filesystem ▼]                                │
│   Path:       [./memory_data          ] [Browse]            │
│                                                              │
│ Auto-Pruning:                                                │
│   ☑ Enabled                                                  │
│   Threshold:  [0.3] (0.0 = keep all, 1.0 = keep only best) │
│   Interval:   [24] hours                                    │
│                                                              │
│              [Save Settings]  [Reset to Defaults]           │
└─────────────────────────────────────────────────────────────┘
```

---

## Best Practices

### 1. Memory Hygiene
✅ **Do:**
- Summarize episode memory before storing in long-term
- Prune low-confidence patterns regularly
- Validate patterns before adding to long-term memory
- Tag memories with metadata (task_id, domain, confidence)

❌ **Don't:**
- Store raw HTML in long-term memory (use summaries)
- Keep failed patterns without analysis
- Allow unbounded memory growth
- Store sensitive data without encryption

### 2. Query Optimization
✅ **Do:**
- Use semantic search for conceptual queries ("how to extract price")
- Use exact key lookup for known patterns
- Apply filters to narrow search space
- Limit results to top-K most relevant

❌ **Don't:**
- Search all layers for every query (route intelligently)
- Ignore relevance scores (filter low scores)
- Retrieve full objects when summaries suffice

### 3. Context Window Management
✅ **Do:**
- Prioritize recent and high-confidence memories
- Summarize old episodes aggressively
- Use hierarchical memory retrieval (summary → details on demand)
- Monitor token usage and trigger summarization proactively

❌ **Don't:**
- Include entire memory in every agent call
- Ignore context window limits
- Retrieve memories without relevance ranking

### 4. Multi-Agent Coordination
✅ **Do:**
- Broadcast significant discoveries to shared memory
- Implement consensus mechanisms for conflicting data
- Use message queues for asynchronous updates
- Version shared knowledge to handle conflicts

❌ **Don't:**
- Allow race conditions on shared writes
- Broadcast every minor action (create noise)
- Trust shared data without validation

---

## Performance Metrics

Track these metrics to evaluate memory system effectiveness:

```python
class MemoryMetrics(BaseModel):
    # Retrieval performance
    avg_retrieval_time_ms: float
    cache_hit_rate: float
    
    # Effectiveness
    pattern_reuse_rate: float          # % of times learned patterns helped
    memory_assisted_success_rate: float # Success with vs without memory
    
    # Efficiency
    memory_size_mb: float
    pruned_items_count: int
    summarization_ratio: float         # Compressed size / original size
    
    # Quality
    avg_pattern_confidence: float
    false_positive_rate: float         # Patterns that failed when reused
```

---

## Example Usage

### Full Episode with Memory

```python
# Initialize environment with memory
env = WebScraperEnv(memory_config=MemorySettings())

# Reset episode
obs = env.reset(task_id="task_medium", seed=42)

# Agent checks long-term memory for similar tasks
memory_query = Action(
    action_type="SEARCH_MEMORY",
    query=f"successful extraction patterns for {obs.task_description}",
    memory_layers=["long_term"],
    search_mode="semantic",
    limit=5
)
similar_patterns = env.step(memory_query)

# Agent reasons using working memory
working_memory = {
    "current_goal": "Extract product price",
    "reasoning_steps": [
        f"Retrieved {len(similar_patterns)} similar patterns",
        f"Top pattern: {similar_patterns[0].selector} (confidence: {similar_patterns[0].confidence})",
        "Will try this selector first"
    ],
    "considered_actions": [...]
}

# Agent extracts using learned pattern
extract_action = Action(
    action_type="EXTRACT_FIELD",
    target_field="price",
    selector=similar_patterns[0].selector
)
obs, reward, done, info = env.step(extract_action)

# If successful, reinforce the pattern
if reward.value > 0:
    env.step(Action(
        action_type="WRITE_MEMORY",
        memory_layer="long_term",
        key=f"pattern:price:{similar_patterns[0].selector}",
        value={
            **similar_patterns[0].dict(),
            "success_count": similar_patterns[0].success_count + 1,
            "last_used": datetime.now()
        }
    ))

# Store episode summary
if done:
    env.step(Action(
        action_type="WRITE_MEMORY",
        memory_layer="long_term",
        key=f"episode:{obs.episode_id}",
        value=env.summarize_episode()
    ))
```

---

## Future Enhancements

- **Active Learning:** Agent can request human labeling for ambiguous patterns
- **Federated Memory:** Share memory across organizations without revealing raw data
- **Memory Replay:** Train on stored episodes for offline RL
- **Causal Memory:** Track cause-effect relationships between actions and outcomes
- **Memory Debugging:** Visualize which memories influenced each decision

---

**Next:** See [api.md](./api.md) for multi-model API integration.
