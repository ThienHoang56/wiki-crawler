#!/usr/bin/env python3
"""
Script to take screenshots of FastAPI Swagger UI endpoints
"""
import asyncio
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

async def take_screenshots():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        try:
            # Task 1: Navigate to Swagger UI and take overview screenshot
            print("Task 1: Taking screenshot of Swagger UI overview...")
            await page.goto('http://localhost:8001/docs', wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)  # Wait for page to fully render
            await page.screenshot(path='/home/thiennlh3/project/wiki-crawler/rag-demo/screenshots/01_api_overview.png', full_page=True)
            print("✓ Saved: rag-demo/screenshots/01_api_overview.png")
            
            # Task 2: Test POST /api/v1/search/ask endpoint
            print("\nTask 2: Testing RAG search endpoint...")
            
            # Find and expand the search/ask endpoint
            search_endpoint = page.get_by_text('/api/v1/search/ask', exact=True).first
            await search_endpoint.scroll_into_view_if_needed()
            await search_endpoint.click()
            await page.wait_for_timeout(1000)
            
            # Click "Try it out" button
            try_it_out = page.locator('button:has-text("Try it out")').first
            await try_it_out.click()
            await page.wait_for_timeout(500)
            
            # Find the request body textarea and fill it
            request_body = '{"query": "What is machine learning and how does it work?", "top_k": 3, "model": "gemini-2.5-flash"}'
            textarea = page.locator('textarea[class*="body-param"]').first
            await textarea.fill(request_body)
            await page.wait_for_timeout(500)
            
            # Click Execute button
            execute_button = page.locator('button:has-text("Execute")').first
            await execute_button.click()
            print("  Waiting for response (up to 30s)...")
            
            # Wait for response - look for response section
            try:
                await page.wait_for_selector('.responses-wrapper .response', timeout=30000)
                await page.wait_for_timeout(2000)  # Extra time for content to render
            except PlaywrightTimeout:
                print("  Warning: Response timeout, taking screenshot anyway...")
            
            # Scroll to response and take screenshot
            response_section = page.locator('.responses-wrapper').first
            await response_section.scroll_into_view_if_needed()
            await page.screenshot(path='/home/thiennlh3/project/wiki-crawler/rag-demo/screenshots/04_rag_answer.png', full_page=True)
            print("✓ Saved: rag-demo/screenshots/04_rag_answer.png")
            
            # Task 3: Test POST /api/v1/agent/chat endpoint (first call)
            print("\nTask 3: Testing agent chat endpoint (first call)...")
            
            # Navigate fresh to the page to reset state
            await page.goto('http://localhost:8001/docs', wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Find and expand the agent/chat endpoint
            agent_endpoint = page.get_by_text('/api/v1/agent/chat', exact=True).first
            await agent_endpoint.scroll_into_view_if_needed()
            await agent_endpoint.click()
            await page.wait_for_timeout(1000)
            
            # Find the operation div that contains this endpoint
            agent_operation = page.locator('.opblock').filter(has_text='/api/v1/agent/chat').first
            
            # Click "Try it out" button within this operation
            try_it_out_agent = agent_operation.locator('button:has-text("Try it out")').first
            await try_it_out_agent.click()
            await page.wait_for_timeout(500)
            
            # Fill request body for agent within this operation
            agent_request_body = '{"message": "What is machine learning?", "session_id": "demo-session"}'
            textarea_agent = agent_operation.locator('textarea').first
            await textarea_agent.fill(agent_request_body)
            await page.wait_for_timeout(500)
            
            # Click Execute button within this operation
            execute_button_agent = agent_operation.locator('button:has-text("Execute")').first
            await execute_button_agent.click()
            print("  Waiting for agent response (up to 60s)...")
            
            # Wait for agent response
            # Agent calls can take 10-20 seconds, so wait generously
            await page.wait_for_timeout(15000)
            print("  Response should be ready...")
            
            # Take screenshot of agent response
            await page.screenshot(path='/home/thiennlh3/project/wiki-crawler/agent/screenshots/03_agent_api_endpoint.png', full_page=True)
            print("✓ Saved: agent/screenshots/03_agent_api_endpoint.png")
            
            # Task 4: Follow-up agent call in same session
            print("\nTask 4: Testing agent follow-up (multi-turn conversation)...")
            
            # Clear previous request and enter follow-up
            await textarea_agent.fill('')
            await page.wait_for_timeout(300)
            follow_up_request = '{"message": "How does deep learning differ from that?", "session_id": "demo-session"}'
            await textarea_agent.fill(follow_up_request)
            await page.wait_for_timeout(500)
            
            # Click Execute again
            await execute_button_agent.click()
            print("  Waiting for follow-up response (up to 60s)...")
            
            # Wait for follow-up response
            # Agent follow-up can also take 10-20 seconds
            await page.wait_for_timeout(15000)
            print("  Follow-up response should be ready...")
            
            # Take screenshot of follow-up response
            await page.screenshot(path='/home/thiennlh3/project/wiki-crawler/agent/screenshots/04_agent_multi_turn.png', full_page=True)
            print("✓ Saved: agent/screenshots/04_agent_multi_turn.png")
            
            # Task 5: Get session history
            print("\nTask 5: Getting session history...")
            
            # Navigate fresh to the page
            await page.goto('http://localhost:8001/docs', wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Find and expand the GET /api/v1/agent/sessions/{session_id} endpoint
            session_endpoint = page.get_by_text('/api/v1/agent/sessions/{session_id}', exact=True).first
            await session_endpoint.scroll_into_view_if_needed()
            await session_endpoint.click()
            await page.wait_for_timeout(1000)
            
            # Find the operation div for this GET endpoint
            session_operation = page.locator('.opblock').filter(has_text='/api/v1/agent/sessions/{session_id}').first
            
            # Click "Try it out" button
            try_it_out_session = session_operation.locator('button:has-text("Try it out")').first
            await try_it_out_session.click()
            await page.wait_for_timeout(500)
            
            # Fill session_id parameter
            session_id_input = session_operation.locator('input[placeholder="session_id"]').first
            await session_id_input.fill('demo-session')
            await page.wait_for_timeout(500)
            
            # Click Execute button
            execute_button_session = session_operation.locator('button:has-text("Execute")').first
            await execute_button_session.click()
            print("  Waiting for session history response...")
            
            # Wait for response
            # Session history is a simple GET, should be fast
            await page.wait_for_timeout(3000)
            print("  Session history response should be ready...")
            
            # Take screenshot of session history
            await page.screenshot(path='/home/thiennlh3/project/wiki-crawler/agent/screenshots/05_agent_session_history.png', full_page=True)
            print("✓ Saved: agent/screenshots/05_agent_session_history.png")
            
            print("\n✅ All screenshots completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(take_screenshots())
