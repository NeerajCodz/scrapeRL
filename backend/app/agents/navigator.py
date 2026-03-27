"""Navigator agent for URL prioritization and page navigation."""

from typing import Any
from urllib.parse import urljoin, urlparse

from app.core.action import Action, ActionType
from app.core.observation import Observation, PageElement

from .base import BaseAgent


class NavigatorAgent(BaseAgent):
    """
    Agent responsible for intelligent page navigation.
    
    The NavigatorAgent handles:
    - URL prioritization based on relevance to task
    - Link discovery and scoring
    - Navigation decision making
    - Handling pagination and multi-page content
    - Avoiding irrelevant or harmful URLs
    """

    def __init__(
        self,
        agent_id: str = "navigator",
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the NavigatorAgent.
        
        Args:
            agent_id: Unique identifier for this agent.
            config: Optional configuration with keys:
                - max_depth: Maximum navigation depth (default: 5)
                - allowed_domains: List of allowed domains to visit
                - blocked_patterns: URL patterns to avoid
                - prioritize_https: Prefer HTTPS URLs (default: True)
        """
        super().__init__(agent_id, config)
        self.max_depth = self.config.get("max_depth", 5)
        self.allowed_domains = self.config.get("allowed_domains", [])
        self.blocked_patterns = self.config.get("blocked_patterns", [
            "logout", "signout", "delete", "remove", "unsubscribe",
        ])
        self.prioritize_https = self.config.get("prioritize_https", True)
        self._visited_urls: set[str] = set()
        self._url_scores: dict[str, float] = {}

    async def act(self, observation: Observation) -> Action:
        """
        Select the best navigation action based on observation.
        
        Analyzes available links and decides whether to:
        - Navigate to a new page
        - Go back to a previous page
        - Click an element to reveal more content
        
        Args:
            observation: The current state observation.
            
        Returns:
            The navigation action to execute.
        """
        try:
            # Track current URL
            if observation.current_url:
                self._visited_urls.add(observation.current_url)

            # Check if we've reached max depth
            nav_depth = len(observation.navigation_history)
            if nav_depth >= self.max_depth:
                return self._create_go_back_action(
                    "Reached maximum navigation depth"
                )

            # Find best link to follow
            best_link = await self._find_best_link(observation)

            if best_link:
                return self._create_navigate_action(best_link, observation)

            # Check for pagination
            pagination_action = self._find_pagination(observation)
            if pagination_action:
                return pagination_action

            # No good links, consider going back
            if observation.can_go_back and nav_depth > 1:
                return self._create_go_back_action(
                    "No relevant links found, going back"
                )

            # Nothing to navigate to
            return Action(
                action_type=ActionType.WAIT,
                parameters={"duration_ms": 500},
                reasoning="No navigation targets found",
                confidence=0.5,
                agent_id=self.agent_id,
            )

        except Exception as e:
            return Action(
                action_type=ActionType.FAIL,
                parameters={"success": False, "message": str(e)},
                reasoning=f"Navigation error: {e}",
                confidence=1.0,
                agent_id=self.agent_id,
            )

    async def plan(self, observation: Observation) -> list[Action]:
        """
        Create a navigation plan based on task requirements.
        
        Plans a sequence of navigation actions to reach content
        relevant to the task.
        
        Args:
            observation: The current state observation.
            
        Returns:
            A list of planned navigation actions.
        """
        try:
            actions: list[Action] = []
            task_context = observation.task_context

            if not task_context:
                return []

            # Analyze task hints for navigation targets
            target_urls = self._extract_urls_from_hints(task_context.hints)

            for url in target_urls[:3]:  # Limit to top 3 URLs
                if url not in self._visited_urls:
                    actions.append(
                        Action(
                            action_type=ActionType.NAVIGATE,
                            parameters={"url": url, "timeout_ms": 30000},
                            reasoning=f"Navigating to task-relevant URL: {url}",
                            confidence=0.85,
                            agent_id=self.agent_id,
                        )
                    )

            # If no URLs from hints, plan a search
            if not actions:
                search_query = self._build_search_query(task_context)
                actions.append(
                    Action(
                        action_type=ActionType.SEARCH_ENGINE,
                        parameters={"query": search_query, "engine": "google"},
                        reasoning=f"Searching for: {search_query}",
                        confidence=0.7,
                        agent_id=self.agent_id,
                    )
                )

            return actions

        except Exception as e:
            return [
                Action(
                    action_type=ActionType.FAIL,
                    parameters={"message": f"Navigation planning failed: {e}"},
                    reasoning=str(e),
                    confidence=1.0,
                    agent_id=self.agent_id,
                )
            ]

    async def _find_best_link(self, observation: Observation) -> str | None:
        """Find the best link to follow based on task relevance."""
        if not observation.task_context:
            return None

        target_fields = observation.task_context.target_fields
        remaining_fields = observation.fields_remaining

        # Score all links on the page
        link_scores: list[tuple[str, float]] = []

        for element in observation.page_elements:
            if not element.is_interactive:
                continue

            href = element.attributes.get("href", "")
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            # Resolve relative URLs
            full_url = self._resolve_url(href, observation.current_url)
            if not full_url:
                continue

            # Skip already visited URLs
            if full_url in self._visited_urls:
                continue

            # Skip blocked patterns
            if self._is_blocked_url(full_url):
                continue

            # Check domain restrictions
            if not self._is_allowed_domain(full_url):
                continue

            # Score the link
            score = self._score_link(element, full_url, remaining_fields)
            if score > 0:
                link_scores.append((full_url, score))

        # Return highest scoring link
        if link_scores:
            link_scores.sort(key=lambda x: x[1], reverse=True)
            return link_scores[0][0]

        return None

    def _score_link(
        self,
        element: PageElement,
        url: str,
        target_fields: list[str],
    ) -> float:
        """Score a link based on relevance to task fields."""
        score = 0.0
        text = (element.text or "").lower()
        url_lower = url.lower()

        # Check if link text contains target field names
        for field in target_fields:
            field_lower = field.lower()
            if field_lower in text:
                score += 0.4
            if field_lower in url_lower:
                score += 0.3

        # Prefer HTTPS
        if self.prioritize_https and url.startswith("https://"):
            score += 0.1

        # Boost content-like URLs
        content_indicators = ["detail", "view", "info", "about", "product", "page"]
        for indicator in content_indicators:
            if indicator in url_lower:
                score += 0.2
                break

        # Penalize non-content URLs
        noise_indicators = ["login", "cart", "checkout", "share", "print"]
        for indicator in noise_indicators:
            if indicator in url_lower:
                score -= 0.3
                break

        return max(0.0, score)

    def _resolve_url(self, href: str, base_url: str | None) -> str | None:
        """Resolve a relative URL to an absolute URL."""
        if not href:
            return None

        if href.startswith(("http://", "https://")):
            return href

        if not base_url:
            return None

        try:
            return urljoin(base_url, href)
        except Exception:
            return None

    def _is_blocked_url(self, url: str) -> bool:
        """Check if URL matches any blocked patterns."""
        url_lower = url.lower()
        for pattern in self.blocked_patterns:
            if pattern.lower() in url_lower:
                return True
        return False

    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL domain is allowed."""
        if not self.allowed_domains:
            return True

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            for allowed in self.allowed_domains:
                if domain == allowed.lower() or domain.endswith("." + allowed.lower()):
                    return True
            return False
        except Exception:
            return False

    def _find_pagination(self, observation: Observation) -> Action | None:
        """Find and create action for pagination elements."""
        pagination_selectors = [
            "[aria-label*='next']",
            "[aria-label*='Next']",
            "a.next",
            "button.next",
            "[rel='next']",
        ]

        for element in observation.page_elements:
            text = (element.text or "").lower()
            if element.is_interactive and ("next" in text or "more" in text):
                return Action(
                    action_type=ActionType.CLICK,
                    parameters={"selector": element.selector},
                    reasoning="Clicking pagination to load more content",
                    confidence=0.7,
                    agent_id=self.agent_id,
                )

        return None

    def _extract_urls_from_hints(self, hints: list[str]) -> list[str]:
        """Extract URLs from task hints."""
        urls = []
        for hint in hints:
            if hint.startswith(("http://", "https://")):
                urls.append(hint)
            elif "://" not in hint and "." in hint:
                # Might be a domain without protocol
                urls.append(f"https://{hint}")
        return urls

    def _build_search_query(self, task_context: Any) -> str:
        """Build a search query from task context."""
        parts = [task_context.task_name]
        if task_context.target_fields:
            parts.extend(task_context.target_fields[:2])
        return " ".join(parts)

    def _create_navigate_action(self, url: str, observation: Observation) -> Action:
        """Create a navigate action for the given URL."""
        return Action(
            action_type=ActionType.NAVIGATE,
            parameters={"url": url, "timeout_ms": 30000},
            reasoning=f"Navigating to relevant URL: {url}",
            confidence=0.75,
            agent_id=self.agent_id,
        )

    def _create_go_back_action(self, reason: str) -> Action:
        """Create a go back action."""
        return Action(
            action_type=ActionType.GO_BACK,
            parameters={},
            reasoning=reason,
            confidence=0.8,
            agent_id=self.agent_id,
        )

    def get_visited_urls(self) -> set[str]:
        """Get the set of visited URLs."""
        return self._visited_urls.copy()

    def reset(self) -> None:
        """Reset the navigator state."""
        super().reset()
        self._visited_urls.clear()
        self._url_scores.clear()
