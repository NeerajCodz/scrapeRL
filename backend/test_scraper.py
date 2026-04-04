"""Test script to verify scraper functionality end-to-end."""

import asyncio
import json
import logging
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api"


async def test_scraper():
    """Test the scraper with a simple task."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Create a scraping task
        logger.info("Creating scraping episode...")
        
        reset_payload = {
            "task_id": "test-scrape-quotes",
            "seed": 42,
            "config": {
                "start_url": "http://quotes.toscrape.com",
                "target_fields": {
                    "quotes": {
                        "text": "quote text",
                        "author": "quote author",
                        "tags": "quote tags"
                    }
                },
                "max_steps": 20,
                "timeout": 300
            }
        }
        
        try:
            response = await client.post(f"{BASE_URL}/episode/reset", json=reset_payload)
            response.raise_for_status()
            reset_data = response.json()
            episode_id = reset_data["episode_id"]
            logger.info(f"✓ Episode created: {episode_id}")
            logger.info(f"  Initial observation: {reset_data['observation']['current_url']}")
            
        except Exception as e:
            logger.error(f"✗ Failed to create episode: {e}")
            if hasattr(e, 'response'):
                logger.error(f"  Response: {e.response.text}")
            return
        
        # Step 2: Execute a few actions
        actions = [
            {
                "action_type": "navigate",
                "parameters": {"url": "http://quotes.toscrape.com"},
                "reasoning": "Navigate to the quotes website to start scraping",
            },
            {
                "action_type": "extract_field",
                "parameters": {
                    "field_name": "quotes",
                    "css_selector": ".quote .text"
                },
                "reasoning": "Extract all quotes from the page",
            },
            {
                "action_type": "done",
                "parameters": {"success": True},
                "reasoning": "Extraction complete",
            }
        ]
        
        for i, action_data in enumerate(actions, 1):
            logger.info(f"\nStep {i}: {action_data['action_type']}")
            
            step_payload = {
                "episode_id": episode_id,
                "action": action_data
            }
            
            try:
                response = await client.post(f"{BASE_URL}/episode/step", json=step_payload)
                response.raise_for_status()
                step_data = response.json()
                
                logger.info(f"✓ Action executed successfully")
                logger.info(f"  Reward: {step_data['reward']:.2f}")
                logger.info(f"  Progress: {step_data['observation'].get('extraction_progress', 0):.1f}%")
                logger.info(f"  Terminated: {step_data['terminated']}")
                
                if step_data.get('reward_breakdown'):
                    logger.info(f"  Reward breakdown:")
                    for key, value in step_data['reward_breakdown'].items():
                        if isinstance(value, (int, float)):
                            logger.info(f"    {key}: {value:.2f}")
                
                if step_data['terminated'] or step_data['truncated']:
                    logger.info("\nEpisode finished!")
                    break
                    
            except Exception as e:
                logger.error(f"✗ Step {i} failed: {e}")
                if hasattr(e, 'response'):
                    logger.error(f"  Response: {e.response.text}")
                break
        
        # Step 3: Get final state
        logger.info("\n" + "="*60)
        logger.info("Fetching final episode state...")
        
        try:
            response = await client.get(f"{BASE_URL}/episode/state/{episode_id}")
            response.raise_for_status()
            state_data = response.json()
            
            logger.info(f"✓ Final state retrieved")
            logger.info(f"  Episode ID: {state_data.get('episode_id', 'N/A')}")
            logger.info(f"  Steps: {state_data.get('step_number', 0)}")
            logger.info(f"  Total reward: {state_data.get('total_reward', 0.0):.2f}")
            logger.info(f"  Terminal: {state_data.get('is_terminal', False)}")
            logger.info(f"  Extracted data: {json.dumps(state_data.get('extracted_data', {}), indent=2)}")
            
        except Exception as e:
            logger.error(f"✗ Failed to get state: {e}")


async def test_websocket():
    """Test WebSocket connectivity (just connect, not full test)."""
    logger.info("\n" + "="*60)
    logger.info("Testing WebSocket endpoint...")
    
    try:
        # Just verify the endpoint exists
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/docs")
            if response.status_code == 200:
                logger.info("✓ API docs accessible at http://localhost:8000/docs")
                logger.info("  WebSocket endpoint: ws://localhost:8000/ws/episode/{episode_id}")
    except Exception as e:
        logger.error(f"✗ Failed to check docs: {e}")


async def main():
    """Run all tests."""
    logger.info("="*60)
    logger.info("ScrapeRL End-to-End Test")
    logger.info("="*60)
    
    await test_scraper()
    await test_websocket()
    
    logger.info("\n" + "="*60)
    logger.info("Testing complete!")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
