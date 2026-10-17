import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging

# Load configuration from main bot .env
load_dotenv("~/Workspace/AbrarAssistant/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BrowserVMBot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("------")
    # Set status
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Browser VMs"))

@bot.command(name="browser")
async def browser_status(ctx):
    """Provides instructions on how to access the Chromium Browser VM Activity."""
    embed = discord.Embed(
        title="🌐 NexusVM browser activity",
        description="Run isolated Chromium instances directly inside Discord!",
        color=0x00f0ff
    )
    embed.add_field(
        name="🚀 How to launch",
        value="1. Join any **Voice Channel** in this server.\n2. Click the **Activity Launcher** button (rocket icon).\n3. Search for or select **NexusVM Browser**.\n4. Browse the web asynchronously with other members!",
        inline=False
    )
    embed.add_field(
        name="⚡ Features",
        value="• **Isolated session** per Discord Server (Guild).\n• Full keyboard input forwarding & mouse clicking.\n• Powered by system's Chromium engine.\n• Seamless, low-latency screenshot-based stream.",
        inline=False
    )
    embed.set_footer(text="NexusVM Browser • Powered by Playwright")
    
    await ctx.send(embed=embed)

@bot.command(name="vmstatus")
async def vm_status(ctx):
    """Checks the status of the Browser VM backend."""
    # Check if backend FastAPI port (8000) is running (locally)
    import socket
    a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    location = ("127.0.0.1", 8000)
    result_of_check = a_socket.connect_ex(location)
    
    is_running = (result_of_check == 0)
    a_socket.close()

    embed = discord.Embed(
        title="🛰️ VM Backend Diagnostics",
        color=0x10b981 if is_running else 0xef4444
    )
    embed.add_field(name="Server Address", value="`http://localhost:8000`", inline=True)
    embed.add_field(name="Status", value="🟢 **Active**" if is_running else "🔴 **Offline**", inline=True)
    embed.add_field(name="Guild ID", value=f"`{ctx.guild.id}`", inline=False)
    
    if is_running:
        embed.description = "The VM Host is healthy and ready to accept WebSocket streaming requests."
    else:
        embed.description = "The VM Host is offline. Start the backend with `bash run.sh`."
        
    await ctx.send(embed=embed)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment!")
    else:
        bot.run(token)
