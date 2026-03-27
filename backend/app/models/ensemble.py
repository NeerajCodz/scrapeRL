"""Model ensemble for running multiple models and aggregating results."""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.models.providers.base import (
    BaseProvider,
    CompletionResponse,
    ProviderError,
    TokenUsage,
)
from app.models.router import SmartModelRouter

logger = logging.getLogger(__name__)


class AggregationStrategy(str, Enum):
    """Strategy for aggregating ensemble results."""

    MAJORITY_VOTE = "majority_vote"  # Use most common response
    CONFIDENCE_WEIGHTED = "confidence_weighted"  # Weight by model confidence
    FIRST_SUCCESS = "first_success"  # Use first successful response
    BEST_QUALITY = "best_quality"  # Use response from highest quality model
    CONCATENATE = "concatenate"  # Combine all responses
    CONSENSUS = "consensus"  # Only return if models agree


@dataclass
class EnsembleResult:
    """Result from an ensemble run."""

    content: str
    responses: list[CompletionResponse]
    agreement_score: float  # 0-1, how much models agreed
    strategy: AggregationStrategy
    selected_model: str | None = None
    total_cost: float = 0.0
    total_tokens: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "responses": [r.to_dict() for r in self.responses],
            "agreement_score": self.agreement_score,
            "strategy": self.strategy.value,
            "selected_model": self.selected_model,
            "total_cost": self.total_cost,
            "total_tokens": {
                "prompt": self.total_tokens.prompt_tokens,
                "completion": self.total_tokens.completion_tokens,
                "total": self.total_tokens.total_tokens,
            },
            "metadata": self.metadata,
        }


