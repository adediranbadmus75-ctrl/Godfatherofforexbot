import os
import sys
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatMemberStatus

# Configure detailed logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
USER_ID = os.environ.get("USER_ID")

logger.info(f"Starting bot initialization...")
logger.info(f"CHANNEL_ID: {CHANNEL_ID}")
logger.info(f"USER_ID: {USER_ID}")
logger.info(f"TOKEN exists: {bool(TOKEN)}")

class MemberMonitorBot:
    def __init__(self):
        logger.info("Creating MemberMonitorBot instance")
        self.application = None
        self.tracked_members = set()
        self.is_running = True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            logger.info(f"Received /start from user {update.effective_user.id}")
            await update.message.reply_text(
                f"🤖 Bot is running!\n\n"
                f"Monitoring channel: {CHANNEL_ID}\n"
                f"Sending notifications to: {USER_ID}\n\n"
                f"Use /status to check current status"
            )
            logger.info(f"Sent /start response to {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error in start command: {e}", exc_info=True)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            logger.info(f"Received /status from user {update.effective_user.id}")
            chat = await context.bot.get_chat(CHANNEL_ID)
            member_count = await context.bot.get_chat_member_count(CHANNEL_ID)
            
            status_text = (
                f"📊 **Bot Status**\n\n"
                f"Channel: {chat.title}\n"
                f"Channel ID: {CHANNEL_ID}\n"
                f"Members: {member_count}\n"
                f"Tracked new members: {len(self.tracked_members)}\n"
                f"Notification User ID: {USER_ID}\n"
                f"Bot Status: 🟢 Active"
            )
            await update.message.reply_text(status_text, parse_mode='Markdown')
            logger.info(f"Sent status response to {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error in status command: {e}", exc_info=True)
            await update.message.reply_text(f"Error getting status: {str(e)}")

    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new chat members joining"""
        try:
            logger.info(f"New member event received from chat {update.effective_chat.id}")
            
            # Check if this is from the channel we're monitoring
            chat_id_str = str(update.effective_chat.id)
            channel_id_str = str(CHANNEL_ID)
            
            # Remove -100 prefix if present for comparison
            if channel_id_str.startswith('-100'):
                channel_id_str = channel_id_str[4:]
            if chat_id_str.startswith('-100'):
                chat_id_str = chat_id_str[4:]
            
            if chat_id_str != channel_id_str:
                logger.info(f"Ignoring member from chat {chat_id_str}, expected {channel_id_str}")
                return

            # Get new members
            for member in update.message.new_chat_members:
                logger.info(f"New member detected: {member.full_name} (ID: {member.id})")
                
                # Skip if it's the bot itself
                if member.id == context.bot.id:
                    logger.info("Skipping bot itself")
                    continue
                
                # Check if we've already notified about this member
                member_key = f"{update.effective_chat.id}_{member.id}"
                if member_key in self.tracked_members:
                    logger.info(f"Already notified about member {member.id}")
                    continue
                
                # Add to tracked members
                self.tracked_members.add(member_key)
                
                # Keep tracked members list manageable
                if len(self.tracked_members) > 10000:
                    self.tracked_members = set(list(self.tracked_members)[-5000:])
                
                # Prepare notification message
                notification = (
                    f"🆕 **New Member Joined!**\n\n"
                    f"**Name:** {member.full_name}\n"
                    f"**Username:** @{member.username if member.username else 'N/A'}\n"
                    f"**User ID:** `{member.id}`\n"
                    f"**Joined at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"**Channel:** {update.effective_chat.title}"
                )
                
                # Send notification to the specified user
                await context.bot.send_message(
                    chat_id=USER_ID,
                    text=notification,
                    parse_mode='Markdown'
                )
                
                logger.info(f"Notified about new member: {member.full_name} (ID: {member.id})")
                
        except Exception as e:
            logger.error(f"Error in new member handler: {e}", exc_info=True)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}", exc_info=True)

    async def initialize(self):
        """Initialize bot and check permissions"""
        try:
            logger.info("Initializing bot...")
            
            # Build the application
            self.application = Application.builder().token(TOKEN).build()
            logger.info("Application built successfully")
            
            # Add handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
            self.application.add_error_handler(self.error_handler)
            logger.info("Handlers added")
            
            # Initialize the application
            await self.application.initialize()
            logger.info("Application initialized")
            
            # Verify bot can access the channel
            chat = await self.application.bot.get_chat(CHANNEL_ID)
            logger.info(f"Connected to channel: {chat.title}")
            
            # Check bot permissions in channel
            bot_member = await self.application.bot.get_chat_member(CHANNEL_ID, self.application.bot.id)
            if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                logger.warning("Bot is not an administrator in the channel!")
                await self.application.bot.send_message(
                    chat_id=USER_ID,
                    text="⚠️ Warning: Bot is not an administrator in the channel! It won't receive join events."
                )
            else:
                logger.info("Bot has administrator permissions in channel")
                
            # Send startup message
            await self.application.bot.send_message(
                chat_id=USER_ID,
                text=f"🤖 Bot started successfully!\n\nMonitoring channel: {CHANNEL_ID}"
            )
            logger.info("Startup message sent")
                
        except Exception as e:
            logger.error(f"Initialization error: {e}", exc_info=True)
            raise

    async def run(self):
        """Run the bot"""
        try:
            await self.initialize()
            
            # Start polling
            logger.info("Starting bot polling...")
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Bot is running! Press Ctrl+C to stop")
            
            # Keep the bot running
            while self.is_running:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("Bot stopped by cancellation")
        except KeyboardInterrupt:
            logger.info("Bot stopped by keyboard interrupt")
        except Exception as e:
            logger.error(f"Error in run method: {e}", exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the bot gracefully"""
        logger.info("Stopping bot...")
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
        logger.info("Bot stopped")

async def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("Starting Telegram Member Bot")
    logger.info("=" * 50)
    
    # Validate environment variables
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        logger.error("Please set it in Render dashboard")
        return
    
    if not CHANNEL_ID:
        logger.error("CHANNEL_ID environment variable not set!")
        logger.error("Please set it in Render dashboard")
        return
    
    if not USER_ID:
        logger.error("USER_ID environment variable not set!")
        logger.error("Please set it in Render dashboard")
        return
    
    try:
        USER_ID_INT = int(USER_ID)
        logger.info(f"USER_ID converted to integer: {USER_ID_INT}")
    except ValueError:
        logger.error(f"USER_ID must be a number, got: {USER_ID}")
        return
    
    logger.info(f"Configuration validated:")
    logger.info(f"  Channel: {CHANNEL_ID}")
    logger.info(f"  User ID: {USER_ID}")
    logger.info(f"  Token length: {len(TOKEN)} characters")
    
    bot = MemberMonitorBot()
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
