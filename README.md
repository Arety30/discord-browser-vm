# Discord Browser VM (NexusVM Browser Activity)

Discord Browser VM puts a real, isolated Chromium browser inside a Discord voice channel as an embedded Activity. A FastAPI backend drives one headless Chromium page per Discord server with Playwright, streams JPEG screenshots of it over a WebSocket at roughly 12 frames per second, and applies the clicks, scroll events, key presses and URL navigations that come back from the viewers. A React frontend, loaded in Discord's Activity iframe through the Embedded App SDK, renders the frames and captures input; a small Discord bot answers `!browser` and `!vmstatus` with instructions and health checks. The result is a shared browser that everyone in the server looks at together, without any viewer's own machine or cookies being involved.

## Where it is used

In Abrar's setup it runs on the laptop next to the other Discord bots, reusing the same Discord application and `.env` as `abrar-assistant`. The backend is exposed to Discord through a public HTTPS tunnel and registered as the application's Activity URL, so members of a private server can open a sandboxed browser from the voice-channel rocket button.

## How it works

### Backend (`backend/main.py`)

- **Sessions.** `sessions` is a dict `guild_id -> BrowserSession`. A session wraps a Playwright instance, a Chromium `Browser`, a `BrowserContext` with a 1280x720 viewport and a desktop user agent, and one `Page`. `get_chromium_executable()` looks for a system Chromium/Chrome in the usual Linux paths and falls back to Playwright's bundled browser. New pages open on the server's own start page.
- **Start page (`GET /start`).** A self-contained HTML page with a search box and four bookmark cards. Its script decides whether the typed text looks like a URL (regex, or contains `localhost`/`127.0.0.1`) and navigates directly; otherwise it submits a Google search.
- **Streaming (`WS /ws/browser?guild_id=...`).** On connect the session for that guild is created or reused and the socket is added to `session.connected_sockets`. A `screenshot_streamer` task loops while the socket is registered: under `session.lock` it takes a `jpeg` screenshot at quality 60, reads URL and title, sends the bytes as a binary frame, sends a JSON `{"type":"state", url, title}` whenever the URL changed, and sleeps 80 ms.
- **Input.** The receive loop parses JSON events and, under the same lock, maps them to Playwright calls: `click`/`mousemove` (x, y in viewport space), `scroll` (`mouse.wheel`), `keydown`/`keyup`/`keypress`/`type`, `navigate` (prefixing `https://` when missing), `back`, `forward`, `reload`, `resize`.
- **Idle cleanup.** A start-up task runs every 60 s and closes any session that has no connected sockets and no activity for 300 s, stopping its browser and Playwright instance.
- **Discord OAuth (`POST /api/token`).** Exchanges the authorization code the frontend obtained through the SDK for an access token using `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` and `DISCORD_REDIRECT_URI` (default `http://localhost:8000`), via `httpx`.
- **Static hosting.** If `frontend/dist` exists it is mounted at `/`.

### Frontend (`frontend/src/App.jsx`)

- If the page is inside an iframe it constructs `DiscordSDK` with the application's client id, waits for `ready()`, calls `authorize` with scopes `identify` and `guilds`, posts the code to `/api/token`, calls `authenticate`, and uses `discordSdk.guildId` as the session key. Outside Discord it falls back to `default_guild` ("Local Sandbox").
- Opens the WebSocket (`ws`/`wss` chosen from the page protocol), sets `binaryType = "arraybuffer"`, turns each binary frame into a Blob object URL on an `<img>` (revoking the previous URL), and derives a "latency" figure from the gap between frames. JSON messages update the URL bar and title or append to a small system log.
- Click coordinates are scaled from the rendered image size to the backend's 1280x720 viewport. Wheel events forward `deltaX`/`deltaY`. A "keyboard focus" toggle decides whether key events on the viewport are forwarded (with default browser behaviour suppressed for Tab, Backspace, Enter, Space and arrows). A separate text box sends a `type` event with its contents and clears itself, which is the practical way to enter text.
- Toolbar: back, forward, reload, URL/search input, connection indicator and latency.

### Bot (`bot.py`)

`!browser` posts an embed explaining how to launch the Activity; `!vmstatus` opens a TCP connection to `127.0.0.1:8000` to report whether the backend is up. The bot sets a "Watching Browser VMs" presence.

### Component table

| Path | Role |
|---|---|
| `backend/main.py` | FastAPI + Playwright: sessions, start page, WebSocket streamer and input handler, OAuth token exchange, static mount |
| `backend/requirements.txt` | fastapi, uvicorn, playwright, websockets, python-dotenv, discord.py, httpx |
| `frontend/src/App.jsx` | Activity UI, SDK handshake, WebSocket client, input capture |
| `frontend/src/index.css`, `index.html` | Glass/dark theme, fonts |
| `frontend/vite.config.js` | Dev server on 3000 with `/api` and `/ws` proxied to 8000; builds to `dist/` |
| `bot.py` | `!browser`, `!vmstatus` |
| `run.sh` | Creates the venv, installs requirements, builds the frontend, starts backend and bot together |

## Setup

Requirements: Python 3.9+, Node.js 18+, a Chromium or Chrome binary (or let Playwright download one with `playwright install chromium`), a Discord application with an Activity enabled.

```bash
cd ~/Workspace/DiscordBrowserVM
chmod +x run.sh
./run.sh            # venv + pip install + npm install + vite build + start both processes
```

Configuration is read from `.env` in the project root and, as a fallback, from the sibling `abrar-assistant` project's `.env`:

```ini
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_CLIENT_ID=000000000000000000
DISCORD_CLIENT_SECRET=your-client-secret
DISCORD_REDIRECT_URI=https://example.com
```

The client id is also hard-coded in `frontend/src/App.jsx` (`new DiscordSDK("...")`) and must match your application.

Registering the Activity in the Discord Developer Portal:

1. Open your application, go to **Embedded Activity**, and enable it.
2. Set the URL mapping to the public HTTPS address that forwards to `http://localhost:8000` (a tunnel such as Cloudflare Tunnel or ngrok works for testing).
3. Add the same address as an OAuth2 redirect and put it in `DISCORD_REDIRECT_URI`.
4. In Discord, join a voice channel, press the rocket (Activity) button and pick the app.

## Usage

```bash
# everything at once
./run.sh

# or separately
source venv/bin/activate
python backend/main.py          # http://0.0.0.0:8000
python bot.py
cd frontend && npm run dev      # optional: Vite dev server on :3000 proxying to :8000
```

Open `http://localhost:8000` in a normal browser to use the "Local Sandbox" session without Discord. In Discord, `!browser` prints launch instructions and `!vmstatus` reports whether the backend port is listening.

## Project structure

```
DiscordBrowserVM/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/{main.jsx, App.jsx, index.css}
├── bot.py
├── run.sh
└── README.md
```

## Limitations and notes

- One Chromium page per server: everyone in that server shares the same tab, cookies and history for the life of the session. There is no per-user isolation and no tab switching.
- Everything is unauthenticated at the WebSocket level; anyone who can reach the backend URL can pick any `guild_id` and drive that browser. Put it behind the Discord tunnel only, or add auth before exposing it more widely.
- Screenshot streaming is CPU-heavy and limited to about 12 fps; video playback will look choppy and audio is not transmitted at all.
- Key events are forwarded with the browser's `event.key` names; most work with Playwright, but some combinations do not map and the "type" box is more reliable for text.
- Sessions are in memory; restarting the backend closes every browser.
- `frontend/dist` and the `.env` fallback paths are absolute in `backend/main.py` and `bot.py`.
