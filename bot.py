import os
import sys
import logging
import asyncio
from datetime import datetime
from typing import Set, Dict
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ChatMemberHandler, ContextTypes
from telegram.constants import ParseMode

# Force flush stdout/stderr for better logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = os.getenv('USER_ID')
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Validate configuration
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable is not set!")
    sys.exit(1)
    
if not OWNER_ID:
    print("❌ ERROR: USER_ID environment variable is not set!")
    sys.exit(1)

try:
    OWNER_ID = int(OWNER_ID)
except ValueError:
    print(f"❌ ERROR: USER_ID must be a number, got: {OWNER_ID}")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Store monitored channels and members
monitored_channels: Set[int] = set()
channel_members: Dict[int, Set[int]] = {}

# Add default channel if provided
if CHANNEL_ID:
    try:
        default_channel = int(CHANNEL_ID)
        monitored_channels.add(default_channel)
        channel_members[default_channel] = set()
        logger.info(f"✅ Added default channel {default_channel}")
    except ValueError:
        logger.error(f"❌ Invalid CHANNEL_ID: {CHANNEL_ID}")

# Startup banner
print("=" * 50)
print("🤖 Telegram Member Monitor Bot")
print("=" * 50)
print(f"Owner ID: {OWNER_ID}")
print(f"Monitored Channels: {len(monitored_channels)}")
print("=" * 50)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    await update.message.reply_text(
        "🤖 **Member Monitor Bot Active**\n\n"
        "**Commands:**\n"
        "• `/add` - Add current channel to monitoring\n"
        "• `/remove` - Remove current channel from monitoring\n"
        "• `/list` - List monitored channels\n"
        "• `/status` - Show bot status\n\n"
        "**Setup:**\n"
        "1. Add bot as admin to your channel\n"
        "2. Go to the channel and send `/add`\n"
        "3. Bot will monitor new members",
        parse_mode=ParseMode.MARKDOWN
    )

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add current channel to monitoring"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    chat = update.effective_chat
    
    if chat.type not in ['channel', 'supergroup']:
        await update.message.reply_text("❌ Use this command in a channel.")
        return
    
    channel_id = chat.id
    channel_name = chat.title or f"Channel {channel_id}"
    
    try:
        # Check if bot is member
        bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        
        if bot_member.status not in ['administrator', 'member']:
            await update.message.reply_text("❌ Bot is not a member of this channel.")
            return
        
        if channel_id in monitored_channels:
            await update.message.reply_text(f"ℹ️ {channel_name} is already monitored.")
            return
        
        monitored_channels.add(channel_id)
        channel_members[channel_id] = set()
        
        await update.message.reply_text(
            f"✅ **Now monitoring {channel_name}**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Started monitoring: {channel_name}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove channel from monitoring"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    chat = update.effective_chat
    
    if chat.type not in ['channel', 'supergroup']:
        await update.message.reply_text("❌ Use this command in a channel.")
        return
    
    channel_id = chat.id
    channel_name = chat.title or f"Channel {channel_id}"
    
    if channel_id not in monitored_channels:
        await update.message.reply_text(f"ℹ️ {channel_name} is not monitored.")
        return
    
    monitored_channels.discard(channel_id)
    channel_members.pop(channel_id, None)
    
    await update.message.reply_text(
        f"✅ **Stopped monitoring {channel_name}**",
        parse_mode=ParseMode.MARKDOWN
    )
    
    logger.info(f"Stopped monitoring: {channel_name}")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List monitored channels"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    if not monitored_channels:
        await update.message.reply_text("📭 No channels monitored.")
        return
    
    message = "📋 **Monitored Channels:**\n\n"
    for channel_id in monitored_channels:
        try:
            chat = await context.bot.get_chat(channel_id)
            message += f"• {chat.title}\n"
            message += f"  ID: `{channel_id}`\n"
            message += f"  Members: {len(channel_members.get(channel_id, set()))}\n\n"
        except:
            message += f"• Unknown channel (ID: `{channel_id}`)\n\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    total_members = sum(len(members) for members in channel_members.values())
    
    await update.message.reply_text(
        f"🤖 **Bot Status**\n\n"
        f"✅ Running\n"
        f"📊 Monitoring: {len(monitored_channels)} channel(s)\n"
        f"👥 Members tracked: {total_members}\n"
        f"🆔 Owner: `{OWNER_ID}`",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle member joins"""
    if not update.chat_member:
        return
    
    chat_member = update.chat_member
    chat = chat_member.chat
    channel_id = chat.id
    
    if channel_id not in monitored_channels:
        return
    
    new_status = chat_member.new_chat_member.status
    old_status = chat_member.old_chat_member.status
    user = chat_member.new_chat_member.user
    
    # Skip bot itself
    if user.id == context.bot.id:
        return
    
    # Member joined
    if new_status == 'member' and old_status in ['left', 'kicked']:
        if channel_id not in channel_members:
            channel_members[channel_id] = set()
        
        if user.id not in channel_members[channel_id]:
            channel_members[channel_id].add(user.id)
            
            # Format message
            username = f"@{user.username}" if user.username else "No username"
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "No name"
            
            message = (
                f"🔔 **NEW MEMBER JOINED!**\n\n"
                f"📱 **Channel:** {chat.title}\n"
                f"👤 **Name:** {full_name}\n"
                f"🆔 **ID:** `{user.id}`\n"
                f"👤 **Username:** {username}\n"
                f"🕐 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📊 **Total:** {len(channel_members[channel_id])} members tracked"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"Notified: {full_name} joined {chat.title}")
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}")

def main():
    """Main function - SIMPLIFIED for Render"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add_channel))
    application.add_handler(CommandHandler("remove", remove_channel))
    application.add_handler(CommandHandler("list", list_channels))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER))
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🚀 Starting bot...")
    
    # Use run_polling instead of manual async management
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0
    )

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
