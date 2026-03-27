"""Tests for reward computation."""

import pytest
from app.core.reward import RewardEngine, RewardBreakdown


def test_reward_engine_creation() -> None:
    """Test creating reward engine."""
    engine = RewardEngine()
    assert engine is not None


def test_reward_breakdown() -> None:
    """Test reward breakdown structure."""
    breakdown = RewardBreakdown(
        accuracy=0.8,
        efficiency=0.6,
        cost=-0.1,
        total=0.7,
    )
    assert breakdown.total == 0.7
    assert breakdown.accuracy == 0.8
