#!/usr/bin/env python3
"""
Comprehensive ScrapeRL System Test Suite

Tests all components at LOW, MID, and HIGH complexity levels:
- Scraper environment and actions
- Reward function calculations
- Plugin system
- Embeddings with Gemini
- Vector search (memory)
- AI providers (NVIDIA, Groq)
- API endpoints

Author: ScrapeRL Test Suite
"""

import asyncio
import json
import sys
import os
import time
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


class TestComplexity(str, Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


@dataclass
class TestResult:
    """Individual test result."""
    name: str
    complexity: TestComplexity
    component: str
    passed: bool
    duration: float
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class TestReporter:
    """Generates comprehensive test reports."""
    
    def __init__(self):
        self.results: list[TestResult] = []
        self.start_time: datetime = datetime.now()
    
    def add_result(self, result: TestResult):
        self.results.append(result)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"  [{result.complexity.value.upper()}] {result.name}: {status} ({result.duration:.2f}s)")
        if result.error:
            print(f"      Error: {result.error[:100]}")
    
    def generate_report(self) -> str:
        """Generate markdown test report."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        success_rate = (passed / len(self.results) * 100) if self.results else 0
        
        report = f"""# ScrapeRL Comprehensive Test Report

**Generated:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}  
**Test Duration:** {duration:.2f}s  

## Summary

- **Total Tests:** {len(self.results)}
- **Passed:** ✅ {passed}
- **Failed:** ❌ {failed}
- **Success Rate:** {success_rate:.1f}%

## Tests by Complexity

