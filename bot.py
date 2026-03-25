import os
import sys
import logging
from datetime import datetime
from typing import Set, Dict, List
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
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Get all owner IDs
def get_owner_ids() -> List[int]:
    """Get list of all authorized user IDs from environment variables"""
    owner_ids = []
    
    # Primary owner
    primary_id = os.getenv('USER_ID')
    if primary_id:
        try:
            owner_ids.append(int(primary_id))
        except ValueError:
            print(f"❌ ERROR: USER_ID must be a number, got: {primary_id}")
    
    # Additional owners (USER_ID_2, USER_ID_3, etc.)
    for i in range(2, 10):  # Supports up to USER_ID_9
        additional_id = os.getenv(f'USER_ID_{i}')
        if additional_id:
            try:
                owner_ids.append(int(additional_id))
                print(f"✅ Added additional owner: USER_ID_{i} = {additional_id}")
            except ValueError:
                print(f"⚠️ Warning: USER_ID_{i} is not a valid number: {additional_id}")
    
    return owner_ids

OWNER_IDS = get_owner_ids()

# Validate configuration
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN environment variable is not set!")
    sys.exit(1)
    
if not OWNER_IDS:
    print("❌ ERROR: At least one USER_ID must be set!")
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
print(f"Owner IDs: {OWNER_IDS}")
print(f"Total Owners: {len(OWNER_IDS)}")
print(f"Monitored Channels: {len(monitored_channels)}")
print("=" * 50)

def is_authorized(user_id: int) -> bool:
    """Check if user is authorized"""
    return user_id in OWNER_IDS

async def notify_all_owners(bot, message: str):
    """Send notification to all authorized owners when someone joins"""
    for owner_id in OWNER_IDS:
        try:
            await bot.send_message(
                chat_id=owner_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"✅ Notification sent to owner {owner_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send notification to {owner_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    owners_list = ", ".join([str(uid) for uid in OWNER_IDS])
    
    await update.message.reply_text(
        f"🤖 **Member Monitor Bot Active**\n\n"
        f"👥 **Authorized Owners:** `{len(OWNER_IDS)}` users\n"
        f"🆔 **Your ID:** `{user_id}`\n\n"
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
    
    if not is_authorized(user_id):
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
            f"✅ **Now monitoring {channel_name}**\n\n"
            f"All {len(OWNER_IDS)} owner(s) will receive notifications when new members join.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Started monitoring: {channel_name}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove channel from monitoring"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
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
    
    if not is_authorized(user_id):
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
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    total_members = sum(len(members) for members in channel_members.values())
    
    await update.message.reply_text(
        f"🤖 **Bot Status**\n\n"
        f"✅ Running\n"
        f"📊 Monitoring: {len(monitored_channels)} channel(s)\n"
        f"👥 Members tracked: {total_members}\n"
        f"🆔 Authorized Owners: `{len(OWNER_IDS)}` users",
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
            
            # Notify all owners
            await notify_all_owners(context.bot, message)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}")

def main():
    """Main function"""
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
