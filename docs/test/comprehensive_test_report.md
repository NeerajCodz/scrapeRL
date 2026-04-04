# ScrapeRL Comprehensive Test Report

**Generated:** 2026-04-05 02:34:31  
**Test Duration:** 22.84s  

## Summary

- **Total Tests:** 21
- **Passed:** ✅ 21
- **Failed:** ❌ 0
- **Success Rate:** 100.0%

## Tests by Complexity

### LOW Complexity (7/7 passed)

#### Environment Reset ✅ PASS

**Component:** Scraper  
**Duration:** 0.68s  

**Details:**
```json
{
  "episode_id": "test-001",
  "task_id": "task_001",
  "observation_fields": [
    "episode_id",
    "task_id",
    "step_number",
    "timestamp",
    "elapsed_seconds",
    "current_url",
    "page_title",
    "page_html",
    "page_html_chunked",
    "page_text",
    "page_elements",
    "navigation_history",
    "can_go_back",
    "can_go_forward",
    "task_context",
    "extracted_so_far",
    "extraction_progress",
    "fields_remaining",
    "memory_context",
    "tool_registry_snapshot",
    "available_actions",
    "pending_messages",
    "active_plan",
    "current_plan_step",
    "last_action_error",
    "consecutive_errors",
    "tokens_used",
    "api_calls_made",
    "estimated_cost_usd",
    "system_hints"
  ]
}
```

---

#### Basic Reward Computation ✅ PASS

**Component:** Reward  
**Duration:** 0.00s  

**Details:**
```json
{
  "reward": 1.0870000000000002,
  "accuracy": 0.9,
  "efficiency": 0.98,
  "completeness": 0.33,
  "total": 1.0870000000000002
}
```

---

#### List Plugins ✅ PASS

**Component:** Plugins  
**Duration:** 0.00s  

**Details:**
```json
{
  "total_plugins": 21,
  "categories": [
    "apis",
    "mcps",
    "skills",
    "processors"
  ],
  "installed_count": 12
}
```

---

#### Create Embeddings Service ✅ PASS

**Component:** Embeddings  
**Duration:** 0.08s  

**Details:**
```json
{
  "provider": "google",
  "model": "models/gemini-embedding-2-preview",
  "has_api_key": true
}
```

---

#### Initialize Memory Manager ✅ PASS

**Component:** Memory  
**Duration:** 0.00s  

**Details:**
```json
{
  "initialized": true,
  "short_term_stats": {
    "size": 0,
    "max_size": 100,
    "episode_id": null,
    "keys": [],
    "utilization": 0.0
  },
  "working_stats": {
    "size": 0,
    "capacity": 20,
    "is_full": false,
    "utilization": 0.0,
    "item_ids": []
  },
  "long_term_stats": {
    "initialized": true,
    "using_fallback": true,
    "collection_name": "scraperl_memory",
    "persist_directory": "./data/chroma",
    "document_count": 0,
    "top_k": 10
  }
}
```

---

#### AI Provider Initialization ✅ PASS

**Component:** AI Providers  
**Duration:** 1.22s  

**Details:**
```json
{
  "available_providers": [
    "google",
    "groq",
    "nvidia"
  ],
  "has_nvidia": true,
  "has_groq": true,
  "nvidia_key_present": true,
  "groq_key_present": true
}
```

---

#### List Tasks Endpoint ✅ PASS

**Component:** API  
**Duration:** 0.00s  

**Details:**
```json
{
  "total_tasks": 3,
  "tasks_returned": 3,
  "task_ids": [
    "task_001",
    "task_002",
    "task_003"
  ]
}
```

---

### MID Complexity (7/7 passed)

#### Navigation & Extraction ✅ PASS

**Component:** Scraper  
**Duration:** 0.00s  

**Details:**
```json
{
  "nav_reward": 0.6500000000000001,
  "extract_reward": 1.0893333333333333,
  "extracted_fields": 1,
  "current_url": "https://example.com"
}
```

---

#### Reward with Ground Truth ✅ PASS

**Component:** Reward  
**Duration:** 0.00s  

**Details:**
```json
{
  "reward": 1.346,
  "accuracy": 1.0,
  "ground_truth_match": true,
  "progress_bonus": 0.45
}
```

---

#### Install/Uninstall Plugin ✅ PASS

**Component:** Plugins  
**Duration:** 0.00s  

**Details:**
```json
{
  "test_plugin": "openai-api",
  "install_success": true,
  "uninstall_success": true
}
```

---

#### Generate Single Embedding ✅ PASS