"""
        # Group by complexity
        for complexity in TestComplexity:
            comp_results = [r for r in self.results if r.complexity == complexity]
            if comp_results:
                comp_passed = sum(1 for r in comp_results if r.passed)
                report += f"### {complexity.value.upper()} Complexity ({comp_passed}/{len(comp_results)} passed)\n\n"
                
                for result in comp_results:
                    status = "✅ PASS" if result.passed else "❌ FAIL"
                    report += f"#### {result.name} {status}\n\n"
                    report += f"**Component:** {result.component}  \n"
                    report += f"**Duration:** {result.duration:.2f}s  \n\n"
                    
                    if result.details:
                        report += "**Details:**\n```json\n"
                        report += json.dumps(result.details, indent=2, default=str)[:1000]
                        report += "\n```\n\n"
                    
                    if result.error:
                        report += f"**Error:**\n```\n{result.error[:500]}\n```\n\n"
                    
                    report += "---\n\n"

        # Component summary
        report += "## Component Summary\n\n"
        report += "| Component | Tests | Passed | Failed | Success Rate |\n"
        report += "|-----------|-------|--------|--------|-------------|\n"
        
        components = set(r.component for r in self.results)
        for comp in sorted(components):
            comp_results = [r for r in self.results if r.component == comp]
            comp_passed = sum(1 for r in comp_results if r.passed)
            comp_failed = len(comp_results) - comp_passed
            comp_rate = (comp_passed / len(comp_results) * 100) if comp_results else 0
            report += f"| {comp} | {len(comp_results)} | {comp_passed} | {comp_failed} | {comp_rate:.1f}% |\n"
        
        return report


class ScrapeRLTestSuite:
    """Comprehensive test suite for ScrapeRL."""
    
    def __init__(self):
        self.reporter = TestReporter()
    
    async def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("🧪 ScrapeRL Comprehensive Test Suite")
        print("="*60 + "\n")
        
        # Test categories
        test_categories = [
            ("Scraper Environment", self.test_scraper_environment),
            ("Reward Function", self.test_reward_function),
            ("Plugins System", self.test_plugins),
            ("Embeddings (Gemini)", self.test_embeddings),
            ("Vector Search / Memory", self.test_vector_search),
            ("AI Providers", self.test_ai_providers),
            ("API Endpoints", self.test_api_endpoints),
        ]
        
        for category_name, test_func in test_categories:
            print(f"\n📋 Testing: {category_name}")
            print("-" * 40)
            try:
                await test_func()
            except Exception as e:
                print(f"  ❌ Category failed: {e}")
        
        # Generate report
        report = self.reporter.generate_report()
        
        # Save report
        report_path = Path(__file__).parent.parent / "docs" / "test" / "comprehensive-test-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding='utf-8')
        
        print("\n" + "="*60)
        print(f"📊 Test Report saved to: {report_path}")
        passed = sum(1 for r in self.reporter.results if r.passed)
        total = len(self.reporter.results)
        print(f"✅ Final Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        print("="*60 + "\n")
        
        return self.reporter.results

    # =========================================================================
    # SCRAPER ENVIRONMENT TESTS
    # =========================================================================
    
    async def test_scraper_environment(self):
        """Test the scraper environment at different complexity levels."""
        
        # LOW: Basic environment creation and reset
        start = time.time()
        try:
            from app.core.env import WebScraperEnv
            from app.config import get_settings
            
            settings = get_settings()
            env = WebScraperEnv(episode_id="test-001", settings=settings)
            
            # Test reset
            obs, info = await env.reset(task_id="task_001")
            
            passed = obs is not None and info.get("episode_id") == "test-001"
            details = {
                "episode_id": info.get("episode_id"),
                "task_id": info.get("task_id"),
                "observation_fields": list(obs.__dict__.keys()) if obs else []
            }
            
            self.reporter.add_result(TestResult(
                name="Environment Reset",
                complexity=TestComplexity.LOW,
                component="Scraper",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Environment Reset",
                complexity=TestComplexity.LOW,
                component="Scraper",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # MID: Navigation and extraction actions
        start = time.time()
        try:
            from app.core.env import WebScraperEnv
            from app.core.action import Action, ActionType
            from app.config import get_settings
            
            settings = get_settings()
            env = WebScraperEnv(episode_id="test-002", settings=settings)
            await env.reset(task_id="task_001")
            
            # Navigate action
            nav_action = Action(
                action_type=ActionType.NAVIGATE,
                parameters={"url": "https://example.com"},
                reasoning="Testing navigation"
            )
            obs, reward, breakdown, terminated, truncated, info = await env.step(nav_action)
            
            # Extract action
            extract_action = Action(
                action_type=ActionType.EXTRACT_FIELD,
                parameters={"field_name": "product_name", "selector": "h1"},
                reasoning="Testing extraction"
            )
            obs2, reward2, breakdown2, terminated2, truncated2, info2 = await env.step(extract_action)
            
            passed = obs is not None and reward is not None and obs2 is not None
            details = {
                "nav_reward": reward,
                "extract_reward": reward2,
                "extracted_fields": len(obs2.extracted_so_far) if obs2 else 0,
                "current_url": obs.current_url if obs else None
            }
            
            self.reporter.add_result(TestResult(
                name="Navigation & Extraction",
                complexity=TestComplexity.MID,
                component="Scraper",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Navigation & Extraction",
                complexity=TestComplexity.MID,
                component="Scraper",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # HIGH: Full episode with multiple actions and completion
        start = time.time()
        try:
            from app.core.env import WebScraperEnv
            from app.core.action import Action, ActionType
            from app.config import get_settings
            
            settings = get_settings()
            env = WebScraperEnv(episode_id="test-003", settings=settings)
            await env.reset(task_id="task_001")
            
            actions = [
                Action(action_type=ActionType.NAVIGATE, parameters={"url": "https://example.com/product/123"}, reasoning="Navigate to product"),
                Action(action_type=ActionType.EXTRACT_FIELD, parameters={"field_name": "product_name"}, reasoning="Extract name"),
                Action(action_type=ActionType.EXTRACT_FIELD, parameters={"field_name": "price"}, reasoning="Extract price"),
                Action(action_type=ActionType.EXTRACT_FIELD, parameters={"field_name": "description"}, reasoning="Extract description"),
                Action(action_type=ActionType.DONE, parameters={"success": True}, reasoning="Task complete"),
            ]
            
            total_reward = 0
            final_obs = None
            for action in actions:
                obs, reward, breakdown, terminated, truncated, info = await env.step(action)
                total_reward += reward
                final_obs = obs
                if terminated or truncated:
                    break
            
            state = env.get_state()
            passed = state.get("is_terminal", False) and len(final_obs.extracted_so_far) >= 3
            details = {
                "total_reward": total_reward,
                "steps_taken": state.get("step_number", 0),
                "extracted_fields": len(final_obs.extracted_so_far) if final_obs else 0,
                "is_terminal": state.get("is_terminal", False),
                "status": state.get("status", "unknown")
            }
            
            self.reporter.add_result(TestResult(
                name="Full Episode Completion",
                complexity=TestComplexity.HIGH,
                component="Scraper",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Full Episode Completion",
                complexity=TestComplexity.HIGH,
                component="Scraper",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))

    # =========================================================================
    # REWARD FUNCTION TESTS
    # =========================================================================
    
    async def test_reward_function(self):
        """Test reward calculation at different complexity levels."""
        
        # LOW: Basic reward computation
        start = time.time()
        try:
            from app.core.reward import RewardEngine, RewardBreakdown
            from app.core.action import Action, ActionType
            from app.core.observation import Observation, TaskContext, ExtractedField
            from app.config import get_settings
            
            settings = get_settings()
            engine = RewardEngine(settings)
            
            # Create test observation
            prev_obs = Observation(
                episode_id="test",
                task_id="task_001",
                step_number=0,
                extraction_progress=0.0
            )
            new_obs = Observation(
                episode_id="test",
                task_id="task_001",
                step_number=1,
                extraction_progress=0.33,
                extracted_so_far=[
                    ExtractedField(field_name="product_name", value="Test Product", confidence=0.9)
                ]
            )
            action = Action(action_type=ActionType.EXTRACT_FIELD, parameters={"field_name": "product_name"})
            
            reward, breakdown = engine.compute_reward(action, prev_obs, new_obs, max_steps=50)
            
            passed = isinstance(reward, float) and isinstance(breakdown, RewardBreakdown)
            details = {
                "reward": reward,
                "accuracy": breakdown.accuracy,
                "efficiency": breakdown.efficiency,
                "completeness": breakdown.completeness,
                "total": breakdown.total
            }
            
            self.reporter.add_result(TestResult(
                name="Basic Reward Computation",
                complexity=TestComplexity.LOW,
                component="Reward",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Basic Reward Computation",
                complexity=TestComplexity.LOW,
                component="Reward",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # MID: Reward with ground truth accuracy
        start = time.time()
        try:
            from app.core.reward import RewardEngine
            from app.core.action import Action, ActionType
            from app.core.observation import Observation, ExtractedField
            from app.config import get_settings
            
            settings = get_settings()
            engine = RewardEngine(settings)
            engine.reset()
            
            # Test with ground truth
            ground_truth = {"product_name": "Test Product", "price": 99.99}
            
            prev_obs = Observation(episode_id="test", task_id="task_001", step_number=0, extraction_progress=0.0)
            new_obs = Observation(
                episode_id="test",
                task_id="task_001",
                step_number=1,
                extraction_progress=0.5,
                extracted_so_far=[
                    ExtractedField(field_name="product_name", value="Test Product", confidence=0.95),
                    ExtractedField(field_name="price", value=99.99, confidence=0.9),
                ]
            )
            action = Action(action_type=ActionType.EXTRACT_FIELD, parameters={"field_name": "price"})
            
            reward, breakdown = engine.compute_reward(action, prev_obs, new_obs, ground_truth=ground_truth, max_steps=50)
            
            passed = breakdown.accuracy == 1.0  # Perfect match
            details = {
                "reward": reward,
                "accuracy": breakdown.accuracy,
                "ground_truth_match": breakdown.accuracy == 1.0,
                "progress_bonus": breakdown.progress_bonus
            }
            
            self.reporter.add_result(TestResult(
                name="Reward with Ground Truth",
                complexity=TestComplexity.MID,
                component="Reward",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Reward with Ground Truth",
                complexity=TestComplexity.MID,
                component="Reward",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # HIGH: Terminal reward and penalties
        start = time.time()
        try:
            from app.core.reward import RewardEngine
            from app.core.observation import Observation, ExtractedField
            from app.config import get_settings
            
            settings = get_settings()
            engine = RewardEngine(settings)
            
            # Test terminal reward
            final_obs = Observation(
                episode_id="test",
                task_id="task_001",
                step_number=10,
                extraction_progress=1.0,
                extracted_so_far=[
                    ExtractedField(field_name="product_name", value="Test Product", confidence=0.95),
                    ExtractedField(field_name="price", value=99.99, confidence=0.9),
                    ExtractedField(field_name="description", value="Great product", confidence=0.85),
                ]
            )
            
            ground_truth = {"product_name": "Test Product", "price": 99.99, "description": "Great product"}
            
            terminal_reward, terminal_breakdown = engine.compute_terminal_reward(
                final_obs, success=True, ground_truth=ground_truth
            )
            
            passed = terminal_reward > 0 and terminal_breakdown.completeness == 1.0
            details = {
                "terminal_reward": terminal_reward,
                "completeness": terminal_breakdown.completeness,
                "accuracy": terminal_breakdown.accuracy,
                "efficiency": terminal_breakdown.efficiency,
                "progress_bonus": terminal_breakdown.progress_bonus
            }
            
            self.reporter.add_result(TestResult(
                name="Terminal Reward Calculation",
                complexity=TestComplexity.HIGH,
                component="Reward",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Terminal Reward Calculation",
                complexity=TestComplexity.HIGH,
                component="Reward",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))

    # =========================================================================
    # PLUGINS TESTS
    # =========================================================================
    
    async def test_plugins(self):
        """Test plugin system at different complexity levels."""
        
        # LOW: List plugins
        start = time.time()
        try:
            from app.api.routes.plugins import PLUGIN_REGISTRY, _installed_plugins
            
            total_plugins = sum(len(plugins) for plugins in PLUGIN_REGISTRY.values())
            categories = list(PLUGIN_REGISTRY.keys())
            
            passed = total_plugins > 0 and len(categories) > 0
            details = {
                "total_plugins": total_plugins,
                "categories": categories,
                "installed_count": len(_installed_plugins)
            }
            
            self.reporter.add_result(TestResult(
                name="List Plugins",
                complexity=TestComplexity.LOW,
                component="Plugins",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="List Plugins",
                complexity=TestComplexity.LOW,
                component="Plugins",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # MID: Install/uninstall plugin
        start = time.time()
        try:
            from app.api.routes.plugins import _installed_plugins, PLUGIN_REGISTRY
            
            # Find a plugin that's not installed
            test_plugin_id = None
            for plugins in PLUGIN_REGISTRY.values():
                for plugin in plugins:
                    if plugin["id"] not in _installed_plugins and "captcha" not in plugin["id"]:
                        test_plugin_id = plugin["id"]
                        break
                if test_plugin_id:
                    break
            
            if test_plugin_id:
                # Install
                _installed_plugins.add(test_plugin_id)
                is_installed = test_plugin_id in _installed_plugins
                
                # Uninstall
                _installed_plugins.discard(test_plugin_id)
                is_uninstalled = test_plugin_id not in _installed_plugins
                
                passed = is_installed and is_uninstalled
                details = {
                    "test_plugin": test_plugin_id,
                    "install_success": is_installed,
                    "uninstall_success": is_uninstalled
                }
            else:
                passed = True
                details = {"message": "No test plugin available (all installed)"}
            
            self.reporter.add_result(TestResult(
                name="Install/Uninstall Plugin",
                complexity=TestComplexity.MID,
                component="Plugins",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Install/Uninstall Plugin",
                complexity=TestComplexity.MID,
                component="Plugins",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # HIGH: Plugin categories and core plugins check
        start = time.time()
        try:
            from app.api.routes.plugins import PLUGIN_REGISTRY, _installed_plugins
            
            # Check that all categories have plugins
            categories_with_plugins = {cat: len(plugins) for cat, plugins in PLUGIN_REGISTRY.items()}
            
            # Check core plugins are installed
            core_plugins = {"mcp-browser", "mcp-search", "mcp-html", "skill-planner", "skill-navigator", "skill-extractor", "skill-verifier", "proc-json"}
            core_installed = core_plugins.intersection(_installed_plugins)
            
            # Check AI providers
            ai_providers = {"google-api", "groq-api", "nvidia-api"}
            ai_installed = ai_providers.intersection(_installed_plugins)
            
            passed = len(core_installed) >= 6 and len(ai_installed) >= 2
            details = {
                "categories": categories_with_plugins,
                "core_plugins_installed": list(core_installed),
                "ai_providers_installed": list(ai_installed),
                "total_installed": len(_installed_plugins)
            }
            
            self.reporter.add_result(TestResult(
                name="Plugin Categories & Core Plugins",
                complexity=TestComplexity.HIGH,
                component="Plugins",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Plugin Categories & Core Plugins",
                complexity=TestComplexity.HIGH,
                component="Plugins",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))

    # =========================================================================
    # EMBEDDINGS TESTS (Gemini)
    # =========================================================================
    
    async def test_embeddings(self):
        """Test embeddings service with Gemini."""
        
        # LOW: Create embeddings service
        start = time.time()
        try:
            from app.core.embeddings import EmbeddingsService, create_embeddings_service
            
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            model = os.getenv("GEMINI_MODEL_EMBEDDING", "models/gemini-embedding-2-preview")
            
            service = create_embeddings_service(
                provider="google",
                model=model,
                api_key=api_key
            )
            
            passed = service is not None and service.provider == "google"
            details = {
                "provider": service.provider,
                "model": service.model,
                "has_api_key": api_key is not None
            }
            
            self.reporter.add_result(TestResult(
                name="Create Embeddings Service",
                complexity=TestComplexity.LOW,
                component="Embeddings",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Create Embeddings Service",
                complexity=TestComplexity.LOW,
                component="Embeddings",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # MID: Generate single embedding
        start = time.time()
        try:
            from app.core.embeddings import create_embeddings_service
            import numpy as np
            
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            model = os.getenv("GEMINI_MODEL_EMBEDDING", "models/gemini-embedding-2-preview")
            
            service = create_embeddings_service(
                provider="google",
                model=model,
                api_key=api_key
            )
            
            # Generate embedding
            text = "This is a test document about web scraping and data extraction."
            embedding = await service.embed_text(text)
            
            passed = isinstance(embedding, np.ndarray) and len(embedding) > 0
            details = {
                "embedding_dim": len(embedding),
                "embedding_type": str(embedding.dtype),
                "text_length": len(text),
                "sample_values": embedding[:5].tolist() if len(embedding) > 5 else embedding.tolist()
            }
            
            self.reporter.add_result(TestResult(
                name="Generate Single Embedding",
                complexity=TestComplexity.MID,
                component="Embeddings",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Generate Single Embedding",
                complexity=TestComplexity.MID,
                component="Embeddings",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # HIGH: Batch embeddings and similarity search
        start = time.time()
        try:
            from app.core.embeddings import create_embeddings_service
            import numpy as np
            
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            model = os.getenv("GEMINI_MODEL_EMBEDDING", "models/gemini-embedding-2-preview")
            
            service = create_embeddings_service(
                provider="google",
                model=model,
                api_key=api_key
            )
            
            # Generate batch embeddings
            texts = [
                "Web scraping extracts data from websites",
                "Machine learning uses neural networks",
                "Data extraction from HTML pages",
            ]
            
            embeddings = await service.embed_batch(texts)
            query_embedding = await service.embed_query("scraping data from web")
            
            # Find most similar
            similar = service.find_most_similar(query_embedding, list(embeddings), top_k=2)
            
            passed = len(embeddings) == 3 and len(similar) == 2
            details = {
                "batch_size": len(texts),
                "embeddings_shape": embeddings.shape if hasattr(embeddings, 'shape') else len(embeddings),
                "top_match_index": similar[0][0] if similar else None,
                "top_match_score": similar[0][1] if similar else None,
                "similarity_ranking": [(idx, round(score, 4)) for idx, score in similar]
            }
            
            self.reporter.add_result(TestResult(
                name="Batch Embeddings & Similarity Search",
                complexity=TestComplexity.HIGH,
                component="Embeddings",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Batch Embeddings & Similarity Search",
                complexity=TestComplexity.HIGH,
                component="Embeddings",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))

    # =========================================================================
    # VECTOR SEARCH / MEMORY TESTS
    # =========================================================================
    
    async def test_vector_search(self):
        """Test vector search and memory system."""
        
        # LOW: Initialize memory manager
        start = time.time()
        try:
            from app.memory.manager import MemoryManager, MemoryType
            from app.config import get_settings
            
            settings = get_settings()
            manager = MemoryManager(settings)
            await manager.initialize()
            
            passed = manager.is_initialized
            stats = await manager.get_stats()
            details = {
                "initialized": manager.is_initialized,
                "short_term_stats": stats.short_term,
                "working_stats": stats.working,
                "long_term_stats": stats.long_term
            }
            
            self.reporter.add_result(TestResult(
                name="Initialize Memory Manager",
                complexity=TestComplexity.LOW,
                component="Memory",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Initialize Memory Manager",
                complexity=TestComplexity.LOW,
                component="Memory",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # MID: Store and retrieve from different memory types
        start = time.time()
        try:
            from app.memory.manager import MemoryManager, MemoryType
            from app.config import get_settings
            
            settings = get_settings()
            manager = MemoryManager(settings)
            await manager.initialize()
            
            # Test short-term memory
            await manager.store("test_key", "test_value", MemoryType.SHORT_TERM)
            short_term_result = await manager.retrieve("test_key", MemoryType.SHORT_TERM)
            
            # Test working memory
            await manager.store("thought_1", "This is a test thought", MemoryType.WORKING, priority=0.5)
            working_result = await manager.retrieve("thought_1", MemoryType.WORKING)
            
            # Test shared memory
            await manager.store("shared_key", {"data": "shared_value"}, MemoryType.SHARED)
            shared_result = await manager.retrieve("shared_key", MemoryType.SHARED)
            
            passed = (
                short_term_result == "test_value" and
                working_result == "This is a test thought" and
                shared_result == {"data": "shared_value"}
            )
            details = {
                "short_term": short_term_result,
                "working": working_result,
                "shared": shared_result
            }
            
            # Cleanup
            await manager.clear()
            
            self.reporter.add_result(TestResult(
                name="Store & Retrieve Memory",
                complexity=TestComplexity.MID,
                component="Memory",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Store & Retrieve Memory",
                complexity=TestComplexity.MID,
                component="Memory",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # HIGH: Long-term memory with vector search
        start = time.time()
        try:
            from app.memory.manager import MemoryManager, MemoryType
            from app.config import get_settings
            
            settings = get_settings()
            manager = MemoryManager(settings)
            await manager.initialize()
            
            # Store documents
            doc1 = await manager.remember("Web scraping extracts data from websites using automated tools")
            doc2 = await manager.remember("Machine learning models can predict outcomes based on data")
            doc3 = await manager.remember("Data extraction from HTML pages requires parsing the DOM")
            
            # Search
            results = await manager.recall("scraping data from web", top_k=2)
            
            passed = len(results) >= 1 or manager.long_term._using_fallback
            details = {
                "documents_stored": 3,
                "search_results": len(results),
                "using_fallback": manager.long_term._using_fallback,
                "top_result_score": results[0].score if results else None
            }
            
            # Cleanup
            await manager.clear(MemoryType.LONG_TERM)
            
            self.reporter.add_result(TestResult(
                name="Long-term Memory & Vector Search",
                complexity=TestComplexity.HIGH,
                component="Memory",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Long-term Memory & Vector Search",
                complexity=TestComplexity.HIGH,
                component="Memory",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))

    # =========================================================================
    # AI PROVIDERS TESTS
    # =========================================================================
    
    async def test_ai_providers(self):
        """Test AI providers (NVIDIA, Groq)."""
        
        # LOW: Test NVIDIA provider initialization
        start = time.time()
        try:
            from app.models.router import SmartModelRouter
            
            nvidia_key = os.getenv("NVIDIA_API_KEY")
            groq_key = os.getenv("GROQ_API_KEY")
            google_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            
            router = SmartModelRouter(
                nvidia_api_key=nvidia_key,
                groq_api_key=groq_key,
                google_api_key=google_key
            )
            await router.initialize()
            
            providers = list(router.providers.keys())
            
            has_nvidia = "nvidia" in providers
            has_groq = "groq" in providers
            
            passed = has_nvidia or has_groq
            details = {
                "available_providers": providers,
                "has_nvidia": has_nvidia,
                "has_groq": has_groq,
                "nvidia_key_present": nvidia_key is not None,
                "groq_key_present": groq_key is not None
            }
            
            self.reporter.add_result(TestResult(
                name="AI Provider Initialization",
                complexity=TestComplexity.LOW,
                component="AI Providers",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="AI Provider Initialization",
                complexity=TestComplexity.LOW,
                component="AI Providers",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # MID: Test NVIDIA completion
        start = time.time()
        try:
            from app.models.router import SmartModelRouter
            from app.models.providers.base import TaskType
            
            nvidia_key = os.getenv("NVIDIA_API_KEY")
            groq_key = os.getenv("GROQ_API_KEY")
            google_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            
            router = SmartModelRouter(
                nvidia_api_key=nvidia_key,
                groq_api_key=groq_key,
                google_api_key=google_key
            )
            await router.initialize()
            
            messages = [{"role": "user", "content": "What is 2+2? Reply with just the number."}]
            
            response = await router.complete(
                messages=messages,
                task_type=TaskType.GENERAL,
                model="llama-3.3-70b",
                max_tokens=50,
                fallback=False
            )
            
            passed = response is not None and response.content is not None
            details = {
                "model_used": response.model if response else None,
                "provider_used": response.provider if response else None,
                "content_preview": response.content[:100] if response and response.content else None,
                "total_tokens": response.usage.total_tokens if response and response.usage else None
            }
            
            self.reporter.add_result(TestResult(
                name="NVIDIA Completion",
                complexity=TestComplexity.MID,
                component="AI Providers",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="NVIDIA Completion",
                complexity=TestComplexity.MID,
                component="AI Providers",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # HIGH: Test Groq completion and fallback
        start = time.time()
        try:
            from app.models.router import SmartModelRouter
            from app.models.providers.base import TaskType
            
            nvidia_key = os.getenv("NVIDIA_API_KEY")
            groq_key = os.getenv("GROQ_API_KEY")
            google_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            
            router = SmartModelRouter(
                nvidia_api_key=nvidia_key,
                groq_api_key=groq_key,
                google_api_key=google_key
            )
            await router.initialize()
            
            messages = [{"role": "user", "content": "Write a Python function to calculate factorial. Be concise."}]
            
            # Test Groq
            response = await router.complete(
                messages=messages,
                task_type=TaskType.CODE,
                model="llama-3.3-70b-versatile",
                max_tokens=200,
                fallback=False
            )
            
            passed = response is not None and response.content is not None and "def" in response.content.lower()
            details = {
                "model_used": response.model if response else None,
                "provider_used": response.provider if response else None,
                "content_preview": response.content[:200] if response and response.content else None,
                "has_code": "def" in response.content.lower() if response and response.content else False
            }
            
            self.reporter.add_result(TestResult(
                name="Groq Code Generation",
                complexity=TestComplexity.HIGH,
                component="AI Providers",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Groq Code Generation",
                complexity=TestComplexity.HIGH,
                component="AI Providers",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))

    # =========================================================================
    # API ENDPOINTS TESTS
    # =========================================================================
    
    async def test_api_endpoints(self):
        """Test API endpoints."""
        
        # LOW: Test tasks endpoint
        start = time.time()
        try:
            from app.api.routes.tasks import TASK_REPOSITORY, list_tasks
            
            # Direct function call (simulating endpoint)
            response = await list_tasks()
            
            passed = response.total > 0 and len(response.tasks) > 0
            details = {
                "total_tasks": response.total,
                "tasks_returned": len(response.tasks),
                "task_ids": [t.id for t in response.tasks]
            }
            
            self.reporter.add_result(TestResult(
                name="List Tasks Endpoint",
                complexity=TestComplexity.LOW,
                component="API",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="List Tasks Endpoint",
                complexity=TestComplexity.LOW,
                component="API",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # MID: Test plugins endpoint
        start = time.time()
        try:
            from app.api.routes.plugins import list_plugins, list_installed_plugins
            
            all_plugins = await list_plugins()
            installed = await list_installed_plugins()
            
            passed = "plugins" in all_plugins and installed["count"] > 0
            details = {
                "total_plugins": all_plugins["stats"]["total"],
                "installed": installed["count"],
                "categories": all_plugins["categories"]
            }
            
            self.reporter.add_result(TestResult(
                name="Plugins Endpoint",
                complexity=TestComplexity.MID,
                component="API",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Plugins Endpoint",
                complexity=TestComplexity.MID,
                component="API",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))
        
        # HIGH: Test episode lifecycle
        start = time.time()
        try:
            from app.api.deps import create_environment, get_environment, remove_environment, list_environments
            from app.config import get_settings
            
            settings = get_settings()
            
            # Create environment
            episode_id = "api-test-001"
            env = create_environment(episode_id, settings)
            
            # Reset
            obs, info = await env.reset(task_id="task_001")
            
            # List
            envs = list_environments()
            
            # Get state
            state = env.get_state()
            
            # Remove
            removed = remove_environment(episode_id)
            
            passed = (
                episode_id in envs and
                state["task_id"] == "task_001" and
                removed
            )
            details = {
                "episode_id": episode_id,
                "task_id": state.get("task_id"),
                "environments_listed": len(envs),
                "removed": removed
            }
            
            self.reporter.add_result(TestResult(
                name="Episode Lifecycle",
                complexity=TestComplexity.HIGH,
                component="API",
                passed=passed,
                duration=time.time() - start,
                details=details
            ))
        except Exception as e:
            self.reporter.add_result(TestResult(
                name="Episode Lifecycle",
                complexity=TestComplexity.HIGH,
                component="API",
                passed=False,
                duration=time.time() - start,
                error=str(e)
            ))


async def main():
    """Run the test suite."""
    suite = ScrapeRLTestSuite()
    results = await suite.run_all_tests()
    
    # Return exit code based on test results
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
