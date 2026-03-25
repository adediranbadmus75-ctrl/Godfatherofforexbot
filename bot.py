import os
import logging
from datetime import datetime
from typing import Set, Dict
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ChatMemberHandler, ContextTypes
from telegram.constants import ParseMode

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('YOUR_USER_ID'))

# Validate configuration
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not OWNER_ID:
    raise ValueError("YOUR_USER_ID environment variable is required")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store monitored channels and their members in memory
monitored_channels: Set[int] = set()
channel_members: Dict[int, Set[int]] = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    logger.info(f"Received /start from user {user_id}")
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized. This bot is for personal use only.")
        return
    
    await update.message.reply_text(
        "🤖 **Member Monitor Bot Active**\n\n"
        "**Commands:**\n"
        "• `/add` - Add current channel to monitoring\n"
        "• `/remove` - Remove current channel from monitoring\n"
        "• `/list` - List all monitored channels\n"
        "• `/help` - Show this message\n\n"
        "**Setup:**\n"
        "1. Add bot as admin to your channel\n"
        "2. Go to the channel and send `/add`\n"
        "3. Bot will start monitoring new members\n\n"
        "⚠️ Bot needs at least 'View Messages' and 'Invite Users' permissions",
        parse_mode=ParseMode.MARKDOWN
    )
    
    logger.info(f"Sent welcome message to user {user_id}")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add current channel to monitoring"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    
    # Check if command is used in a channel or supergroup
    chat = update.effective_chat
    chat_type = chat.type
    
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
        
        logger.info(f"Started monitoring channel: {channel_name} (ID: {channel_id})")
        
    except Exception as e:
        logger.error(f"Error adding channel {channel_id}: {e}")
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
    
    logger.info(f"Stopped monitoring channel: {channel_name} (ID: {channel_id})")

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
    logger.error(f"Update {update} caused error: {context.error}")
    
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
                 "Use /add in any channel where I'm admin to start monitoring.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("Startup notification sent to owner")
    except Exception as e:
        logger.error(f"Failed to send startup notification: {e}")

def main():
    """Main entry point"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("add", add_channel))
        application.add_handler(CommandHandler("remove", remove_channel))
        application.add_handler(CommandHandler("list", list_channels))
        
        # Add handler for member updates (catches joins and leaves)
        application.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Start bot with proper polling configuration
        logger.info("🚀 Starting Telegram Member Monitor Bot...")
        logger.info(f"Bot token: {BOT_TOKEN[:10]}...")
        logger.info(f"Owner ID: {OWNER_ID}")
        
        # Start polling with higher timeout and proper settings
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=30
        )
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    main()
