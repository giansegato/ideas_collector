from app import App, logger, DEFAULT_CARD_NAME_LEN

from telegram import ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    RegexHandler,
    ConversationHandler,
)
from config import TG_TOKEN_IDEAS, PROJECT_NAME_COLLECTOR
from trello import Trello
import re

_CONV_STATE_CHOOSE_LIST = 101

app = App(PROJECT_NAME_COLLECTOR)


def extract_commands_from_text(message):
    if message is None:
        return None, None, message

    extract_commands_regex = r'((in #([^\s]+))$|(as \*([^\s]+))$)|(in #([^\s]+) as *([^\s]+))$'
    command = ""
    for finding in re.findall(extract_commands_regex, message):
        if type(finding) == str:
            if (finding != '') & (finding != '_') & (finding != ' '):
                command = finding
                break
        elif type(finding) == tuple:
            for f in finding:
                if (f != '') & (f != '_') & (f != ' '):
                    command = f
                    break

    if command == "":
        return None, None, message

    message = message.split(command)[0]

    get_list_name_regex = r'in #([^\s]+)'
    findings = []
    for finding in re.findall(get_list_name_regex, command):
        if type(finding) == str:
            if (finding != '') & (finding != '_') & (finding != ' '):
                findings.append(finding)
        elif type(finding) == tuple:
            for f in finding:
                if (f != '') & (f != '_') & (f != ' '):
                    findings.append(f)

    if len(findings) == 0:
        chosen_list_name = None
    else:
        chosen_list_name = findings[-1]

    get_card_name_regex = r'as \*([^\s]+)'
    findings = []
    for finding in re.findall(get_card_name_regex, command):
        if type(finding) == str:
            if (finding != '') & (finding != ' '):
                findings.append(finding)
        elif type(finding) == tuple:
            for f in finding:
                if (f != '') & (f != '_') & (f != ' '):
                    findings.append(f)

    if len(findings) == 0:
        chosen_card_name = message[:DEFAULT_CARD_NAME_LEN]
        if chosen_card_name == '':
            chosen_card_name = None
    else:
        chosen_card_name = findings[-1].strip()

    return chosen_list_name, chosen_card_name, message.strip()


def start(bot, update):
    logger.info("Got /start or /help")
    update.message.reply_text(
        """
        Hi there!\n{}
        You can use the shortcut mode in this way:\n
        - anything in #list_name as *card_name
        - anything in #list_name
        - anything as *card_name
        """.format(
            "First, using /setup you should authenticate your Trello account.\n"
            if update.message.from_user.id not in app._USER_SETUPS
            else ""
        )
    )
    return ConversationHandler.END


def process_shortcut_mode(bot, update):
    if not app.is_user_setup(update):
        update.message.reply_text("You are not authenticated yet. Use /setup please.")
        return

    chosen_list_name, chosen_card_name, content = extract_commands_from_text(update.message.text)

    content_type = 'text'
    if len(update.message.entities) > 0:
        if update.message.entities[0].type == 'url':
            content_type = 'url'

    kwargs = {
        'content': content,
        'content_type': content_type,
        'card_name': chosen_card_name,
        'update': update,
    }

    if chosen_list_name is None:
        inbox_list_id = app._USER_SETUPS[app.get_tg_id(update)]['inbox_list_id']
        if inbox_list_id:
            kwargs['list_id'] = inbox_list_id
            logger.info("I will insert the file {} in the list {} with the name {}.".format(
                content, inbox_list_id, chosen_card_name
            ))
        else:
            update.message.reply_text("No default list provided! "
                                      "Re-run the setup with at least a list please.")
    else:
        kwargs['list_name'] = chosen_list_name
        logger.info("I will insert the file {} in the list {} with the name {}.".format(
            content, chosen_list_name, chosen_card_name
        ))

    app.append_card(**kwargs)


def process_anything_text(bot, update, user_data):
    if not app.is_user_setup(update):
        update.message.reply_text("You are not authenticated yet. Use /setup please.")
        user_data.clear()
        return

    content = update.message.text
    content_type = 'text'
    if len(update.message.entities) > 0:
        if update.message.entities[0].type == 'url':
            content_type = 'url'

    user_data['_content'] = content
    user_data['_content_type'] = content_type
    user_data['_card_name'] = str(content)[:DEFAULT_CARD_NAME_LEN] if content_type != 'url' else content

    trello = Trello(app._USER_SETUPS[app.get_tg_id(update)]['trello_token'])
    board_lists = trello.get_board_lists(app._USER_SETUPS[app.get_tg_id(update)]['board_id'])

    if board_lists is None:
        board_lists = []

    update.message.reply_text(
        "Where do you want to save it?",
        reply_markup=ReplyKeyboardMarkup(
            [
                [
                    '#{list_name}'.format(list_name=l['name']) for k, l in board_lists.items()
                ],
                ['/cancel']
            ],
            one_time_keyboard=True,
        ),
    )

    return _CONV_STATE_CHOOSE_LIST


