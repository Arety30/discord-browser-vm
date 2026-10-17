import os
import asyncio
import json
import logging
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from dotenv import load_dotenv
import httpx

# Load credentials from the main Discord bot's .env file
load_dotenv("~/Workspace/DiscordBrowserVM/.env")
load_dotenv("~/Workspace/AbrarAssistant/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BrowserVM")

app = FastAPI(title="Discord Browser VM Backend")

# In-memory storage for active browser sessions
class BrowserSession:
    def __init__(self, guild_id: str, browser: Browser, context: BrowserContext, page: Page):
        self.guild_id = guild_id
        self.browser = browser
        self.context = context
        self.page = page
        self.connected_sockets = set()
        self.lock = asyncio.Lock()
        self.last_activity = asyncio.get_event_loop().time()
        self.playwright = None

sessions: Dict[str, BrowserSession] = {}

def get_chromium_executable():
    """Find local Chromium executable."""
    paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium",
    ]
    for p in paths:
        if os.path.exists(p):
            logger.info(f"Using local Chromium engine: {p}")
            return p
    logger.info("Local Chromium executable not found in standard paths. Playwright default will be used.")
    return None

async def create_session(guild_id: str) -> BrowserSession:
    """Creates a new browser instance for a specific guild."""
    logger.info(f"Initializing new Browser VM for Guild: {guild_id}")
    playwright = await async_playwright().start()
    
    exec_path = get_chromium_executable()
    launch_kwargs = {
        "headless": True,
    }
    if exec_path:
        launch_kwargs["executable_path"] = exec_path
        
    browser = await playwright.chromium.launch(**launch_kwargs)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    # Start on the custom gorgeous start page
    await page.goto("http://localhost:8000/start")
    
    session = BrowserSession(guild_id, browser, context, page)
    session.playwright = playwright
    
    sessions[guild_id] = session
    return session

async def close_session(guild_id: str):
    """Closes a browser session and cleans up resources."""
    if guild_id in sessions:
        session = sessions[guild_id]
        logger.info(f"Closing Browser VM for Guild: {guild_id}")
        try:
            await session.page.close()
            await session.context.close()
            await session.browser.close()
            await session.playwright.stop()
        except Exception as e:
            logger.error(f"Error closing session {guild_id}: {e}")
        del sessions[guild_id]

# Periodically clean up idle sessions (e.g. no activity for 5 minutes)
async def cleanup_idle_sessions():
    while True:
        await asyncio.sleep(60)
        now = asyncio.get_event_loop().time()
        idle_guilds = []
        for guild_id, session in sessions.items():
            if not session.connected_sockets and (now - session.last_activity > 300):
                idle_guilds.append(guild_id)
        
        for guild_id in idle_guilds:
            logger.info(f"Session for Guild {guild_id} has been idle. Terminating VM...")
            await close_session(guild_id)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_idle_sessions())

