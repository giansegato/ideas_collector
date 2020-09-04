from app import App, logger, DEFAULT_CARD_NAME_LEN

from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
)
from config import TG_TOKEN_GDT, PROJECT_NAME_GTD


app = App(PROJECT_NAME_GTD)


def start(bot, update):
    logger.info("Got /start or /help")
    update.message.reply_text(
        """
        Hi there!\n{}
        """.format(
            "First, using /setup you should authenticate your Trello account.\n"
            if update.message.from_user.id not in app._USER_SETUPS
            else ""
        )
    )
    return ConversationHandler.END


def process_anything_text(bot, update):
    if not app.is_user_setup(update):
        update.message.reply_text("You are not authenticated yet. Use /setup please.")
        return

    content = update.message.text
    content_type = 'text'
    card_name = str(content)[:DEFAULT_CARD_NAME_LEN]

    inbox_list_id = app._USER_SETUPS[app.get_tg_id(update)]['inbox_list_id']
    if inbox_list_id:
        app.append_card(content=content,
                        content_type=content_type,
                        card_name=card_name,
                        list_id=inbox_list_id,
                        update=update)
        return
    else:
        update.message.reply_text("No default list provided! Re-run the setup with at least a list please.")


def process_anything_file(bot, update):
    if not app.is_user_setup(update):
        update.message.reply_text("You are not authenticated yet. Use /setup please.")
        return

    if len(update.message.photo) > 0:
        photo = update.message.photo[-1]
        file_id = photo.file_id
        content = photo.get_file().file_path
        content_type = 'image'
    else:
        file = update.message.document[-1]
        file_id = file.file_name
        # mime_type = file.mime_type
        content = file.get_file().file_path
        content_type = 'document'

    chosen_card_name = update.message.caption
    if chosen_card_name is None:
        chosen_card_name = file_id

    inbox_list_id = app._USER_SETUPS[app.get_tg_id(update)]['inbox_list_id']
    if inbox_list_id:
        app.append_card(content=content,
                        content_type=content_type,
                        card_name=chosen_card_name,
                        list_id=inbox_list_id,
                        update=update)
        return
    else:
        update.message.reply_text("No default list provided! Re-run the setup with at least a list please.")


app.load_users()

# Telegram messages handler
updater = Updater(token=TG_TOKEN_GDT)

# Get the dispatcher to register handlers
dp = updater.dispatcher

dp.add_handler(CommandHandler("status", app.status))
dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("help", start))

dp.add_handler(app.get_setup_handler())

dp.add_handler(MessageHandler(Filters.text,
                              process_anything_text))

dp.add_handler(MessageHandler(Filters.photo,
                              process_anything_file))

dp.add_handler(MessageHandler(Filters.document,
                              process_anything_file))

# Start the Bot
updater.start_polling()

# Run the bot until you press Ctrl-C or the process receives SIGINT,
# SIGTERM or SIGABRT. This should be used most of the time, since
# start_polling() is non-blocking and will stop the bot gracefully.

logger.info("Bot is idle, listening")
updater.idle()