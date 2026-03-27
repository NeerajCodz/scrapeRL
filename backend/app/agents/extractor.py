"""Extractor agent for data extraction with selectors."""

import re
from typing import Any

from app.core.action import Action, ActionType
from app.core.observation import Observation, PageElement

from .base import BaseAgent


class ExtractorAgent(BaseAgent):
    """
    Agent responsible for extracting structured data from pages.
    
    The ExtractorAgent handles:
    - Identifying data elements using CSS/XPath selectors
    - Extracting text, attributes, and structured content
    - Handling tables and lists
    - Post-processing extracted values
    - Confidence scoring for extractions
    """

    def __init__(
        self,
        agent_id: str = "extractor",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the ExtractorAgent.
        
        Args:
            agent_id: Unique identifier for this agent.
            config: Optional configuration with keys:
                - min_confidence: Minimum confidence to accept extraction
                - extraction_timeout: Timeout for extraction operations
                - enable_fuzzy_matching: Enable fuzzy text matching
        """
        super().__init__(agent_id, config)
        self.min_confidence = self.config.get("min_confidence", 0.5)
        self.extraction_timeout = self.config.get("extraction_timeout", 5000)
        self.enable_fuzzy_matching = self.config.get("enable_fuzzy_matching", True)
        self._extraction_cache: dict[str, Any] = {}
        self._selector_patterns: dict[str, list[str]] = self._init_selector_patterns()

    def _init_selector_patterns(self) -> dict[str, list[str]]:
        """Initialize common selector patterns for different field types."""
        return {
            "price": [
                "[class*='price']",
                "[id*='price']",
                "[itemprop='price']",
                ".product-price",
                ".item-price",
                "span[data-price]",
            ],
            "title": [
                "h1",
                "[class*='title']",
                "[itemprop='name']",
                ".product-title",
                ".item-title",
            ],
            "description": [
                "[class*='description']",
                "[itemprop='description']",
                ".product-description",
                "article p",
                ".content p",
            ],
            "image": [
                "[class*='product-image'] img",
                "[itemprop='image']",
                ".main-image img",
                "figure img",
            ],
            "date": [
                "time",
                "[datetime]",
                "[class*='date']",
                "[itemprop='datePublished']",
            ],
            "author": [
                "[class*='author']",
                "[itemprop='author']",
                "[rel='author']",
                ".byline",
            ],
        }

    async def act(self, observation: Observation) -> Action:
        """
        Select the best extraction action based on observation.
        
        Analyzes the page and decides what data to extract next.
        
        Args:
            observation: The current state observation.
            
        Returns:
            The extraction action to execute.
        """
        try:
            # Get remaining fields to extract
            remaining_fields = observation.fields_remaining

            if not remaining_fields:
                return Action(
                    action_type=ActionType.DONE,
                    parameters={"success": True, "message": "All fields extracted"},
                    reasoning="No more fields to extract",
                    confidence=1.0,
                    agent_id=self.agent_id,
                )

            # Pick the next field to extract
            field_name = remaining_fields[0]

            # Find best selector for the field
            selector, confidence = await self._find_selector_for_field(
                field_name,
                observation,
            )

            if selector and confidence >= self.min_confidence:
                return self._create_extraction_action(
                    field_name,
                    selector,
                    confidence,
                )

            # Try alternative extraction methods
            alt_action = await self._try_alternative_extraction(
                field_name,
                observation,
            )
            if alt_action:
                return alt_action

            # Cannot extract this field
            return Action(
                action_type=ActionType.EXTRACT_FIELD,
                parameters={
                    "field_name": field_name,
                    "selector": None,
                    "extraction_method": "llm",
                },
                reasoning=f"No selector found, using LLM extraction for {field_name}",
                confidence=0.4,
                agent_id=self.agent_id,
            )

        except Exception as e:
            return Action(
                action_type=ActionType.FAIL,
                parameters={"success": False, "message": str(e)},
                reasoning=f"Extraction error: {e}",
                confidence=1.0,
                agent_id=self.agent_id,
            )

    async def plan(self, observation: Observation) -> list[Action]:
        """
        Create an extraction plan for all remaining fields.
        
        Analyzes the page structure and plans the optimal
        extraction sequence.
        
        Args:
            observation: The current state observation.
            
        Returns:
            A list of planned extraction actions.
        """
        try:
            actions: list[Action] = []
            remaining_fields = observation.fields_remaining

            for field_name in remaining_fields:
                selector, confidence = await self._find_selector_for_field(
                    field_name,
                    observation,
                )

                if selector:
                    actions.append(
                        self._create_extraction_action(
                            field_name,
                            selector,
                            confidence,
                        )
                    )
                else:
                    # Plan LLM-based extraction as fallback
                    actions.append(
                        Action(
                            action_type=ActionType.EXTRACT_FIELD,
                            parameters={
                                "field_name": field_name,
                                "extraction_method": "llm",
                            },
                            reasoning=f"Planning LLM extraction for {field_name}",
                            confidence=0.5,
                            agent_id=self.agent_id,
                        )
                    )

            return actions

        except Exception as e:
            return [
                Action(
                    action_type=ActionType.FAIL,
                    parameters={"message": f"Extraction planning failed: {e}"},
                    reasoning=str(e),
                    confidence=1.0,
                    agent_id=self.agent_id,
                )
            ]

    async def _find_selector_for_field(
        self,
        field_name: str,
        observation: Observation,
    ) -> tuple[str | None, float]:
        """
        Find the best selector for a field.
        
        Args:
            field_name: Name of the field to extract.
            observation: Current observation.
            
        Returns:
            Tuple of (selector, confidence).
        """
        best_selector: str | None = None
        best_confidence = 0.0

        # Check predefined patterns first
        patterns = self._get_patterns_for_field(field_name)
        for pattern in patterns:
            element = self._find_element_by_selector(
                pattern,
                observation.page_elements,
            )
            if element:
                confidence = self._calculate_confidence(element, field_name)
                if confidence > best_confidence:
                    best_selector = element.selector
                    best_confidence = confidence

        # Search by text content if fuzzy matching enabled
        if self.enable_fuzzy_matching and best_confidence < 0.7:
            element, confidence = self._find_element_by_text(
                field_name,
                observation.page_elements,
            )
            if element and confidence > best_confidence:
                best_selector = element.selector
                best_confidence = confidence

        return best_selector, best_confidence

    def _get_patterns_for_field(self, field_name: str) -> list[str]:
        """Get selector patterns for a field type."""
        field_lower = field_name.lower()

        # Direct match
        if field_lower in self._selector_patterns:
            return self._selector_patterns[field_lower]

        # Partial match
        for key, patterns in self._selector_patterns.items():
            if key in field_lower or field_lower in key:
                return patterns

        # Generate generic patterns
        return [
            f"[class*='{field_lower}']",
            f"[id*='{field_lower}']",
            f"[data-{field_lower}]",
            f".{field_lower}",
            f"#{field_lower}",
        ]

    def _find_element_by_selector(
        self,
        selector: str,
        elements: list[PageElement],
    ) -> PageElement | None:
        """Find an element matching a selector pattern."""
        selector_lower = selector.lower()

        for element in elements:
            element_selector = element.selector.lower()
            if selector_lower in element_selector:
                return element

            # Check class and id attributes
            classes = element.attributes.get("class", "").lower()
            element_id = element.attributes.get("id", "").lower()

            if selector_lower.strip(".[#]") in classes:
                return element
            if selector_lower.strip(".[#]") in element_id:
                return element

        return None

    def _find_element_by_text(
        self,
        field_name: str,
        elements: list[PageElement],
    ) -> tuple[PageElement | None, float]:
        """Find an element by text content matching."""
        field_lower = field_name.lower().replace("_", " ")
        best_element: PageElement | None = None
        best_score = 0.0

        for element in elements:
            if not element.text:
                continue

            text_lower = element.text.lower()

            # Check for label-like patterns
            if f"{field_lower}:" in text_lower or f"{field_lower} :" in text_lower:
                score = 0.9
            elif field_lower in text_lower:
                # Calculate similarity score
                score = len(field_lower) / max(len(text_lower), 1) * 0.8
            else:
                continue

            if score > best_score:
                best_element = element
                best_score = score

        return best_element, best_score

    def _calculate_confidence(self, element: PageElement, field_name: str) -> float:
        """Calculate extraction confidence for an element."""
        confidence = 0.5

        # Boost for visible elements
        if element.is_visible:
            confidence += 0.1

        # Boost for semantic attributes
        if element.attributes.get("itemprop"):
            confidence += 0.2
        if element.attributes.get("data-field"):
            confidence += 0.15

        # Boost if text contains field name
        if element.text and field_name.lower() in element.text.lower():
            confidence += 0.1

        # Penalty for very long text (likely not a single field)
        if element.text and len(element.text) > 500:
            confidence -= 0.2

        return min(1.0, max(0.0, confidence))

    async def _try_alternative_extraction(
        self,
        field_name: str,
        observation: Observation,
    ) -> Action | None:
        """Try alternative extraction methods."""
        # Check for table data
        for element in observation.page_elements:
            if element.tag in ("table", "tbody"):
                return Action(
                    action_type=ActionType.EXTRACT_TABLE,
                    parameters={
                        "table_selector": element.selector,
                        "target_field": field_name,
                    },
                    reasoning=f"Extracting {field_name} from table",
                    confidence=0.6,
                    agent_id=self.agent_id,
                )

        # Check for list data
        for element in observation.page_elements:
            if element.tag in ("ul", "ol", "dl"):
                return Action(
                    action_type=ActionType.EXTRACT_LIST,
                    parameters={
                        "container_selector": element.selector,
                        "item_selector": "li",
                        "field_selectors": {field_name: "text"},
                    },
                    reasoning=f"Extracting {field_name} from list",
                    confidence=0.55,
                    agent_id=self.agent_id,
                )

        return None

    def _create_extraction_action(
        self,
        field_name: str,
        selector: str,
        confidence: float,
    ) -> Action:
        """Create an extraction action."""
        return Action(
            action_type=ActionType.EXTRACT_FIELD,
            parameters={
                "field_name": field_name,
                "selector": selector,
                "extraction_method": "text",
            },
            reasoning=f"Extracting {field_name} using selector: {selector}",
            confidence=confidence,
            agent_id=self.agent_id,
        )

    def extract_with_regex(
        self,
        text: str,
        pattern: str,
        group: int = 0,
    ) -> str | None:
        """
        Extract text using a regex pattern.
        
        Args:
            text: The text to search in.
            pattern: Regex pattern.
            group: Capture group to return.
            
        Returns:
            Extracted text or None.
        """
        try:
            match = re.search(pattern, text)
            if match:
                return match.group(group)
            return None
        except re.error:
            return None

    def post_process_value(
        self,
        value: Any,
        field_name: str,
    ) -> Any:
        """
        Post-process an extracted value based on field type.
        
        Args:
            value: The raw extracted value.
            field_name: Name of the field (used to infer type).
            
        Returns:
            Processed value.
        """
        if value is None:
            return None

        value_str = str(value).strip()
        field_lower = field_name.lower()

        # Price processing
        if "price" in field_lower:
            # Remove currency symbols but keep numbers and decimal
            price_match = re.search(r"[\d,]+\.?\d*", value_str.replace(",", ""))
            if price_match:
                return float(price_match.group().replace(",", ""))

        # Date processing
        if "date" in field_lower:
            return value_str  # Return as-is, let caller parse

        # Number processing
        if any(x in field_lower for x in ["count", "quantity", "number"]):
            num_match = re.search(r"\d+", value_str)
            if num_match:
                return int(num_match.group())

        return value_str

    def reset(self) -> None:
        """Reset the extractor state."""
        super().reset()
        self._extraction_cache.clear()
