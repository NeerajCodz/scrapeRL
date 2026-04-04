"""Comprehensive AI Provider Test Script
Tests NVIDIA, Groq, and Google Gemini providers with 10 different prompts.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.models.router import SmartModelRouter, TaskType


# Test prompts covering different use cases
TEST_PROMPTS = [
    {
        "name": "Code Generation",
        "prompt": "Write a Python function to calculate fibonacci numbers recursively.",
        "task_type": TaskType.CODE,
        "preferred_provider": "nvidia",
        "preferred_model": "llama-3.3-70b",
    },
    {
        "name": "Data Extraction",
        "prompt": "Extract the key information from this text: 'John Doe, age 35, lives in New York and works as a software engineer at Tech Corp since 2020.'",
        "task_type": TaskType.EXTRACTION,
        "preferred_provider": "groq",
        "preferred_model": "llama-3.3-70b-versatile",
    },
    {
        "name": "Reasoning Task",
        "prompt": "If a train travels 120 miles in 2 hours, and another train travels 180 miles in 3 hours, which train is faster and by how much?",
        "task_type": TaskType.REASONING,
        "preferred_provider": "nvidia",
        "preferred_model": "devstral-2-123b",
    },
    {
        "name": "General Question",
        "prompt": "What are the three primary colors?",
        "task_type": TaskType.GENERAL,
        "preferred_provider": "groq",
        "preferred_model": "llama-3.3-70b-versatile",
    },
    {
        "name": "JSON Generation",
        "prompt": "Generate a JSON object representing a user profile with name, email, age, and interests (array).",
        "task_type": TaskType.CODE,
        "preferred_provider": "nvidia",
        "preferred_model": "devstral-2-123b",
    },
    {
        "name": "Text Summarization",
        "prompt": "Summarize in one sentence: Artificial intelligence is transforming industries by automating tasks, improving decision-making, and creating new opportunities for innovation.",
        "task_type": TaskType.GENERAL,
        "preferred_provider": "groq",
        "preferred_model": "llama-3.3-70b-versatile",
    },
    {
        "name": "Math Problem",
        "prompt": "Solve: 2x + 5 = 15. Show your work.",
        "task_type": TaskType.REASONING,
        "preferred_provider": "nvidia",
        "preferred_model": "llama-3.3-70b",
    },
    {
        "name": "Creative Writing",
        "prompt": "Write a haiku about coding at night.",
        "task_type": TaskType.GENERAL,
        "preferred_provider": "nvidia",
        "preferred_model": "llama-3.3-70b",
    },
    {
        "name": "Code Debug",
        "prompt": "Find the bug in this code: def add(a, b): return a + b + 1",
        "task_type": TaskType.CODE,
        "preferred_provider": "groq",
        "preferred_model": "llama-3.3-70b-versatile",
    },
    {
        "name": "Complex Reasoning",
        "prompt": "If all roses are flowers, and some flowers fade quickly, can we conclude that some roses fade quickly?",
        "task_type": TaskType.REASONING,
        "preferred_provider": "nvidia",
        "preferred_model": "devstral-2-123b",
    },
]


class TestReporter:
    """Test reporter for generating markdown reports."""
    
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
        
    def start(self):
        """Mark test start time."""
        self.start_time = datetime.now()
        
    def end(self):
        """Mark test end time."""
        self.end_time = datetime.now()
        
    def add_result(self, test_case: dict, success: bool, response: str = None, 
                   error: str = None, duration: float = 0, metadata: dict = None):
        """Add a test result."""
        self.results.append({
            "test_name": test_case["name"],
            "prompt": test_case["prompt"],
            "task_type": test_case["task_type"].value,
            "preferred_provider": test_case.get("preferred_provider"),
            "preferred_model": test_case.get("preferred_model"),
            "success": success,
            "response": response,
            "error": error,
            "duration_seconds": duration,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        })
        
    def generate_markdown(self) -> str:
        """Generate markdown test report."""
        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total_tests - passed
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else None
        
        md = f"""# AI Provider Test Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Test Duration:** {total_duration.total_seconds():.2f}s  

## Summary

- **Total Tests:** {total_tests}
- **Passed:** ✅ {passed}
- **Failed:** ❌ {failed}
- **Success Rate:** {success_rate:.1f}%

## Test Results

