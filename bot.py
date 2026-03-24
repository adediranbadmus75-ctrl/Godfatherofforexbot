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
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # e.g., @channelusername or -1001234567890
USER_ID = int(os.environ.get("USER_ID"))  # Your Telegram user ID

class MemberMonitorBot:
    def __init__(self):
        self.app = Application.builder().token(TOKEN).build()
        self.setup_handlers()
        self.tracked_members = set()

    def setup_handlers(self):
        """Setup bot handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.new_member_handler))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            f"🤖 Bot is running!\n\n"
            f"Monitoring channel: {CHANNEL_ID}\n"
            f"Sending notifications to: {USER_ID}\n\n"
            f"Use /status to check current status"
        )

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

    async def new_member_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new chat members joining"""
        try:
            # Check if this is from the channel we're monitoring
            if str(update.effective_chat.id) != str(CHANNEL_ID).replace('-100', ''):
                return

            # Get new members
            for member in update.message.new_chat_members:
                # Skip if it's the bot itself
                if member.id == context.bot.id:
                    continue
                
                # Check if we've already notified about this member
                member_key = f"{update.effective_chat.id}_{member.id}"
                if member_key in self.tracked_members:
                    continue
                
                # Add to tracked members
                self.tracked_members.add(member_key)
                
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
            logger.error(f"Error in new member handler: {e}")
            # Try to notify about the error
            try:
                await context.bot.send_message(
                    chat_id=USER_ID,
                    text=f"⚠️ Error processing new member: {str(e)}"
                )
            except:
                pass

    async def initialize(self):
        """Initialize bot and check permissions"""
        try:
            # Verify bot can access the channel
            chat = await self.app.bot.get_chat(CHANNEL_ID)
            logger.info(f"Connected to channel: {chat.title}")
            
            # Check bot permissions in channel
            bot_member = await self.app.bot.get_chat_member(CHANNEL_ID, self.app.bot.id)
            if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                logger.warning("Bot is not an administrator in the channel!")
                await self.app.bot.send_message(
                    chat_id=USER_ID,
                    text="⚠️ Warning: Bot is not an administrator in the channel! It won't receive join events."
                )
            else:
                logger.info("Bot has administrator permissions in channel")
                
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            raise

    async def run(self):
        """Run the bot"""
        await self.initialize()
        
        # Start the bot
        logger.info("Starting bot...")
        await self.app.initialize()
        await self.app.start()
        
        # Start polling
        await self.app.updater.start_polling()
        
        logger.info("Bot is running! Press Ctrl+C to stop")
        
        # Keep the bot running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

async def main():
    """Main entry point"""
    if not all([TOKEN, CHANNEL_ID, USER_ID]):
        logger.error("Missing environment variables!")
        logger.error("Required: TELEGRAM_BOT_TOKEN, CHANNEL_ID, USER_ID")
        return
    
    bot = MemberMonitorBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
