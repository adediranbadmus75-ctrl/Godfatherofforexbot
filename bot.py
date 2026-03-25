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

# Force flush stdout/stderr
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Load environment variables
load_dotenv()

# Configuration - Using your exact environment variable names
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = os.getenv('USER_ID')  # Changed from YOUR_USER_ID to USER_ID
CHANNEL_ID = os.getenv('CHANNEL_ID')  # This will be used as default channel

# Validate configuration
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable is not set!")
    sys.exit(1)
    
if not OWNER_ID:
    print("❌ ERROR: USER_ID environment variable is not set!")
    print("Please add USER_ID to your Render environment variables.")
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
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Store monitored channels and their members in memory
monitored_channels: Set[int] = set()
channel_members: Dict[int, Set[int]] = {}

# If CHANNEL_ID is provided, add it to monitored channels on startup
if CHANNEL_ID:
    try:
        default_channel = int(CHANNEL_ID)
        monitored_channels.add(default_channel)
        channel_members[default_channel] = set()
        logger.info(f"✅ Added default channel {default_channel} from CHANNEL_ID env var")
    except ValueError:
        logger.error(f"❌ CHANNEL_ID must be a number, got: {CHANNEL_ID}")

# Print startup banner
print("=" * 50)
print("🤖 Telegram Member Monitor Bot")
print("=" * 50)
print(f"Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
print(f"Owner ID: {OWNER_ID}")
print(f"Default Channel ID: {CHANNEL_ID if CHANNEL_ID else 'Not set'}")
print(f"Monitored Channels: {len(monitored_channels)}")
print("=" * 50)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    logger.info(f"📨 Received /start from user {user_id}")
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized. This bot is for personal use only.")
        return
    
    # Show current monitoring status
    status_text = ""
    if monitored_channels:
        status_text = f"\n\n📊 **Currently monitoring {len(monitored_channels)} channel(s)**"
    
    await update.message.reply_text(
        f"🤖 **Member Monitor Bot Active**{status_text}\n\n"
        "**Commands:**\n"
        "• `/add` - Add current channel to monitoring\n"
        "• `/remove` - Remove current channel from monitoring\n"
        "• `/list` - List all monitored channels\n"
        "• `/status` - Show bot status\n"
        "• `/help` - Show this message\n\n"
        "**Setup:**\n"
        "1. Add bot as admin to your channel\n"
        "2. Go to the channel and send `/add`\n"
        "3. Bot will start monitoring new members\n\n"
        "⚠️ Bot needs at least 'View Messages' and 'Invite Users' permissions",
        parse_mode=ParseMode.MARKDOWN
    )
    
    logger.info(f"✅ Sent welcome message to user {user_id}")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add current channel to monitoring"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    # Check if command is used in a channel or supergroup
    chat = update.effective_chat
    chat_type = chat.type
    
    logger.info(f"📝 Add channel command from user {user_id} in chat {chat.id} (type: {chat_type})")
    
    if chat_type not in ['channel', 'supergroup']:
        await update.message.reply_text(
            "❌ This command must be used in a channel or supergroup.\n"
            "Please add the bot to your channel and send /add there."
        )
        return
    
    channel_id = chat.id
    channel_name = chat.title or f"Channel {channel_id}"
    
    # Check if bot is member of the channel
    try:
        bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        
        if bot_member.status not in ['administrator', 'member']:
            await update.message.reply_text(
                f"❌ I'm not a member of {channel_name}.\n"
                f"Please add me as an administrator first."
            )
            return
        
        # Add channel to monitoring
        if channel_id in monitored_channels:
            await update.message.reply_text(f"ℹ️ {channel_name} is already being monitored.")
            return
        
        monitored_channels.add(channel_id)
        channel_members[channel_id] = set()
        
        # Try to get existing members (optional, for reference)
        try:
            # This only works if bot is admin with sufficient permissions
            admins = await context.bot.get_chat_administrators(channel_id)
            for admin in admins:
                channel_members[channel_id].add(admin.user.id)
            logger.info(f"Initialized {len(channel_members[channel_id])} existing members in {channel_name}")
        except Exception as e:
            logger.warning(f"Could not fetch existing members for {channel_name}: {e}")
        
        await update.message.reply_text(
            f"✅ **Now monitoring {channel_name}**\n\n"
            f"I'll notify you whenever a new member joins.\n"
            f"Channel ID: `{channel_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"✅ Started monitoring channel: {channel_name} (ID: {channel_id})")
        
    except Exception as e:
        logger.error(f"❌ Error adding channel {channel_id}: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove current channel from monitoring"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    chat = update.effective_chat
    chat_type = chat.type
    
    if chat_type not in ['channel', 'supergroup']:
        await update.message.reply_text(
            "❌ This command must be used in the channel you want to remove."
        )
        return
    
    channel_id = chat.id
    channel_name = chat.title or f"Channel {channel_id}"
    
    if channel_id not in monitored_channels:
        await update.message.reply_text(f"ℹ️ {channel_name} is not being monitored.")
        return
    
    monitored_channels.discard(channel_id)
    channel_members.pop(channel_id, None)
    
    await update.message.reply_text(
        f"✅ **Stopped monitoring {channel_name}**",
        parse_mode=ParseMode.MARKDOWN
    )
    
    logger.info(f"✅ Stopped monitoring channel: {channel_name} (ID: {channel_id})")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all monitored channels"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    if not monitored_channels:
        await update.message.reply_text("📭 No channels are currently being monitored.")
        return
    
    message = "📋 **Monitored Channels:**\n\n"
    
    for channel_id in monitored_channels:
        try:
            chat = await context.bot.get_chat(channel_id)
            channel_name = chat.title or f"Channel {channel_id}"
            member_count = len(channel_members.get(channel_id, set()))
            message += f"• **{channel_name}**\n"
            message += f"  ID: `{channel_id}`\n"
            message += f"  Members tracked: {member_count}\n\n"
        except Exception as e:
            message += f"• Unknown channel (ID: `{channel_id}`)\n"
            message += f"  Error: {str(e)[:50]}\n\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot status"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    status_msg = (
        f"🤖 **Bot Status**\n\n"
        f"✅ Bot is running\n"
        f"📊 Monitoring {len(monitored_channels)} channel(s)\n"
        f"👥 Total members tracked: {sum(len(members) for members in channel_members.values())}\n"
        f"🕐 Uptime: Active\n"
        f"🔧 Owner ID: `{OWNER_ID}`\n"
    )
    
    if CHANNEL_ID:
        status_msg += f"📌 Default channel: `{CHANNEL_ID}`\n"
    
    await update.message.reply_text(status_msg, parse_mode=ParseMode.MARKDOWN)

async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle member join/leave events"""
    if not update.chat_member:
        return
    
    chat_member = update.chat_member
    chat = chat_member.chat
    channel_id = chat.id
    
    # Only process if channel is being monitored
    if channel_id not in monitored_channels:
        return
    
    new_status = chat_member.new_chat_member.status
    old_status = chat_member.old_chat_member.status
    user = chat_member.new_chat_member.user
    
    # Skip if it's the bot itself
    if user.id == context.bot.id:
        return
    
    # Check if user joined the channel
    if new_status == 'member' and old_status in ['left', 'kicked']:
        # Initialize member set if not exists
        if channel_id not in channel_members:
            channel_members[channel_id] = set()
        
        # Check if this is a new member we haven't seen
        if user.id not in channel_members[channel_id]:
            channel_members[channel_id].add(user.id)
            
            # Prepare notification message
            username = f"@{user.username}" if user.username else "No username"
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "No name"
            user_link = f"https://t.me/{user.username}" if user.username else "No profile link"
            
            message = (
                f"🔔 **NEW MEMBER JOINED!**\n\n"
                f"📱 **Channel:** {chat.title}\n"
                f"👤 **User:** {full_name}\n"
                f"🆔 **User ID:** `{user.id}`\n"
                f"👤 **Username:** {username}\n"
                f"🔗 **Profile:** {user_link}\n"
                f"🕐 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"📊 **Total members tracked:** {len(channel_members[channel_id])}"
            )
            
            # Send notification to owner
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"✅ Notified owner about new member: {full_name} (ID: {user.id}) in {chat.title}")
            except Exception as e:
                logger.error(f"❌ Failed to send notification: {e}")
    
    # Optional: Track when members leave
    elif old_status == 'member' and new_status in ['left', 'kicked']:
        if channel_id in channel_members:
            channel_members[channel_id].discard(user.id)
            logger.info(f"Member {user.id} left {chat.title}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    await start(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"❌ Update {update} caused error: {context.error}")
    
    # Notify owner about critical errors
    if update and update.effective_user and update.effective_user.id == OWNER_ID:
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"⚠️ **Error occurred:**\n```\n{str(context.error)[:200]}\n```",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

async def post_init(application: Application):
    """Callback after application initialization"""
    logger.info("✅ Bot started successfully!")
    logger.info(f"Bot username: @{application.bot.username}")
    
    # Send startup notification to owner
    try:
        await application.bot.send_message(
            chat_id=OWNER_ID,
            text="🤖 **Bot is online and ready!**\n\n"
                 f"📊 Monitoring {len(monitored_channels)} channel(s)\n\n"
                 "Use /add in any channel where I'm admin to start monitoring.\n"
                 "Use /status to check bot status.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("✅ Startup notification sent to owner")
    except Exception as e:
        logger.error(f"❌ Failed to send startup notification: {e}")

async def main_async():
    """Async main function"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_channel))
    application.add_handler(CommandHandler("remove", remove_channel))
    application.add_handler(CommandHandler("list", list_channels))
    application.add_handler(CommandHandler("status", status_command))
    
    # Add handler for member updates (catches joins and leaves)
    application.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Initialize and start
    await application.initialize()
    await application.start()
    
    # Start polling
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0
    )
    
    logger.info("🚀 Bot polling started!")
    
    # Keep running
    try:
        # Keep the bot running
        stop_signal = asyncio.Event()
        await stop_signal.wait()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def main():
    """Main entry point"""
    try:
        print("🚀 Starting Telegram Member Monitor Bot...")
        asyncio.run(main_async())
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