"""
        
        for i, result in enumerate(self.results, 1):
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            md += f"### {i}. {result['test_name']} {status}\n\n"
            md += f"**Task Type:** {result['task_type']}  \n"
            md += f"**Provider:** {result['preferred_provider']}  \n"
            md += f"**Model:** {result['preferred_model']}  \n"
            md += f"**Duration:** {result['duration_seconds']:.2f}s  \n\n"
            
            md += f"**Prompt:**\n```\n{result['prompt']}\n```\n\n"
            
            if result["success"]:
                md += f"**Response:**\n```\n{result['response'][:500]}{'...' if len(result['response']) > 500 else ''}\n```\n\n"
                
                if result["metadata"]:
                    md += f"**Metadata:**\n"
                    for key, value in result["metadata"].items():
                        md += f"- {key}: {value}\n"
                    md += "\n"
            else:
                md += f"**Error:**\n```\n{result['error']}\n```\n\n"
            
            md += "---\n\n"
        
        # Provider summary
        md += "## Provider Performance\n\n"
        providers = {}
        for result in self.results:
            provider = result["preferred_provider"]
            if provider not in providers:
                providers[provider] = {"total": 0, "passed": 0, "total_duration": 0}
            providers[provider]["total"] += 1
            if result["success"]:
                providers[provider]["passed"] += 1
            providers[provider]["total_duration"] += result["duration_seconds"]
        
        md += "| Provider | Tests | Passed | Failed | Success Rate | Avg Duration |\n"
        md += "|----------|-------|--------|--------|--------------|-------------|\n"
        
        for provider, stats in sorted(providers.items()):
            success_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            avg_duration = stats["total_duration"] / stats["total"] if stats["total"] > 0 else 0
            md += f"| {provider} | {stats['total']} | {stats['passed']} | {stats['total'] - stats['passed']} | {success_rate:.1f}% | {avg_duration:.2f}s |\n"
        
        return md


async def run_tests():
    """Run all test cases."""
    print("="*80)
    print("AI Provider Comprehensive Test Suite")
    print("="*80)
    print()
    
    # Initialize settings and router
    settings = get_settings()
    print("Initializing model router...")
    print(f"  NVIDIA API Key: {'[SET]' if settings.nvidia_api_key else '[NOT SET]'}")
    print(f"  Groq API Key: {'[SET]' if settings.groq_api_key else '[NOT SET]'}")
    print(f"  Google API Key: {'[SET]' if settings.google_api_key else '[NOT SET]'}")
    print()
    
    router = SmartModelRouter(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        groq_api_key=settings.groq_api_key,
        nvidia_api_key=settings.nvidia_api_key,
    )
    await router.initialize()
    
    available_providers = [p for p in router.providers.keys()]
    print(f"Available providers: {', '.join(available_providers)}")
    print()
    
    reporter = TestReporter()
    reporter.start()
    
    # Run tests
    for i, test_case in enumerate(TEST_PROMPTS, 1):
        print(f"[{i}/{len(TEST_PROMPTS)}] Running: {test_case['name']}")
        print(f"  Provider: {test_case['preferred_provider']}")
        print(f"  Model: {test_case['preferred_model']}")
        print(f"  Task Type: {test_case['task_type'].value}")
        
        start_time = time.time()
        
        try:
            response = await router.complete(
                messages=[{"role": "user", "content": test_case["prompt"]}],
                model=test_case.get("preferred_model"),
                task_type=test_case["task_type"],
                fallback=False,  # No fallback - test only the requested model
                max_tokens=500,
                temperature=0.7,
            )
            
            duration = time.time() - start_time
            
            if response and response.content:
                print(f"  [OK] Success ({duration:.2f}s)")
                print(f"  Response: {response.content[:100]}...")
                
                reporter.add_result(
                    test_case=test_case,
                    success=True,
                    response=response.content,
                    duration=duration,
                    metadata={
                        "model_used": response.model,
                        "provider_used": response.provider,
                        "tokens": response.usage.total_tokens if response.usage else 0,
                    }
                )
            else:
                print(f"  [FAIL] Failed: Empty response")
                reporter.add_result(
                    test_case=test_case,
                    success=False,
                    error="Empty response from provider",
                    duration=duration,
                )
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"  [FAIL] Failed ({duration:.2f}s): {str(e)}")
            reporter.add_result(
                test_case=test_case,
                success=False,
                error=str(e),
                duration=duration,
            )
        
        print()
    
    reporter.end()
    
    # Generate report
    print("="*80)
    print("Generating test report...")
    
    report_md = reporter.generate_markdown()
    
    # Save report
    report_path = Path("docs/test/ai_provider_test_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")
    
    print(f"[OK] Report saved to: {report_path}")
    print()
    
    # Print summary
    total = len(reporter.results)
    passed = sum(1 for r in reporter.results if r["success"])
    failed = total - passed
    
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total}")
    print(f"Passed: [OK] {passed}")
    print(f"Failed: [X] {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    print("="*80)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    exit(0 if success else 1)