# Discord OAuth Code Exchange Endpoint
@app.post("/api/token")
async def get_discord_token(request: Request):
    try:
        body = await request.json()
        code = body.get("code")
        if not code:
            return {"error": "Missing authorization code"}

        client_id = os.getenv("DISCORD_CLIENT_ID")
        client_secret = os.getenv("DISCORD_CLIENT_SECRET")
        # For Discord Activities, redirect_uri must match your activity url or developer portal configuration
        redirect_uri = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:8000")

        logger.info(f"Exchanging Discord auth code for token. ClientID: {client_id}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://discord.com/api/v10/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            token_data = response.json()
            if "error" in token_data:
                logger.error(f"Discord API token exchange error: {token_data}")
            return token_data
    except Exception as e:
        logger.error(f"Token endpoint error: {e}")
        return {"error": str(e)}

# Beautiful Space-themed start page for the browser VM
@app.get("/start")
async def get_start_page():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NexusVM Start Page</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-primary: #0a0a16;
                --accent-primary: #00f0ff;
                --accent-secondary: #ad00ff;
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
                --card-bg: rgba(255, 255, 255, 0.03);
                --card-border: rgba(255, 255, 255, 0.08);
            }
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }
            body {
                background: radial-gradient(circle at 50% 50%, #12102e 0%, var(--bg-primary) 100%);
                color: var(--text-main);
                font-family: 'Outfit', sans-serif;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                overflow: hidden;
            }
            body::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: 
                    radial-gradient(circle at 20% 30%, rgba(173, 0, 255, 0.15) 0%, transparent 40%),
                    radial-gradient(circle at 80% 70%, rgba(0, 240, 255, 0.15) 0%, transparent 40%);
                z-index: -1;
            }
            .container {
                max-width: 800px;
                width: 90%;
                text-align: center;
                z-index: 10;
            }
            h1 {
                font-size: 3.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.5rem;
                letter-spacing: -1px;
                animation: fadeIn 1s ease-out;
            }
            p.tagline {
                font-size: 1.2rem;
                color: var(--text-muted);
                margin-bottom: 2.5rem;
                font-family: 'Inter', sans-serif;
            }
            .search-box {
                position: relative;
                width: 100%;
                max-width: 600px;
                margin: 0 auto 3rem;
            }
            .search-input {
                width: 100%;
                padding: 1.2rem 1.5rem 1.2rem 3.5rem;
                border-radius: 50px;
                border: 1px solid var(--card-border);
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                color: var(--text-main);
                font-size: 1.1rem;
                font-family: 'Inter', sans-serif;
                outline: none;
                transition: all 0.3s ease;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            .search-input:focus {
                border-color: var(--accent-primary);
                box-shadow: 0 0 20px rgba(0, 240, 255, 0.3), 0 10px 30px rgba(0,0,0,0.5);
                background: rgba(255, 255, 255, 0.08);
            }
            .search-icon {
                position: absolute;
                left: 1.3rem;
                top: 50%;
                transform: translateY(-50%);
                color: var(--text-muted);
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 1.5rem;
                margin-top: 1.5rem;
            }
            .bookmark-card {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-decoration: none;
                color: var(--text-main);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                backdrop-filter: blur(5px);
            }
            .bookmark-card:hover {
                transform: translateY(-5px);
                border-color: var(--accent-primary);
                background: rgba(255, 255, 255, 0.08);
                box-shadow: 0 10px 25px rgba(0, 240, 255, 0.15);
            }
            .bookmark-icon {
                width: 48px;
                height: 48px;
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.05);
                display: flex;
                justify-content: center;
                align-items: center;
                margin-bottom: 0.8rem;
                font-size: 1.5rem;
                transition: all 0.3s ease;
            }
            .bookmark-card:hover .bookmark-icon {
                background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
                transform: scale(1.1);
            }
            .bookmark-name {
                font-weight: 600;
                font-size: 1rem;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>NexusVM Browser</h1>
            <p class="tagline">Your high-performance virtual environment browser sandbox</p>
            
            <div class="search-box">
                <span class="search-icon">🔍</span>
                <form action="https://www.google.com/search" method="get" id="search-form">
                    <input type="text" name="q" class="search-input" placeholder="Search Google or type a URL..." autofocus autocomplete="off">
                </form>
            </div>
            
            <div class="grid">
                <a href="https://www.google.com" class="bookmark-card">
                    <div class="bookmark-icon">🌐</div>
                    <span class="bookmark-name">Google</span>
                </a>
                <a href="https://www.youtube.com" class="bookmark-card">
                    <div class="bookmark-icon">📺</div>
                    <span class="bookmark-name">YouTube</span>
                </a>
                <a href="https://github.com" class="bookmark-card">
                    <div class="bookmark-icon">💻</div>
                    <span class="bookmark-name">GitHub</span>
                </a>
                <a href="https://wikipedia.org" class="bookmark-card">
                    <div class="bookmark-icon">📚</div>
                    <span class="bookmark-name">Wikipedia</span>
                </a>
            </div>
        </div>
        
        <script>
            document.getElementById('search-form').addEventListener('submit', function(e) {
                const input = this.querySelector('input');
                const val = input.value.trim();
                
                if (val.match(/^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/) || val.includes("localhost") || val.includes("127.0.0.1")) {
                    e.preventDefault();
                    let url = val;
                    if (!url.startsWith('http://') && !url.startsWith('https://')) {
                        url = 'https://' + url;
                    }
                    window.location.href = url;
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# WebSocket streaming endpoint
@app.websocket("/ws/browser")
async def browser_websocket(websocket: WebSocket, guild_id: str = "default"):
    await websocket.accept()
    logger.info(f"WebSocket Client connected for Guild: {guild_id}")
    
    if guild_id not in sessions:
        try:
            session = await create_session(guild_id)
        except Exception as e:
            logger.error(f"Failed to start Browser VM for guild {guild_id}: {e}")
            await websocket.send_json({"type": "error", "message": f"Failed to launch Browser VM: {str(e)}"})
            await websocket.close()
            return
    else:
        session = sessions[guild_id]
        
    session.connected_sockets.add(websocket)
    session.last_activity = asyncio.get_event_loop().time()
    
    try:
        current_url = session.page.url
        await websocket.send_json({
            "type": "state", 
            "url": current_url,
            "title": await session.page.title()
        })
    except Exception as e:
        logger.error(f"Error sending initial state: {e}")

    async def screenshot_streamer():
        last_url = ""
        while websocket in session.connected_sockets:
            try:
                async with session.lock:
                    screenshot = await session.page.screenshot(type="jpeg", quality=60)
                    url = session.page.url
                    title = await session.page.title()
                
                await websocket.send_bytes(screenshot)
                
                if url != last_url:
                    await websocket.send_json({
                        "type": "state",
                        "url": url,
                        "title": title
                    })
                    last_url = url
                    
                await asyncio.sleep(0.08)
            except Exception as e:
                logger.debug(f"Streamer closed for {guild_id}: {e}")
                break

    streamer_task = asyncio.create_task(screenshot_streamer())
    
    try:
        while True:
            data = await websocket.receive_text()
            event = json.loads(data)
            session.last_activity = asyncio.get_event_loop().time()
            
            event_type = event.get("type")
            
            async with session.lock:
                if event_type == "click":
                    x = event.get("x")
                    y = event.get("y")
                    await session.page.mouse.click(x, y)
                    
                elif event_type == "mousemove":
                    x = event.get("x")
                    y = event.get("y")
                    await session.page.mouse.move(x, y)
                    
                elif event_type == "scroll":
                    dx = event.get("deltaX", 0)
                    dy = event.get("deltaY", 0)
                    await session.page.mouse.wheel(dx, dy)
                    
                elif event_type == "keydown":
                    key = event.get("key")
                    if key:
                        await session.page.keyboard.down(key)
                        
                elif event_type == "keyup":
                    key = event.get("key")
                    if key:
                        await session.page.keyboard.up(key)
                        
                elif event_type == "keypress":
                    key = event.get("key")
                    if key:
                        await session.page.keyboard.press(key)
                        
                elif event_type == "type":
                    text = event.get("text")
                    if text:
                        await session.page.keyboard.type(text)
                        
                elif event_type == "navigate":
                    url = event.get("url")
                    if url:
                        if not url.startswith("http://") and not url.startswith("https://"):
                            url = "https://" + url
                        logger.info(f"[{guild_id}] Navigating to: {url}")
                        await session.page.goto(url)
                        
                elif event_type == "back":
                    try:
                        await session.page.go_back()
                    except Exception:
                        pass
                        
                elif event_type == "forward":
                    try:
                        await session.page.go_forward()
                    except Exception:
                        pass
                        
                elif event_type == "reload":
                    await session.page.reload()
                    
                elif event_type == "resize":
                    w = event.get("width", 1280)
                    h = event.get("height", 720)
                    await session.page.set_viewport_size({"width": w, "height": h})
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket Client disconnected for Guild: {guild_id}")
    finally:
        session.connected_sockets.discard(websocket)
        streamer_task.cancel()
        session.last_activity = asyncio.get_event_loop().time()

# Mount frontend build directory
frontend_dist = "~/Workspace/DiscordBrowserVM/frontend/dist"
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    logger.warning("Frontend build folder not found yet. Please run frontend build.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
