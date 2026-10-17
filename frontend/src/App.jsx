import React, { useState, useEffect, useRef } from 'react';
import { DiscordSDK } from "@discord/embedded-app-sdk";

// Initialize Discord SDK (if running inside Discord)
let discordSdk = null;
if (typeof window !== 'undefined' && window.parent !== window) {
  // Simple check to see if we might be in an iframe
  discordSdk = new DiscordSDK("000000000000000000");
}

function App() {
  const [guildId, setGuildId] = useState("default_guild");
  const [guildName, setGuildName] = useState("Local Sandbox");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [currentUrl, setCurrentUrl] = useState("http://localhost:8000/start");
  const [urlInput, setUrlInput] = useState("");
  const [pageTitle, setPageTitle] = useState("Loading VM...");
  const [systemLogs, setSystemLogs] = useState(["Connecting to Browser VM..."]);
  const [isKeyboardFocused, setIsKeyboardFocused] = useState(false);
  const [latency, setLatency] = useState(0);

  const socketRef = useRef(null);
  const imgRef = useRef(null);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // Initialize Discord SDK
  useEffect(() => {
    async function setupDiscord() {
      if (!discordSdk) {
        setSystemLogs(prev => [...prev, "Running outside of Discord. Local dev mode active."]);
        setLoading(false);
        return;
      }

      try {
        setSystemLogs(prev => [...prev, "Initializing Discord Embedded SDK..."]);
        await discordSdk.ready();
        
        // Authenticate
        const { code } = await discordSdk.commands.authorize({
          client_id: "000000000000000000",
          response_type: "code",
          state: "",
          prompt: "none",
          scope: ["identify", "guilds"],
        });

        // Fetch tokens from backend
        const response = await fetch("/api/token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code }),
        });
        const { access_token } = await response.json();
        
        // Authenticate SDK
        await discordSdk.commands.authenticate({ access_token });
        
        // Extract Guild Info
        if (discordSdk.guildId) {
          setGuildId(discordSdk.guildId);
          // Fetch guild details using Discord API or just set placeholders
          setGuildName(`Guild VM (${discordSdk.guildId.substring(0, 6)})`);
        }
        
        setSystemLogs(prev => [...prev, "Discord Handshake complete."]);
      } catch (err) {
        console.error("Discord SDK setup failed:", err);
        setSystemLogs(prev => [...prev, `Discord SDK setup failed: ${err.message}. Falling back to default.`]);
      } finally {
        setLoading(false);
      }
    }

    setupDiscord();
  }, []);

  // Establish WebSocket Connection once Guild ID is ready
  useEffect(() => {
    if (loading) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/browser?guild_id=${guildId}`;
    
    setSystemLogs(prev => [...prev, `Connecting to browser stream at ${wsUrl}...`]);
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.binaryType = "arraybuffer";

    let lastFrameTime = Date.now();

    ws.onopen = () => {
      setConnected(true);
      setSystemLogs(prev => [...prev, "Virtual browser connection established!"]);
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Render screenshot
        const blob = new Blob([event.data], { type: "image/jpeg" });
        const url = URL.createObjectURL(blob);
        if (imgRef.current) {
          const oldUrl = imgRef.current.src;
          imgRef.current.src = url;
          // Clean up old object URL to prevent memory leaks
          if (oldUrl && oldUrl.startsWith("blob:")) {
            URL.revokeObjectURL(oldUrl);
          }
        }
        setLatency(Date.now() - lastFrameTime);
        lastFrameTime = Date.now();
      } else {
        // Parse JSON state updates
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "state") {
            setCurrentUrl(msg.url);
            setUrlInput(msg.url);
            setPageTitle(msg.title || "NexusVM Web Browser");
          } else if (msg.type === "error") {
            setSystemLogs(prev => [...prev, `[VM ERROR] ${msg.message}`]);
          }
        } catch (e) {
          console.error("Failed to parse JSON WS message", e);
        }
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setSystemLogs(prev => [...prev, "WebSocket connection closed."]);
    };

    ws.onerror = (err) => {
      setSystemLogs(prev => [...prev, `WebSocket Error: ${err.message}`]);
    };

    return () => {
      ws.close();
    };
  }, [guildId, loading]);

  // Handle address input navigation
  const handleNavigate = (e) => {
    e.preventDefault();
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: "navigate",
        url: urlInput
      }));
    }
  };

  // Generic control message sender
  const sendControl = (actionType, details = {}) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: actionType,
        ...details
      }));
    }
  };

  // Convert click coordinates to 1280x720 backend viewport space
  const handleViewportClick = (e) => {
    if (!imgRef.current) return;
    
    const rect = imgRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Scale to standard 1280x720 viewport
    const scaledX = Math.round((x / rect.width) * 1280);
    const scaledY = Math.round((y / rect.height) * 720);
    
    sendControl("click", { x: scaledX, y: scaledY });
  };

  // Send scroll wheel events
  const handleViewportWheel = (e) => {
    e.preventDefault();
    // Throttle or directly send
    sendControl("scroll", {
      deltaX: Math.round(e.deltaX),
      deltaY: Math.round(e.deltaY)
    });
  };

  // Keyboard input forwarding
  const handleKeyDown = (e) => {
    if (!isKeyboardFocused) return;
    
    // Prevent default browser shortcuts inside the activity viewport
    if (["Tab", "Backspace", "Enter", "Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      e.preventDefault();
    }

    sendControl("keydown", { key: e.key });
  };

  const handleKeyUp = (e) => {
    if (!isKeyboardFocused) return;
    sendControl("keyup", { key: e.key });
  };

  // Clear remote text input helper
  const handleKeyboardTypeHelper = (e) => {
    sendControl("type", { text: e.target.value });
    e.target.value = ""; // Clear input field immediately
  };

  return (
    <div className="glass-panel" style={{
      display: 'flex',
      flexDirection: 'column',
      width: '100vw',
      height: '100vh',
      padding: '0.8rem',
      gap: '0.8rem',
      boxSizing: 'border-box'
    }}>
      {/* Top Header / Stats Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0.2rem 0.5rem',
        fontSize: '0.85rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.2rem' }}>🌐</span>
          <span style={{ fontWeight: 800, letterSpacing: '-0.5px' }} className="glowing-text">NexusVM Browser</span>
          <span style={{
            background: 'rgba(255,255,255,0.06)',
            padding: '2px 8px',
            borderRadius: '4px',
            fontSize: '0.75rem',
            color: 'var(--text-muted)'
          }}>{guildName}</span>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: 'var(--text-muted)' }}>
          <span>Latency: <strong style={{ color: latency > 150 ? '#ef4444' : '#10b981' }}>{latency}ms</strong></span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <span style={{
              display: 'inline-block',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: connected ? '#10b981' : '#ef4444'
            }}></span>
            <span>{connected ? "VM Active" : "VM Offline"}</span>
          </div>
        </div>
      </div>

      {/* Main Browser Control Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.6rem',
        padding: '0.5rem',
        borderRadius: '12px',
        backgroundColor: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid var(--border-light)'
      }}>
        {/* Navigation Buttons */}
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          <button className="btn-control" onClick={() => sendControl("back")} title="Go Back">
            ◀
          </button>
          <button className="btn-control" onClick={() => sendControl("forward")} title="Go Forward">
            ▶
          </button>
          <button className="btn-control" onClick={() => sendControl("reload")} title="Reload Page">
            🔄
          </button>
        </div>

        {/* Address Bar */}
        <form onSubmit={handleNavigate} style={{ flexGrow: 1, display: 'flex' }}>
          <input
            type="text"
            className="address-input"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Search or enter web address..."
          />
        </form>

        {/* Virtual Keyboard Focus Mode indicator/helper */}
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <input 
            type="text"
            placeholder="Type here to input text..."
            onChange={handleKeyboardTypeHelper}
            style={{
              width: '180px',
              padding: '0.4rem 0.8rem',
              borderRadius: '8px',
              border: '1px solid var(--border-light)',
              background: 'rgba(0,0,0,0.2)',
              fontSize: '0.8rem',
              outline: 'none',
              color: 'var(--text-main)'
            }}
          />
          <button 
            className="btn-control" 
            style={{
              borderColor: isKeyboardFocused ? 'var(--accent-cyan)' : 'var(--border-light)',
              boxShadow: isKeyboardFocused ? 'var(--glow-shadow)' : 'none',
              fontSize: '0.8rem',
              padding: '0.4rem 0.8rem'
            }}
            onClick={() => setIsKeyboardFocused(!isKeyboardFocused)}
            title="Toggle Direct Keyboard Capture"
          >
            ⌨️ Keyboard Capture: {isKeyboardFocused ? "ON" : "OFF"}
          </button>
        </div>
      </div>

      {/* Main Viewport Container */}
      <div 
        ref={containerRef}
        style={{
          flexGrow: 1,
          position: 'relative',
          borderRadius: '12px',
          overflow: 'hidden',
          backgroundColor: '#000',
          border: '1px solid var(--border-light)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          outline: isKeyboardFocused ? '1px solid var(--accent-cyan)' : 'none',
          boxShadow: isKeyboardFocused ? 'var(--glow-shadow)' : 'none'
        }}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onKeyUp={handleKeyUp}
        onFocus={() => setIsKeyboardFocused(true)}
        onBlur={() => setIsKeyboardFocused(false)}
      >
        {!connected && (
          <div style={{
            position: 'absolute',
            zIndex: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '1rem',
            textAlign: 'center',
            padding: '2rem'
          }}>
            <div className="spinner" style={{ fontSize: '2.5rem' }}>🛰️</div>
            <div style={{ fontWeight: 600 }}>Connecting to Isolated Browser VM...</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {systemLogs[systemLogs.length - 1]}
            </div>
          </div>
        )}

        <img
          ref={imgRef}
          onMouseDown={handleViewportClick}
          onWheel={handleViewportWheel}
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            cursor: 'crosshair',
            display: connected ? 'block' : 'none',
            userSelect: 'none',
            WebkitUserDrag: 'none'
          }}
          alt="Browser Viewport Stream"
        />
      </div>

      {/* Page Title & Status Bar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0.2rem 0.5rem',
        fontSize: '0.75rem',
        color: 'var(--text-muted)'
      }}>
        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
          Title: <strong style={{ color: 'var(--text-main)' }}>{pageTitle}</strong>
        </div>
        <div>
          VM Resolution: <strong>1280 x 720 (Auto-Scaled)</strong>
        </div>
      </div>
    </div>
  );
}

export default App;