class ModelEnsemble:
    """Run multiple models and aggregate their results."""

    # Model quality tiers for weighted voting
    MODEL_QUALITY_TIERS: dict[str, float] = {
        # Tier 1: Highest quality
        "claude-3-opus-20240229": 1.0,
        "gpt-4o": 0.98,
        "claude-3-5-sonnet-20241022": 0.97,
        "gemini-1.5-pro": 0.95,
        # Tier 2: High quality
        "gpt-4-turbo": 0.90,
        "gpt-4": 0.88,
        "claude-3-sonnet-20240229": 0.85,
        "llama-3.3-70b-versatile": 0.83,
        # Tier 3: Good quality
        "gpt-4o-mini": 0.75,
        "claude-3-5-haiku-20241022": 0.73,
        "gemini-1.5-flash": 0.70,
        "mixtral-8x7b-32768": 0.68,
        # Tier 4: Fast/cheap
        "claude-3-haiku-20240307": 0.60,
        "llama-3.1-8b-instant": 0.55,
        "gpt-3.5-turbo": 0.50,
    }

    def __init__(
        self,
        router: SmartModelRouter,
        default_models: list[str] | None = None,
        default_strategy: AggregationStrategy = AggregationStrategy.CONFIDENCE_WEIGHTED,
        timeout: float = 60.0,
    ):
        """Initialize the ensemble.

        Args:
            router: SmartModelRouter instance for accessing providers
            default_models: Default models to use in ensemble
            default_strategy: Default aggregation strategy
            timeout: Timeout for each model completion
        """
        self.router = router
        self.default_models = default_models or []
        self.default_strategy = default_strategy
        self.timeout = timeout

    async def run(
        self,
        messages: list[dict[str, Any]],
        models: list[str] | None = None,
        strategy: AggregationStrategy | None = None,
        min_responses: int = 1,
        **kwargs: Any,
    ) -> EnsembleResult:
        """Run multiple models and aggregate results.

        Args:
            messages: List of message dicts
            models: List of model IDs to use (uses defaults if not specified)
            strategy: Aggregation strategy (uses default if not specified)
            min_responses: Minimum number of successful responses required
            **kwargs: Additional completion parameters

        Returns:
            EnsembleResult with aggregated content and metadata

        Raises:
            ProviderError: If not enough models respond successfully
        """
        models_to_use = models or self.default_models
        strategy = strategy or self.default_strategy

        if not models_to_use:
            # Use top 3 available models
            available = self.router.get_available_models()
            models_to_use = [m.id for m in available[:3]]

        if not models_to_use:
            raise ProviderError("No models available for ensemble", "ensemble")

        # Run all models concurrently
        tasks = []
        for model_id in models_to_use:
            provider = self.router.get_provider_for_model(model_id)
            if provider:
                task = self._run_model(provider, model_id, messages, **kwargs)
                tasks.append((model_id, task))

        if not tasks:
            raise ProviderError("No valid models for ensemble", "ensemble")

        # Gather results
        responses: list[CompletionResponse] = []
        errors: list[tuple[str, Exception]] = []

        results = await asyncio.gather(
            *[t[1] for t in tasks],
            return_exceptions=True,
        )

        for (model_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.warning(f"Model {model_id} failed: {result}")
                errors.append((model_id, result))
            elif result is not None:
                responses.append(result)

        if len(responses) < min_responses:
            raise ProviderError(
                f"Only {len(responses)} models responded, need {min_responses}. "
                f"Errors: {[str(e) for _, e in errors]}",
                "ensemble",
            )

        # Aggregate results
        result = self._aggregate(responses, strategy)

        return result

    async def _run_model(
        self,
        provider: BaseProvider,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> CompletionResponse | None:
        """Run a single model with timeout."""
        try:
            return await asyncio.wait_for(
                provider.complete(messages, model_id, **kwargs),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Model {model_id} timed out")
            return None
        except Exception as e:
            logger.warning(f"Model {model_id} error: {e}")
            raise

    def _aggregate(
        self,
        responses: list[CompletionResponse],
        strategy: AggregationStrategy,
    ) -> EnsembleResult:
        """Aggregate responses based on strategy."""
        if not responses:
            raise ProviderError("No responses to aggregate", "ensemble")

        # Calculate total cost and tokens
        total_cost = sum(r.cost for r in responses)
        total_tokens = TokenUsage()
        for r in responses:
            total_tokens = total_tokens + r.usage

        # Calculate agreement score
        agreement_score = self._calculate_agreement(responses)

        # Select content based on strategy
        if strategy == AggregationStrategy.FIRST_SUCCESS:
            content, selected_model = self._first_success(responses)
        elif strategy == AggregationStrategy.MAJORITY_VOTE:
            content, selected_model = self._majority_vote(responses)
        elif strategy == AggregationStrategy.CONFIDENCE_WEIGHTED:
            content, selected_model = self._confidence_weighted(responses)
        elif strategy == AggregationStrategy.BEST_QUALITY:
            content, selected_model = self._best_quality(responses)
        elif strategy == AggregationStrategy.CONCATENATE:
            content, selected_model = self._concatenate(responses)
        elif strategy == AggregationStrategy.CONSENSUS:
            content, selected_model = self._consensus(responses, agreement_score)
        else:
            content, selected_model = self._first_success(responses)

        return EnsembleResult(
            content=content,
            responses=responses,
            agreement_score=agreement_score,
            strategy=strategy,
            selected_model=selected_model,
            total_cost=total_cost,
            total_tokens=total_tokens,
            metadata={
                "num_responses": len(responses),
                "models_used": [r.model for r in responses],
            },
        )

    def _calculate_agreement(self, responses: list[CompletionResponse]) -> float:
        """Calculate agreement score between responses.

        Uses simple similarity based on common words/tokens.
        """
        if len(responses) < 2:
            return 1.0

        # Tokenize responses (simple word-based)
        response_tokens = []
        for r in responses:
            words = set(r.content.lower().split())
            response_tokens.append(words)

        # Calculate pairwise Jaccard similarity
        similarities = []
        for i in range(len(response_tokens)):
            for j in range(i + 1, len(response_tokens)):
                set_i = response_tokens[i]
                set_j = response_tokens[j]

                if not set_i and not set_j:
                    similarities.append(1.0)
                elif not set_i or not set_j:
                    similarities.append(0.0)
                else:
                    intersection = len(set_i & set_j)
                    union = len(set_i | set_j)
                    similarities.append(intersection / union)

        return sum(similarities) / len(similarities) if similarities else 1.0

    def _first_success(
        self, responses: list[CompletionResponse]
    ) -> tuple[str, str | None]:
        """Return the first successful response."""
        r = responses[0]
        return r.content, r.model

    def _majority_vote(
        self, responses: list[CompletionResponse]
    ) -> tuple[str, str | None]:
        """Return the most common response (by content similarity)."""
        if len(responses) == 1:
            return responses[0].content, responses[0].model

        # Find response most similar to others
        best_idx = 0
        best_score = 0.0

        for i, r in enumerate(responses):
            score = 0.0
            words_i = set(r.content.lower().split())

            for j, other in enumerate(responses):
                if i != j:
                    words_j = set(other.content.lower().split())
                    if words_i and words_j:
                        intersection = len(words_i & words_j)
                        union = len(words_i | words_j)
                        score += intersection / union

            if score > best_score:
                best_score = score
                best_idx = i

        return responses[best_idx].content, responses[best_idx].model

    def _confidence_weighted(
        self, responses: list[CompletionResponse]
    ) -> tuple[str, str | None]:
        """Weight responses by model quality/confidence."""
        if len(responses) == 1:
            return responses[0].content, responses[0].model

        # Score each response by model quality
        scored = []
        for r in responses:
            quality = self.MODEL_QUALITY_TIERS.get(r.model, 0.5)
            scored.append((quality, r))

        # Sort by quality
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return highest quality response
        best = scored[0][1]
        return best.content, best.model

    def _best_quality(
        self, responses: list[CompletionResponse]
    ) -> tuple[str, str | None]:
        """Return response from highest quality model."""
        best_quality = 0.0
        best_response = responses[0]

        for r in responses:
            quality = self.MODEL_QUALITY_TIERS.get(r.model, 0.5)
            if quality > best_quality:
                best_quality = quality
                best_response = r

        return best_response.content, best_response.model

    def _concatenate(
        self, responses: list[CompletionResponse]
    ) -> tuple[str, str | None]:
        """Concatenate all responses."""
        parts = []
        models = []

        for r in responses:
            parts.append(f"[{r.model}]:\n{r.content}")
            models.append(r.model)

        content = "\n\n---\n\n".join(parts)
        return content, None  # No single model selected

    def _consensus(
        self,
        responses: list[CompletionResponse],
        agreement_score: float,
    ) -> tuple[str, str | None]:
        """Return result only if models agree (high agreement score)."""
        if agreement_score < 0.5:
            # Low agreement, return best quality with warning
            content, model = self._best_quality(responses)
            return f"[LOW CONSENSUS - {agreement_score:.2f}]\n{content}", model

        # Good agreement, return majority vote
        return self._majority_vote(responses)

    async def compare(
        self,
        messages: list[dict[str, Any]],
        models: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Compare responses from multiple models side-by-side.

        Args:
            messages: List of message dicts
            models: List of model IDs to compare
            **kwargs: Additional completion parameters

        Returns:
            Dictionary with comparison data
        """
        result = await self.run(
            messages,
            models,
            strategy=AggregationStrategy.CONCATENATE,
            **kwargs,
        )

        # Build comparison
        comparison = {
            "responses": [],
            "agreement_score": result.agreement_score,
            "total_cost": result.total_cost,
            "total_tokens": {
                "prompt": result.total_tokens.prompt_tokens,
                "completion": result.total_tokens.completion_tokens,
                "total": result.total_tokens.total_tokens,
            },
        }

        for r in result.responses:
            comparison["responses"].append({
                "model": r.model,
                "provider": r.provider,
                "content": r.content,
                "cost": r.cost,
                "latency_ms": r.latency_ms,
                "tokens": {
                    "prompt": r.usage.prompt_tokens,
                    "completion": r.usage.completion_tokens,
                },
                "quality_tier": self.MODEL_QUALITY_TIERS.get(r.model, 0.5),
            })

        return comparison

    async def debate(
        self,
        messages: list[dict[str, Any]],
        models: list[str] | None = None,
        rounds: int = 2,
        **kwargs: Any,
    ) -> EnsembleResult:
        """Run a debate between models where they can respond to each other.

        Args:
            messages: Initial messages
            models: Models to participate in debate
            rounds: Number of debate rounds
            **kwargs: Additional completion parameters

        Returns:
            Final ensemble result with debate history
        """
        models_to_use = models or self.default_models[:2]  # Default to 2 models

        if len(models_to_use) < 2:
            raise ProviderError("Debate requires at least 2 models", "ensemble")

        all_responses: list[CompletionResponse] = []
        debate_history: list[dict[str, Any]] = []
        current_messages = messages.copy()

        for round_num in range(rounds):
            round_responses = []

            for model_id in models_to_use:
                provider = self.router.get_provider_for_model(model_id)
                if not provider:
                    continue

                try:
                    response = await asyncio.wait_for(
                        provider.complete(current_messages, model_id, **kwargs),
                        timeout=self.timeout,
                    )
                    round_responses.append(response)
                    all_responses.append(response)

                    debate_history.append({
                        "round": round_num + 1,
                        "model": model_id,
                        "content": response.content,
                    })

                except Exception as e:
                    logger.warning(f"Model {model_id} failed in round {round_num + 1}: {e}")

            # Add responses to messages for next round
            if round_responses and round_num < rounds - 1:
                for r in round_responses:
                    current_messages.append({
                        "role": "assistant",
                        "content": f"[{r.model}]: {r.content}",
                    })

                # Ask for follow-up
                current_messages.append({
                    "role": "user",
                    "content": "Consider the other perspectives and refine your answer.",
                })

        # Aggregate final round responses
        final_responses = all_responses[-len(models_to_use) :]
        result = self._aggregate(final_responses, AggregationStrategy.CONFIDENCE_WEIGHTED)

        # Add debate history to metadata
        result.metadata["debate_history"] = debate_history
        result.metadata["total_rounds"] = rounds

        return result