def process_trello_list_conv(bot, update, user_data):
    if not app.is_user_setup(update):
        update.message.reply_text("You are not authenticated yet. Use /setup please.")
        user_data.clear()
        return

    content = user_data['_content']
    content_type = user_data['_content_type']

    choice = update.message.text
    if choice == ".":
        chosen_list_name = None
        chosen_card_name = user_data['_card_name']
    else:
        if choice[0] == '#':
            choice = 'in ' + choice
        chosen_list_name, chosen_card_name, _ = extract_commands_from_text(choice)
        if chosen_card_name is None:
            chosen_card_name = user_data['_card_name']

    kwargs = {
        'content': content,
        'content_type': content_type,
        'card_name': chosen_card_name,
        'update': update,
    }

    if chosen_list_name is None:
        inbox_list_id = app._USER_SETUPS[app.get_tg_id(update)]['inbox_list_id']
        if inbox_list_id:
            kwargs['list_id'] = inbox_list_id
            logger.info("I will insert the file {} in the list {} with the name {}.".format(
                content, inbox_list_id, chosen_card_name
            ))
        else:
            update.message.reply_text("No default list provided! "
                                      "Re-run the setup with at least a list please.")
    else:
        kwargs['list_name'] = chosen_list_name
        logger.info("I will insert the file {} in the list {} with the name {}.".format(
            content, chosen_list_name, chosen_card_name
        ))

    app.append_card(**kwargs)

    return ConversationHandler.END


def process_wong_trello_list_conv(bot, update, user_data):
    update.message.reply_text("Your choice is not valid. Please restart.")
    user_data.clear()
    return ConversationHandler.END


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

    command = update.message.caption
    if command is not None:
        command = ('in ' + command) if command[0] == "#" else command
    chosen_list_name, chosen_card_name, _ = extract_commands_from_text(command)
    if chosen_card_name is None:
        chosen_card_name = file_id[:10]

    kwargs = {
        'content': content,
        'content_type': content_type,
        'card_name': chosen_card_name,
        'update': update,
    }

    if chosen_list_name is None:
        inbox_list_id = app._USER_SETUPS[app.get_tg_id(update)]['inbox_list_id']
        if inbox_list_id:
            kwargs['list_id'] = inbox_list_id
            logger.info("I will insert the file {} in the list {} with the name {}.".format(
                content, inbox_list_id, chosen_card_name
            ))
        else:
            update.message.reply_text("No default list provided! "
                                      "Re-run the setup with at least a list please.")
    else:
        kwargs['list_name'] = chosen_list_name
        logger.info("I will insert the file {} in the list {} with the name {}.".format(
            content, chosen_list_name, chosen_card_name
        ))

    app.append_card(**kwargs)


app.load_users()


# Telegram messages handler
updater = Updater(token=TG_TOKEN_IDEAS)

# Get the dispatcher to register handlers
dp = updater.dispatcher

debug = False
if debug:

    dp.add_handler(MessageHandler(Filters.text, lambda b, update: print(update.message.text)))
    dp.add_handler(MessageHandler(Filters.photo, lambda b, update: print(update.message.text)))

else:

    dp.add_handler(CommandHandler("status", app.status))
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", start))

    dp.add_handler(app.get_setup_handler())

    dp.add_handler(RegexHandler('^(.*)(( in #((_)?)([^\s]+))|( as \*([^\s]+)))$',
                                process_shortcut_mode))

    dp.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.text,
                                     process_anything_text,
                                     pass_user_data=True)],
        states={
            _CONV_STATE_CHOOSE_LIST: [RegexHandler('(^(in )?((#((_)?)([^\s]+))( as \*([^\s]+))?)$)|(^\.$)',
                                                   process_trello_list_conv,
                                                   pass_user_data=True),
                                      MessageHandler(Filters.text,
                                                     process_wong_trello_list_conv,
                                                     pass_user_data=True)]
        },
        fallbacks=[
            CommandHandler("cancel", app.cancel_conv, pass_user_data=True),
        ]
    )
    )

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
