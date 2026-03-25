import os
import sys
import asyncio
import logging
from datetime import datetime

# Print Python version at startup
print(f"Python version: {sys.version}")
print(f"Starting bot...")

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram.constants import ChatMemberStatus
except ImportError as e:
    print(f"Error importing telegram: {e}")
    sys.exit(1)

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

class MemberMonitorBot:
    def __init__(self):
        self.tracked_members = set()
        self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            await update.message.reply_text(
                f"🤖 Bot is active!\n\n"
                f"📡 Monitoring: {CHANNEL_ID}\n"
                f"📤 Notifications sent to: {USER_ID}\n\n"
                f"Use /status to check bot status"
            )
            logger.info(f"Start command sent to {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Start command error: {e}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            # Get channel info
            chat = await context.bot.get_chat(CHANNEL_ID)
            member_count = await context.bot.get_chat_member_count(CHANNEL_ID)
            
            status_text = (
                f"📊 **Bot Status**\n\n"
                f"📢 Channel: {chat.title}\n"
                f"🆔 Channel ID: {CHANNEL_ID}\n"
                f"👥 Members: {member_count}\n"
                f"🆕 New members tracked: {len(self.tracked_members)}\n"
                f"📱 Your User ID: {USER_ID}\n"
                f"✅ Status: **Active**\n"
                f"🐍 Python: {sys.version.split()[0]}"
            )
            await update.message.reply_text(status_text, parse_mode='Markdown')
            logger.info(f"Status command sent to {update.effective_user.id}")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            logger.error(f"Status command error: {e}")

    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new members joining"""
        try:
            # Check if this is from our channel
            channel_id_clean = str(CHANNEL_ID).replace('-100', '')
            chat_id_clean = str(update.effective_chat.id).replace('-100', '')
            
            if chat_id_clean != channel_id_clean:
                return

            # Process each new member
            for member in update.message.new_chat_members:
                if member.id == context.bot.id:
                    continue
                
                member_key = f"{update.effective_chat.id}_{member.id}"
                if member_key in self.tracked_members:
                    continue
                
                self.tracked_members.add(member_key)
                
                # Keep list manageable
                if len(self.tracked_members) > 10000:
                    self.tracked_members = set(list(self.tracked_members)[-5000:])
                
                # Send notification
                notification = (
                    f"🆕 **New Member Joined!**\n\n"
                    f"👤 **Name:** {member.full_name}\n"
                    f"📱 **Username:** @{member.username if member.username else 'N/A'}\n"
                    f"🆔 **User ID:** `{member.id}`\n"
                    f"⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📢 **Channel:** {update.effective_chat.title}"
                )
                
                await context.bot.send_message(
                    chat_id=int(USER_ID),
                    text=notification,
                    parse_mode='Markdown'
                )
                
                logger.info(f"New member notification sent: {member.full_name}")
                
        except Exception as e:
            logger.error(f"Member handler error: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Error: {context.error}")

    async def run(self):
        """Run the bot"""
        try:
            logger.info("Building application...")
            self.application = Application.builder().token(TOKEN).build()
            logger.info("Application built successfully")
            
            # Add handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(MessageHandler(
                filters.StatusUpdate.NEW_CHAT_MEMBERS, 
                self.new_member_handler
            ))
            self.application.add_error_handler(self.error_handler)
            
            # Start the bot
            logger.info("Starting bot...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("✅ Bot is running successfully!")
            
            # Send startup notification
            try:
                await self.application.bot.send_message(
                    chat_id=int(USER_ID),
                    text=f"✅ Bot started successfully!\n\nMonitoring: {CHANNEL_ID}\nPython: {sys.version.split()[0]}"
                )
            except Exception as e:
                logger.error(f"Startup notification failed: {e}")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Run error: {e}")
            raise

async def main():
    """Main entry point"""
    # Validate environment
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
        logger.error(f"USER_ID must be a number: {USER_ID}")
        return
    
    logger.info("=" * 50)
    logger.info("Starting Telegram Member Bot")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Channel: {CHANNEL_ID}")
    logger.info(f"User ID: {USER_ID}")
    logger.info("=" * 50)
    
    bot = MemberMonitorBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
