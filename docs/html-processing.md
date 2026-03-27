# 🌐 HTML Processing Engine

## Table of Contents
1. [Overview](#overview)
2. [Semantic Understanding](#semantic-understanding)
3. [Content Classification](#content-classification)
4. [Smart Extraction](#smart-extraction)
5. [Adaptive Chunking](#adaptive-chunking)
6. [Batch Processing](#batch-processing)
7. [Diff-Based Updates](#diff-based-updates)
8. [Schema Detection](#schema-detection)

---

## Overview

The **HTML Processing Engine** provides advanced capabilities for understanding, parsing, and extracting data from complex web pages.

### Challenges

Modern web pages are challenging:
- **Size:** 1MB+ of HTML
- **Complexity:** Nested divs, dynamic IDs, inline styles
- **Noise:** Ads, tracking scripts, navigation repeated on every page
- **Inconsistency:** Same site uses different structures across pages
- **Obfuscation:** Anti-scraping measures (randomized classes, etc.)

### Solution

Our engine provides:
- ✅ **Semantic understanding** of page structure
- ✅ **Content classification** (main content vs noise)
- ✅ **Smart extraction** with pattern recognition
- ✅ **Adaptive chunking** for large pages
- ✅ **Batch processing** with deduplication
- ✅ **Diff-based updates** for paginated content

---

## Semantic Understanding

### Architecture

```python
class SemanticHTMLAnalyzer:
    """Understands page structure at a semantic level."""
    
    def analyze(self, html: str) -> SemanticStructure:
        """Analyze HTML and identify semantic regions."""
        soup = BeautifulSoup(html, 'lxml')
        
        structure = SemanticStructure()
        structure.header = self.detect_header(soup)
        structure.navigation = self.detect_navigation(soup)
        structure.main_content = self.detect_main_content(soup)
        structure.sidebar = self.detect_sidebar(soup)
        structure.footer = self.detect_footer(soup)
        structure.ads = self.detect_ads(soup)
        structure.forms = self.detect_forms(soup)
        structure.tables = self.detect_tables(soup)
        structure.lists = self.detect_lists(soup)
        structure.product_cards = self.detect_product_cards(soup)
        
        return structure
```

### Semantic Regions

#### 1. Header Detection

```python
def detect_header(self, soup: BeautifulSoup) -> Optional[Tag]:
    """Detect page header."""
    # Try semantic tags first
    header = soup.find('header')
    if header:
        return header
    
    # Try common patterns
    candidates = soup.find_all(['div', 'section'], class_=re.compile(r'header|top|banner', re.I))
    if candidates:
        # Pick the topmost element
        return min(candidates, key=lambda el: self.get_vertical_position(el))
    
    # Fallback: First div with logo + navigation
    for div in soup.find_all('div'):
        has_logo = div.find(['img', 'svg'], class_=re.compile(r'logo', re.I))
        has_nav = div.find(['nav', 'ul'], class_=re.compile(r'menu|nav', re.I))
        if has_logo and has_nav:
            return div
    
    return None
```

#### 2. Main Content Detection

```python
def detect_main_content(self, soup: BeautifulSoup) -> Optional[Tag]:
    """Detect main content area (most important for extraction)."""
    # Try semantic tags
    main = soup.find('main')
    if main:
        return main
    
    article = soup.find('article')
    if article:
        return article
    
    # Content scoring approach
    candidates = soup.find_all(['div', 'section'])
    scored = []
    
    for candidate in candidates:
        score = 0
        
        # More text = higher score
        text_length = len(candidate.get_text(strip=True))
        score += text_length * 0.1
        
        # Has article/main role
        if candidate.get('role') in ['main', 'article']:
            score += 100
        
        # Common content class names
        if candidate.get('class'):
            classes = ' '.join(candidate.get('class'))
            if re.search(r'content|main|article|post|product', classes, re.I):
                score += 50
        
        # Penalize if contains nav/aside
        if candidate.find(['nav', 'aside']):
            score -= 30
        
        scored.append((candidate, score))
    
    if scored:
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]
    
    return None
```

#### 3. Product Card Detection

```python
def detect_product_cards(self, soup: BeautifulSoup) -> List[Tag]:
    """Detect product cards in e-commerce listings."""
    cards = []
    
    # Pattern 1: Schema.org markup
    cards.extend(soup.find_all(itemtype=re.compile(r'schema.org/Product')))
    
    # Pattern 2: Common class patterns
    class_patterns = [
        r'product[-_]card',
        r'product[-_]item',
        r'product[-_]box',
        r'item[-_]card',
        r'listing[-_]item'
    ]
    
    for pattern in class_patterns:
        cards.extend(soup.find_all(class_=re.compile(pattern, re.I)))
    
    # Pattern 3: Structural detection
    # Look for repeated elements with image + title + price
    candidates = soup.find_all(['div', 'article', 'li'])
    
    for candidate in candidates:
        has_image = candidate.find(['img'])
        has_title = candidate.find(['h1', 'h2', 'h3', 'h4'], class_=re.compile(r'title|name', re.I))
        has_price = candidate.find(class_=re.compile(r'price', re.I))
        
        if has_image and has_title and has_price:
            cards.append(candidate)
    
    # Deduplicate
    return list(set(cards))
```

---

## Content Classification

### Classifier

```python
class ContentClassifier:
    """Classify HTML elements by type."""
    
    CATEGORIES = [
        'navigation',
        'header',
        'footer',
        'sidebar',
        'main_content',
        'advertisement',
        'product_listing',
        'product_detail',
        'form',
        'table',
        'pagination',
        'breadcrumb',
        'comment_section',
        'related_items'
    ]
    
    def classify_element(self, element: Tag) -> str:
        """Classify a single element."""
        features = self.extract_features(element)
        return self.model.predict(features)
    
    def extract_features(self, element: Tag) -> Dict:
        """Extract features for classification."""
        return {
            'tag_name': element.name,
            'class_names': element.get('class', []),
            'id': element.get('id', ''),
            'role': element.get('role', ''),
            'text_length': len(element.get_text(strip=True)),
            'link_density': self.calculate_link_density(element),
            'has_images': bool(element.find('img')),
            'has_forms': bool(element.find('form')),
            'position': self.get_vertical_position(element),
            'parent_classes': element.parent.get('class', []) if element.parent else [],
            'children_count': len(element.find_all(recursive=False)),
            'schema_type': element.get('itemtype', '')
        }
```

### Classification Rules

```python
def classify_by_rules(self, element: Tag) -> Optional[str]:
    """Rule-based classification (fast, deterministic)."""
    
    # Navigation
    if element.name == 'nav':
        return 'navigation'
    
    if any('nav' in str(c) for c in element.get('class', [])):
        return 'navigation'
    
    # Header
    if element.name == 'header':
        return 'header'
    
    # Footer
    if element.name == 'footer':
        return 'footer'
    
    # Advertisement (common patterns)
    ad_patterns = ['ad', 'advertisement', 'sponsored', 'promo']
    classes = ' '.join(element.get('class', []))
    if any(pattern in classes.lower() for pattern in ad_patterns):
        return 'advertisement'
    
    # Product listing
    if element.get('itemtype') == 'http://schema.org/Product':
        return 'product_detail'
    
    # Form
    if element.name == 'form' or element.find('form'):
        return 'form'
    
    # Table
    if element.name == 'table':
        return 'table'
    
    return None
```

---

## Smart Extraction

### Pattern-Based Extraction

```python
class SmartExtractor:
    """Intelligently extract data based on field semantics."""
    
    def extract(self, html: str, field_name: str) -> ExtractionResult:
        """Extract a field using multiple strategies."""
        soup = BeautifulSoup(html, 'lxml')
        
        # Strategy 1: Schema.org markup
        result = self.extract_from_schema(soup, field_name)
        if result:
            return result
        
        # Strategy 2: OpenGraph / meta tags
        result = self.extract_from_meta(soup, field_name)
        if result:
            return result
        
        # Strategy 3: Pattern matching
        result = self.extract_by_pattern(soup, field_name)
        if result:
            return result
        
        # Strategy 4: ML-based extraction
        result = self.extract_by_ml(soup, field_name)
        if result:
            return result
        
        return ExtractionResult(value=None, confidence=0.0)
```

### Field-Specific Patterns

```python
EXTRACTION_PATTERNS = {
    'price': {
        'regexes': [
            r'\$\s*\d+[.,]\d{2}',           # $49.99
            r'€\s*\d+[.,]\d{2}',            # €49,99
            r'£\s*\d+[.,]\d{2}',            # £49.99
            r'\d+[.,]\d{2}\s*USD',          # 49.99 USD
        ],
        'css_selectors': [
            '[itemprop="price"]',
            '.price',
            '.product-price',
            'span.sale-price',
            'div.price-box span',
        ],
        'class_keywords': ['price', 'cost', 'sale', 'amount'],
        'text_indicators': ['$', '€', '£', 'USD', 'EUR', 'GBP']
    },
    
    'product_name': {
        'css_selectors': [
            '[itemprop="name"]',
            'h1.product-title',
            'h1.product-name',
            'div.product-info h1',
        ],
        'class_keywords': ['title', 'name', 'product-name'],
        'heading_tags': ['h1', 'h2']
    },
    
    'rating': {
        'regexes': [
            r'(\d+\.?\d*)\s*out of\s*5',
            r'(\d+\.?\d*)\s*/\s*5',
            r'(\d+\.?\d*)\s*stars?',
        ],
        'css_selectors': [
            '[itemprop="ratingValue"]',
            '.rating',
            '.star-rating',
            'span.rating-value',
        ],
        'class_keywords': ['rating', 'stars', 'score'],
    },
    
    'email': {
        'regexes': [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ],
        'css_selectors': [
            '[href^="mailto:"]',
            '[itemprop="email"]',
        ]
    },
    
    'phone': {
        'regexes': [
            r'\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',  # US format
            r'\+\d{1,3}\s?\(?\d{1,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}',  # International
        ],
        'css_selectors': [
            '[href^="tel:"]',
            '[itemprop="telephone"]',
        ]
    }
}
```

### Confidence Scoring

```python
def score_extraction(self, value: Any, field_name: str, method: str) -> float:
    """Score extraction confidence."""
    confidence = 0.0
    
    # Method confidence
    method_confidence = {
        'schema.org': 0.95,
        'meta_tag': 0.90,
        'pattern_match': 0.70,
        'ml_model': 0.80,
        'class_name': 0.60
    }
    confidence += method_confidence.get(method, 0.5)
    
    # Value validation
    if field_name == 'price':
        if self.is_valid_price(value):
            confidence += 0.1
        else:
            confidence -= 0.3
    
    elif field_name == 'email':
        if self.is_valid_email(value):
            confidence += 0.1
        else:
            confidence = 0.0  # Invalid email
    
    # Context validation
    parent_context = self.get_parent_context(value)
    if field_name in parent_context:
        confidence += 0.1
    
    return min(confidence, 1.0)
```

---

## Adaptive Chunking

### Chunking Strategy

```python
class AdaptiveChunker:
    """Split large HTML into processable chunks."""
    
    def chunk(self, html: str, max_size: int = 50000) -> List[Chunk]:
        """Split HTML intelligently."""
        soup = BeautifulSoup(html, 'lxml')
        
        if len(html) <= max_size:
            return [Chunk(html=html, type='full', index=0)]
        
        # Strategy 1: Split by semantic sections
        chunks = self.chunk_by_sections(soup, max_size)
        if chunks:
            return chunks
        
        # Strategy 2: Split by repeated elements (product cards)
        chunks = self.chunk_by_repeated_elements(soup, max_size)
        if chunks:
            return chunks
        
        # Strategy 3: Sliding window with overlap
        chunks = self.chunk_by_sliding_window(html, max_size, overlap=5000)
        return chunks
    
    def chunk_by_sections(self, soup: BeautifulSoup, max_size: int) -> List[Chunk]:
        """Split by major sections."""
        sections = soup.find_all(['article', 'section', 'div'], class_=re.compile(r'section|container', re.I))
        
        chunks = []
        current_chunk = ""
        current_index = 0
        
        for section in sections:
            section_html = str(section)
            
            if len(current_chunk) + len(section_html) > max_size:
                # Save current chunk
                if current_chunk:
                    chunks.append(Chunk(
                        html=current_chunk,
                        type='section',
                        index=current_index
                    ))
                    current_index += 1
                
                # Start new chunk
                current_chunk = section_html
            else:
                current_chunk += section_html
        
        # Add final chunk
        if current_chunk:
            chunks.append(Chunk(html=current_chunk, type='section', index=current_index))
        
        return chunks
    
    def chunk_by_repeated_elements(self, soup: BeautifulSoup, max_size: int) -> List[Chunk]:
        """Split by repeated elements (e.g., product cards)."""
        # Detect repeated pattern
        repeated = self.detect_repeated_elements(soup)
        
        if not repeated:
            return []
        
        chunks = []
        current_chunk = ""
        current_items = []
        current_index = 0
        
        for element in repeated:
            element_html = str(element)
            
            if len(current_chunk) + len(element_html) > max_size:
                # Save current chunk
                if current_chunk:
                    chunks.append(Chunk(
                        html=current_chunk,
                        type='repeated',
                        index=current_index,
                        item_count=len(current_items)
                    ))
                    current_index += 1
                
                # Start new chunk
                current_chunk = element_html
                current_items = [element]
            else:
                current_chunk += element_html
                current_items.append(element)
        
        # Add final chunk
        if current_chunk:
            chunks.append(Chunk(
                html=current_chunk,
                type='repeated',
                index=current_index,
                item_count=len(current_items)
            ))
        
        return chunks
```

---

## Batch Processing

### Parallel Processing

```python
class BatchProcessor:
    """Process large pages in parallel batches."""
    
    async def process_large_page(
        self,
        html: str,
        extraction_task: ExtractionTask
    ) -> List[Dict]:
        """Process a large page in parallel."""
        # 1. Chunk the HTML
        chunks = self.chunker.chunk(html)
        
        # 2. Process chunks in parallel
        tasks = [
            self.process_chunk(chunk, extraction_task)
            for chunk in chunks
        ]
        
        chunk_results = await asyncio.gather(*tasks)
        
        # 3. Merge and deduplicate results
        merged = self.merge_results(chunk_results)
        
        # 4. Cross-chunk validation
        validated = self.validate_across_chunks(merged, chunks)
        
        return validated
    
    async def process_chunk(
        self,
        chunk: Chunk,
        task: ExtractionTask
    ) -> List[Dict]:
        """Process a single chunk."""
        extractor = SmartExtractor()
        results = []
        
        for field in task.fields:
            result = extractor.extract(chunk.html, field)
            if result.value:
                results.append({
                    'field': field,
                    'value': result.value,
                    'confidence': result.confidence,
                    'chunk_index': chunk.index
                })
        
        return results
    
    def merge_results(self, chunk_results: List[List[Dict]]) -> List[Dict]:
        """Merge and deduplicate results from chunks."""
        merged = {}
        
        for chunk_result in chunk_results:
            for item in chunk_result:
                key = (item['field'], item['value'])
                
                if key in merged:
                    # Increase confidence if found in multiple chunks
                    merged[key]['confidence'] = max(
                        merged[key]['confidence'],
                        item['confidence']
                    )
                    merged[key]['chunk_count'] += 1
                else:
                    merged[key] = {
                        **item,
                        'chunk_count': 1
                    }
        
        return list(merged.values())
```

---

## Diff-Based Updates

### Incremental Processing

```python
class DiffProcessor:
    """Process only changed content between page loads."""
    
    def __init__(self):
        self.page_cache = {}
    
    def process_with_diff(
        self,
        url: str,
        current_html: str,
        extraction_task: ExtractionTask
    ) -> Dict:
        """Process only the diff from last visit."""
        previous_html = self.page_cache.get(url)
        
        if not previous_html:
            # First visit, process full page
            result = self.process_full(current_html, extraction_task)
            self.page_cache[url] = current_html
            return result
        
        # Calculate diff
        diff = self.calculate_diff(previous_html, current_html)
        
        if diff.similarity > 0.95:
            # Page barely changed, use cached results
            return self.page_cache.get(f"{url}_result")
        
        # Process only changed regions
        result = self.process_diff(diff, extraction_task)
        
        # Update cache
        self.page_cache[url] = current_html
        self.page_cache[f"{url}_result"] = result
        
        return result
    
    def calculate_diff(self, html1: str, html2: str) -> Diff:
        """Calculate structural diff between two HTML documents."""
        soup1 = BeautifulSoup(html1, 'lxml')
        soup2 = BeautifulSoup(html2, 'lxml')
        
        # Find added, removed, and modified elements
        diff = Diff()
        diff.added = self.find_added_elements(soup1, soup2)
        diff.removed = self.find_removed_elements(soup1, soup2)
        diff.modified = self.find_modified_elements(soup1, soup2)
        diff.similarity = self.calculate_similarity(soup1, soup2)
        
        return diff
```

---

## Schema Detection

### Auto-Detect Data Schemas

```python
class SchemaDetector:
    """Automatically detect data schemas in HTML."""
    
    def detect_schema(self, html: str) -> Schema:
        """Detect the implicit schema of the page."""
        soup = BeautifulSoup(html, 'lxml')
        
        # 1. Check for schema.org markup
        schema_org = self.detect_schema_org(soup)
        if schema_org:
            return schema_org
        
        # 2. Detect repeated patterns
        repeated = self.detect_repeated_pattern(soup)
        if repeated:
            return self.infer_schema_from_pattern(repeated)
        
        # 3. Detect tables
        tables = soup.find_all('table')
        if tables:
            return self.infer_schema_from_table(tables[0])
        
        return Schema()
    
    def infer_schema_from_pattern(self, elements: List[Tag]) -> Schema:
        """Infer schema from repeated elements."""
        # Analyze first few elements
        sample = elements[:5]
        
        field_candidates = {}
        
        for element in sample:
            # Find all text-bearing children
            children = element.find_all(string=True, recursive=True)
            
            for child in children:
                # Classify by parent tag/class
                parent = child.parent
                key = (parent.name, ' '.join(parent.get('class', [])))
                
                if key not in field_candidates:
                    field_candidates[key] = []
                
                field_candidates[key].append(child.strip())
        
        # Build schema
        schema = Schema()
        
        for (tag, class_name), values in field_candidates.items():
            # Infer field type from values
            field_type = self.infer_type(values)
            field_name = self.guess_field_name(class_name, values)
            
            schema.add_field(Field(
                name=field_name,
                type=field_type,
                selector=f"{tag}.{class_name}" if class_name else tag,
                sample_values=values
            ))
        
        return schema
```

---

**Next:** See [search-engine.md](./search-engine.md) for search optimization.
