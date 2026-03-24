import os
import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatMemberStatus

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
USER_ID = os.environ.get("USER_ID")

logger.info(f"Starting bot...")
logger.info(f"CHANNEL_ID: {CHANNEL_ID}")
logger.info(f"USER_ID: {USER_ID}")

class MemberMonitorBot:
    def __init__(self):
        self.tracked_members = set()
        self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            f"🤖 Bot is running!\n\n"
            f"Monitoring channel: {CHANNEL_ID}\n"
            f"Sending notifications to: {USER_ID}\n\n"
            f"Use /status to check current status"
        )
        logger.info(f"Sent /start response to {update.effective_user.id}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
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
        except Exception as e:
            await update.message.reply_text(f"Error getting status: {str(e)}")
            logger.error(f"Error in status: {e}")

    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new chat members joining"""
        try:
            # Check if this is from the channel we're monitoring
            channel_id_str = str(CHANNEL_ID).replace('-100', '')
            chat_id_str = str(update.effective_chat.id).replace('-100', '')
            
            if chat_id_str != channel_id_str:
                return

            # Get new members
            for member in update.message.new_chat_members:
                # Skip if it's the bot itself
                if member.id == context.bot.id:
                    continue
                
                # Check if we've already notified
                member_key = f"{update.effective_chat.id}_{member.id}"
                if member_key in self.tracked_members:
                    continue
                
                # Add to tracked members
                self.tracked_members.add(member_key)
                
                # Clean up old entries if too many
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
                
                # Send notification
                await context.bot.send_message(
                    chat_id=int(USER_ID),
                    text=notification,
                    parse_mode='Markdown'
                )
                
                logger.info(f"Notified about new member: {member.full_name}")
                
        except Exception as e:
            logger.error(f"Error in new member handler: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")

    async def run(self):
        """Run the bot"""
        # Build and initialize application
        self.application = Application.builder().token(TOKEN).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))
        self.application.add_error_handler(self.error_handler)
        
        # Initialize and start
        await self.application.initialize()
        await self.application.start()
        
        # Start polling
        await self.application.updater.start_polling()
        
        logger.info("Bot is running!")
        
        # Send startup notification
        try:
            await self.application.bot.send_message(
                chat_id=int(USER_ID),
                text=f"🤖 Bot started successfully!\n\nMonitoring channel: {CHANNEL_ID}"
            )
        except Exception as e:
            logger.error(f"Could not send startup message: {e}")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

async def main():
    """Main entry point"""
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return
    
    if not CHANNEL_ID:
        logger.error("CHANNEL_ID not set!")
        return
    
    if not USER_ID:
        logger.error("USER_ID not set!")
        return
    
    try:
        int(USER_ID)
    except ValueError:
        logger.error(f"USER_ID must be a number, got: {USER_ID}")
        return
    
    bot = MemberMonitorBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
