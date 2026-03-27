"""Tests for agent coordinator."""

import pytest
from app.agents.coordinator import AgentCoordinator
from app.agents.planner import PlannerAgent
from app.agents.navigator import NavigatorAgent
from app.agents.extractor import ExtractorAgent
from app.agents.verifier import VerifierAgent


def test_coordinator_creation() -> None:
    """Test creating agent coordinator."""
    coordinator = AgentCoordinator()
    assert coordinator is not None


def test_agent_registration() -> None:
    """Test registering agents with coordinator."""
    coordinator = AgentCoordinator()
    planner = PlannerAgent("planner_1")
    
    coordinator.register_agent("custom_planner", planner)
    assert coordinator.get_agent("custom_planner") is planner


def test_all_agents_instantiation() -> None:
    """Test all agent types can be instantiated."""
    planner = PlannerAgent("planner")
    navigator = NavigatorAgent("navigator")
    extractor = ExtractorAgent("extractor")
    verifier = VerifierAgent("verifier")
    
    assert planner.agent_id == "planner"
    assert navigator.agent_id == "navigator"
    assert extractor.agent_id == "extractor"
    assert verifier.agent_id == "verifier"
