from bot.telegram_bot import TelegramBot
from config import TOKEN



if __name__ == "__main__":
    """
    Main entry point for executing the bot.

    Initializes and starts the TelegramBot instance with the provided token.
    Initializes sqlite
    """
        
    bot = TelegramBot(TOKEN)
    bot.start_bot()
