# 🔍 Search Engine Layer

## Table of Contents
1. [Overview](#overview)
2. [Supported Search Engines](#supported-search-engines)
3. [Query Optimization](#query-optimization)
4. [Multi-Hop Search](#multi-hop-search)
5. [Source Credibility Scoring](#source-credibility-scoring)
6. [Result Ranking](#result-ranking)
7. [Caching & Deduplication](#caching--deduplication)
8. [Configuration](#configuration)

---

## Overview

The **Search Engine Layer** enables agents to search the web intelligently, optimize queries, perform multi-hop searches, and evaluate source credibility.

### Capabilities

- ✅ Multiple search engine APIs (Google, Bing, Brave, DuckDuckGo, Perplexity)
- ✅ Query optimization and rewriting
- ✅ Multi-hop search (search → refine → search again)
- ✅ Source credibility scoring
- ✅ Result ranking and filtering
- ✅ Caching and deduplication
- ✅ Cost tracking

---

## Supported Search Engines

### 1. Google Search API

**Pros:**
- Most comprehensive results
- High quality
- Advanced operators support

**Cons:**
- Requires API key + Custom Search Engine ID
- Costs $5 per 1000 queries after free tier

**Configuration:**
```python
{
    "google": {
        "api_key": "YOUR_GOOGLE_API_KEY",
        "search_engine_id": "YOUR_CSE_ID",
        "region": "us",
        "safe_search": True,
        "num_results": 10
    }
}
```

**Usage:**
```python
results = search_engine.search(
    query="product reviews for Widget Pro",
    engine="google",
    num_results=10
)
```

### 2. Bing Search API

**Pros:**
- Good quality results
- Competitive pricing ($7 per 1000 queries)
- News search included

**Cons:**
- Smaller index than Google
- Less advanced operators

**Configuration:**
```python
{
    "bing": {
        "api_key": "YOUR_BING_API_KEY",
        "market": "en-US",
        "safe_search": "Moderate",
        "freshness": None  # "Day", "Week", "Month"
    }
}
```

### 3. Brave Search API

**Pros:**
- Privacy-focused
- Independent index
- Good pricing ($5 per 1000 queries)
- No tracking

**Cons:**
- Smaller index
- Newer service

**Configuration:**
```python
{
    "brave": {
        "api_key": "YOUR_BRAVE_API_KEY",
        "country": "US",
        "safe_search": "moderate",
        "freshness": None
    }
}
```

### 4. DuckDuckGo (Free, No API Key)

**Pros:**
- Completely free
- No API key required
- Privacy-focused
- Good for testing

**Cons:**
- Rate limited
- Less control over results
- Smaller result set

**Usage:**
```python
from duckduckgo_search import DDGS

results = DDGS().text(
    keywords="web scraping tools",
    max_results=10
)
```

### 5. Perplexity AI (AI-Powered Search)

**Pros:**
- Returns AI-summarized answers with citations
- Real-time web access
- Conversational queries

**Cons:**
- More expensive
- Designed for Q&A, not traditional search

**Configuration:**
```python
{
    "perplexity": {
        "api_key": "YOUR_PERPLEXITY_API_KEY",
        "model": "pplx-70b-online",
        "include_citations": True
    }
}
```

---

## Query Optimization

### Query Rewriter

```python
class QueryOptimizer:
    """Optimize search queries for better results."""
    
    def optimize(self, query: str, context: Dict = None) -> str:
        """Optimize a search query."""
        optimized = query
        
        # 1. Expand abbreviations
        optimized = self.expand_abbreviations(optimized)
        
        # 2. Add context keywords
        if context:
            optimized = self.add_context(optimized, context)
        
        # 3. Remove stop words (optional)
        # optimized = self.remove_stop_words(optimized)
        
        # 4. Add search operators
        optimized = self.add_operators(optimized)
        
        return optimized
    
    def expand_abbreviations(self, query: str) -> str:
        """Expand common abbreviations."""
        expansions = {
            "AI": "artificial intelligence",
            "ML": "machine learning",
            "API": "application programming interface",
            "UI": "user interface",
            "UX": "user experience",
        }
        
        for abbr, full in expansions.items():
            # Only expand if abbreviation stands alone
            query = re.sub(rf'\b{abbr}\b', full, query)
        
        return query
    
    def add_context(self, query: str, context: Dict) -> str:
        """Add contextual keywords."""
        if context.get('domain'):
            query = f"{query} site:{context['domain']}"
        
        if context.get('year'):
            query = f"{query} {context['year']}"
        
        if context.get('location'):
            query = f"{query} {context['location']}"
        
        return query
    
    def add_operators(self, query: str) -> str:
        """Add search operators for precision."""
        # If query has multiple important terms, wrap in quotes
        important_terms = self.extract_important_terms(query)
        
        if len(important_terms) > 1:
            # Exact phrase search for key terms
            for term in important_terms:
                if len(term.split()) > 1:
                    query = query.replace(term, f'"{term}"')
        
        return query
```

### Query Expansion

```python
class QueryExpander:
    """Expand queries with synonyms and related terms."""
    
    def expand(self, query: str) -> List[str]:
        """Generate query variations."""
        variations = [query]
        
        # 1. Synonym replacement
        synonyms = self.get_synonyms(query)
        for synonym_set in synonyms:
            for term, synonym in synonym_set:
                varied = query.replace(term, synonym)
                variations.append(varied)
        
        # 2. Add modifiers
        modifiers = ["best", "top", "review", "comparison", "guide"]
        for modifier in modifiers:
            variations.append(f"{modifier} {query}")
        
        # 3. Question forms
        variations.extend([
            f"what is {query}",
            f"how to {query}",
            f"why {query}"
        ])
        
        return variations[:5]  # Limit to top 5
```

### Bad Query Detection

```python
def is_bad_query(query: str) -> bool:
    """Detect poorly formed queries."""
    # Too short
    if len(query.split()) < 2:
        return True
    
    # All stop words
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be'}
    words = set(query.lower().split())
    if words.issubset(stop_words):
        return True
    
    # No meaningful content
    if not re.search(r'[a-zA-Z]{3,}', query):
        return True
    
    return False
```

---

## Multi-Hop Search

### Multi-Hop Strategy

```python
class MultiHopSearch:
    """Perform multi-hop search with refinement."""
    
    async def search_multi_hop(
        self,
        initial_query: str,
        max_hops: int = 3
    ) -> MultiHopResult:
        """Perform multi-hop search."""
        results_by_hop = []
        current_query = initial_query
        
        for hop in range(max_hops):
            # Execute search
            results = await self.search(current_query)
            results_by_hop.append(results)
            
            # Analyze results
            analysis = self.analyze_results(results)
            
            # Check if we found what we need
            if analysis.is_satisfactory:
                break
            
            # Refine query for next hop
            current_query = self.refine_query(
                current_query,
                results,
                analysis
            )
        
        return MultiHopResult(
            hops=results_by_hop,
            final_query=current_query,
            best_results=self.rank_all_results(results_by_hop)
        )
    
    def refine_query(
        self,
        original_query: str,
        results: List[SearchResult],
        analysis: ResultAnalysis
    ) -> str:
        """Refine query based on previous results."""
        # Extract new keywords from top results
        new_keywords = self.extract_keywords_from_results(results[:3])
        
        # If results were too broad, add specificity
        if analysis.too_broad:
            specific_terms = [kw for kw in new_keywords if len(kw.split()) > 1]
            if specific_terms:
                return f"{original_query} {specific_terms[0]}"
        
        # If results were off-topic, add negative keywords
        if analysis.off_topic_terms:
            negative = ' '.join(f"-{term}" for term in analysis.off_topic_terms)
            return f"{original_query} {negative}"
        
        # If no results, try synonyms
        if analysis.no_results:
            return self.query_expander.expand(original_query)[0]
        
        return original_query
```

### Example Multi-Hop Flow

```python
# Hop 1: Initial broad search
query_1 = "best web scraping tools"
results_1 = search(query_1)
# Results: General articles about scraping tools

# Hop 2: Refine to specific use case
query_2 = "best web scraping tools for e-commerce Python"
results_2 = search(query_2)
# Results: More specific, Python-focused

# Hop 3: Add recent constraint
query_3 = "best web scraping tools for e-commerce Python 2026"
results_3 = search(query_3)
# Results: Latest tools with recent reviews
```

---

## Source Credibility Scoring

### Credibility Scorer

```python
class SourceCredibilityScorer:
    """Score the credibility of search result sources."""
    
    def score(self, url: str, domain: str, result: SearchResult) -> float:
        """Calculate credibility score (0.0 to 1.0)."""
        score = 0.5  # Base score
        
        # 1. Domain reputation
        score += self.domain_reputation_score(domain) * 0.3
        
        # 2. Domain age
        score += self.domain_age_score(domain) * 0.1
        
        # 3. HTTPS
        if url.startswith('https://'):
            score += 0.05
        
        # 4. TLD credibility
        score += self.tld_score(domain) * 0.1
        
        # 5. Presence in result snippet
        score += self.snippet_quality_score(result.snippet) * 0.15
        
        # 6. Backlinks (if available)
        score += self.backlink_score(domain) * 0.2
        
        # 7. Freshness
        score += self.freshness_score(result.date_published) * 0.1
        
        return min(max(score, 0.0), 1.0)
    
    def domain_reputation_score(self, domain: str) -> float:
        """Score based on known domain reputation."""
        # Trusted domains
        trusted = {
            'wikipedia.org': 1.0,
            'github.com': 0.95,
            'stackoverflow.com': 0.95,
            'nytimes.com': 0.9,
            'bbc.com': 0.9,
            'reuters.com': 0.9,
            'arxiv.org': 0.95,
            'nature.com': 0.95,
            'sciencedirect.com': 0.9,
        }
        
        # Known spammy/low-quality domains
        untrusted = {
            'contentvilla.com': 0.1,
            'ehow.com': 0.3,
        }
        
        if domain in trusted:
            return trusted[domain]
        
        if domain in untrusted:
            return untrusted[domain]
        
        # Medium trust for unknown domains
        return 0.5
    
    def tld_score(self, domain: str) -> float:
        """Score based on top-level domain."""
        tld = domain.split('.')[-1]
        
        tld_scores = {
            'edu': 0.9,   # Educational institutions
            'gov': 0.95,  # Government
            'org': 0.8,   # Organizations
            'com': 0.6,   # Commercial (neutral)
            'net': 0.6,
            'io': 0.6,
            'info': 0.4,  # Often spammy
            'xyz': 0.3,   # Cheap, often spam
        }
        
        return tld_scores.get(tld, 0.5)
    
    def snippet_quality_score(self, snippet: str) -> float:
        """Score snippet quality."""
        score = 0.5
        
        # Penalize clickbait patterns
        clickbait_patterns = [
            r'you won\'t believe',
            r'shocking',
            r'one weird trick',
            r'\d+ reasons why',
        ]
        
        for pattern in clickbait_patterns:
            if re.search(pattern, snippet, re.I):
                score -= 0.2
        
        # Reward factual language
        if re.search(r'according to|research|study|data|analysis', snippet, re.I):
            score += 0.2
        
        return max(0.0, score)
    
    def freshness_score(self, date_published: Optional[datetime]) -> float:
        """Score based on content freshness."""
        if not date_published:
            return 0.3  # Unknown date
        
        age_days = (datetime.now() - date_published).days
        
        # Decay function: Fresh content scores higher
        if age_days < 30:
            return 1.0
        elif age_days < 90:
            return 0.8
        elif age_days < 365:
            return 0.6
        elif age_days < 730:
            return 0.4
        else:
            return 0.2
```

### Domain Blacklist

```python
DOMAIN_BLACKLIST = [
    'contentvilla.com',
    'pastebin.com',  # Often scraped/duplicated content
    'scam-detector.com',
    'pinterest.com',  # Image aggregator, not original content
    # Add more as needed
]

def is_blacklisted(url: str) -> bool:
    """Check if URL is blacklisted."""
    domain = urlparse(url).netloc
    return any(blocked in domain for blocked in DOMAIN_BLACKLIST)
```

---

## Result Ranking

### Ranking Algorithm

```python
class ResultRanker:
    """Rank search results by relevance and quality."""
    
    def rank(
        self,
        results: List[SearchResult],
        query: str,
        context: Dict = None
    ) -> List[RankedResult]:
        """Rank results by multiple factors."""
        ranked = []
        
        for result in results:
            score = self.calculate_score(result, query, context)
            ranked.append(RankedResult(
                result=result,
                score=score
            ))
        
        # Sort by score (highest first)
        ranked.sort(key=lambda x: x.score, reverse=True)
        
        return ranked
    
    def calculate_score(
        self,
        result: SearchResult,
        query: str,
        context: Dict
    ) -> float:
        """Calculate ranking score."""
        score = 0.0
        
        # 1. Credibility (40%)
        credibility = self.credibility_scorer.score(
            result.url,
            result.domain,
            result
        )
        score += credibility * 0.4
        
        # 2. Relevance (35%)
        relevance = self.calculate_relevance(result, query)
        score += relevance * 0.35
        
        # 3. Freshness (10%)
        freshness = self.credibility_scorer.freshness_score(result.date_published)
        score += freshness * 0.1
        
        # 4. Engagement signals (10%)
        # (If available: click-through rate, dwell time, etc.)
        score += result.engagement_score * 0.1
        
        # 5. Diversity bonus (5%)
        # Prefer results from different domains
        if context and context.get('seen_domains'):
            if result.domain not in context['seen_domains']:
                score += 0.05
        
        return score
    
    def calculate_relevance(self, result: SearchResult, query: str) -> float:
        """Calculate query-result relevance."""
        # Simple keyword matching (can be enhanced with embeddings)
        query_terms = set(query.lower().split())
        
        # Check title
        title_terms = set(result.title.lower().split())
        title_overlap = len(query_terms & title_terms) / len(query_terms)
        
        # Check snippet
        snippet_terms = set(result.snippet.lower().split())
        snippet_overlap = len(query_terms & snippet_terms) / len(query_terms)
        
        # Weighted average
        relevance = 0.6 * title_overlap + 0.4 * snippet_overlap
        
        return relevance
```

---

## Caching & Deduplication

### Search Result Cache

```python
class SearchCache:
    """Cache search results to reduce API calls."""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, query: str, engine: str) -> Optional[List[SearchResult]]:
        """Get cached results."""
        key = self.make_key(query, engine)
        
        if key in self.cache:
            cached, timestamp = self.cache[key]
            
            # Check if still valid
            age = (datetime.now() - timestamp).total_seconds()
            if age < self.ttl:
                return cached
            else:
                # Expired, remove
                del self.cache[key]
        
        return None
    
    def set(self, query: str, engine: str, results: List[SearchResult]):
        """Cache results."""
        key = self.make_key(query, engine)
        self.cache[key] = (results, datetime.now())
    
    def make_key(self, query: str, engine: str) -> str:
        """Generate cache key."""
        normalized = query.lower().strip()
        return f"{engine}:{normalized}"
```

### Result Deduplication

```python
class ResultDeduplicator:
    """Remove duplicate results across multiple searches."""
    
    def deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicates."""
        seen_urls = set()
        seen_titles = set()
        unique = []
        
        for result in results:
            # Normalize URL (remove query params, fragments)
            normalized_url = self.normalize_url(result.url)
            
            # Normalize title
            normalized_title = result.title.lower().strip()
            
            # Check if we've seen this result
            if normalized_url in seen_urls:
                continue
            
            # Check for near-duplicate titles
            if self.is_near_duplicate_title(normalized_title, seen_titles):
                continue
            
            # Add to unique set
            unique.append(result)
            seen_urls.add(normalized_url)
            seen_titles.add(normalized_title)
        
        return unique
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        parsed = urlparse(url)
        # Remove query params and fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        # Remove trailing slash
        return normalized.rstrip('/')
    
    def is_near_duplicate_title(self, title: str, seen_titles: Set[str]) -> bool:
        """Check if title is near-duplicate of seen titles."""
        from difflib import SequenceMatcher
        
        for seen in seen_titles:
            similarity = SequenceMatcher(None, title, seen).ratio()
            if similarity > 0.85:  # 85% similar
                return True
        
        return False
```

---

## Configuration

### Search Engine Settings

```typescript
interface SearchEngineConfig {
  default: 'google' | 'bing' | 'brave' | 'duckduckgo' | 'perplexity';
  
  providers: {
    google?: GoogleConfig;
    bing?: BingConfig;
    brave?: BraveConfig;
    duckduckgo?: DuckDuckGoConfig;
    perplexity?: PerplexityConfig;
  };
  
  // Global settings
  maxResults: number;              // Default: 10
  timeout: number;                 // Seconds
  cacheResults: boolean;           // Default: true
  cacheTTL: number;                // Seconds
  
  // Query optimization
  optimizeQueries: boolean;        // Default: true
  expandQueries: boolean;          // Default: false
  
  // Multi-hop
  enableMultiHop: boolean;         // Default: false
  maxHops: number;                 // Default: 3
  
  // Filtering
  filterByCredibility: boolean;    // Default: true
  minCredibilityScore: number;     // Default: 0.4
  blacklistedDomains: string[];
  
  // Cost tracking
  trackCosts: boolean;             // Default: true
  dailyQueryLimit: number;         // Default: 1000
}
```

### Usage Example

```python
# Initialize search engine
search = SearchEngine(config)

# Simple search
results = await search.search(
    query="best Python web scraping libraries",
    engine="google",
    num_results=10
)

# Optimized search
results = await search.search_optimized(
    query="web scraping",
    context={"domain": "python.org", "year": 2026},
    optimize=True,
    filter_credibility=True
)

# Multi-hop search
multi_hop_results = await search.search_multi_hop(
    initial_query="web scraping tools",
    max_hops=3
)

# Get ranked results
ranked = search.rank_results(
    results,
    query="web scraping tools",
    context={"seen_domains": ["github.com"]}
)
```

---

**Next:** See [agents.md](./agents.md) for agent architecture.