**Component:** Embeddings  
**Duration:** 1.26s  

**Details:**
```json
{
  "embedding_dim": 3072,
  "embedding_type": "float32",
  "text_length": 63,
  "sample_values": [
    -0.014547660015523434,
    0.03705248236656189,
    0.005636218003928661,
    -0.008768558502197266,
    0.011733976192772388
  ]
}
```

---

#### Store & Retrieve Memory ✅ PASS

**Component:** Memory  
**Duration:** 0.00s  

**Details:**
```json
{
  "short_term": "test_value",
  "working": "This is a test thought",
  "shared": {
    "data": "shared_value"
  }
}
```

---

#### NVIDIA Completion ✅ PASS

**Component:** AI Providers  
**Duration:** 10.68s  

**Details:**
```json
{
  "model_used": "llama-3.3-70b",
  "provider_used": "nvidia",
  "content_preview": "4",
  "total_tokens": 50
}
```

---

#### Plugins Endpoint ✅ PASS

**Component:** API  
**Duration:** 0.00s  

**Details:**
```json
{
  "total_plugins": 21,
  "installed": 11,
  "categories": [
    "apis",
    "mcps",
    "skills",
    "processors"
  ]
}
```

---

### HIGH Complexity (7/7 passed)

#### Full Episode Completion ✅ PASS

**Component:** Scraper  
**Duration:** 0.00s  

**Details:**
```json
{
  "total_reward": 6.334,
  "steps_taken": 5,
  "extracted_fields": 3,
  "is_terminal": true,
  "status": "completed"
}
```

---

#### Terminal Reward Calculation ✅ PASS

**Component:** Reward  
**Duration:** 0.00s  

**Details:**
```json
{
  "terminal_reward": 1.26,
  "completeness": 1.0,
  "accuracy": 1.0,
  "efficiency": 0.8,
  "progress_bonus": 0.5
}
```

---

#### Plugin Categories & Core Plugins ✅ PASS

**Component:** Plugins  
**Duration:** 0.00s  

**Details:**
```json
{
  "categories": {
    "apis": 5,
    "mcps": 6,
    "skills": 6,
    "processors": 4
  },
  "core_plugins_installed": [
    "skill-planner",
    "mcp-search",
    "proc-json",
    "skill-extractor",
    "skill-navigator",
    "mcp-browser",
    "skill-verifier",
    "mcp-html"
  ],
  "ai_providers_installed": [
    "google-api",
    "groq-api",
    "nvidia-api"
  ],
  "total_installed": 12
}
```

---

#### Batch Embeddings & Similarity Search ✅ PASS

**Component:** Embeddings  
**Duration:** 6.96s  

**Details:**
```json
{
  "batch_size": 3,
  "embeddings_shape": [
    3,
    3072
  ],
  "top_match_index": 0,
  "top_match_score": 0.872869610786438,
  "similarity_ranking": [
    [
      0,
      0.8729
    ],
    [
      2,
      0.8077
    ]
  ]
}
```

---

#### Long-term Memory & Vector Search ✅ PASS

**Component:** Memory  
**Duration:** 0.00s  

**Details:**
```json
{
  "documents_stored": 3,
  "search_results": 0,
  "using_fallback": true,
  "top_result_score": null
}
```

---

#### Groq Code Generation ✅ PASS

**Component:** AI Providers  
**Duration:** 1.96s  

**Details:**
```json
{
  "model_used": "llama-3.3-70b-versatile",
  "provider_used": "groq",
  "content_preview": "```python\ndef factorial(n):\n    \"\"\"Calculate factorial of n.\"\"\"\n    if n < 0:\n        raise ValueError(\"Factorial is not defined for negative numbers\")\n    elif n == 0 or n == 1:\n        return 1\n    ",
  "has_code": true
}
```

---

#### Episode Lifecycle ✅ PASS

**Component:** API  
**Duration:** 0.00s  

**Details:**
```json
{
  "episode_id": "api-test-001",
  "task_id": "task_001",
  "environments_listed": 1,
  "removed": true
}
```

---

## Component Summary

| Component | Tests | Passed | Failed | Success Rate |
|-----------|-------|--------|--------|-------------|
| AI Providers | 3 | 3 | 0 | 100.0% |
| API | 3 | 3 | 0 | 100.0% |
| Embeddings | 3 | 3 | 0 | 100.0% |
| Memory | 3 | 3 | 0 | 100.0% |
| Plugins | 3 | 3 | 0 | 100.0% |
| Reward | 3 | 3 | 0 | 100.0% |
| Scraper | 3 | 3 | 0 | 100.0% |
