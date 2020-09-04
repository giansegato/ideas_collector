import logging
import pickle
from telegram import ReplyKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Filters,
    RegexHandler,
    ConversationHandler,
)
from trello import Trello

_CONV_STATE_SETUP_TOKEN, _CONV_STATE_SETUP_BOARD = range(2)

DEFAULT_LIST_NAME = 'inbox'
DEFAULT_CARD_NAME_LEN = 200

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


class App:
    _USER_SETUPS = None

    def __init__(self, project_name):
        self.project_name = project_name

    def load_users(self):
        try:
            self._USER_SETUPS = pickle.load(open("./data/{}_user_setup.p".format(self.project_name), "rb"))
        except FileNotFoundError:
            self._USER_SETUPS = {}

    def setup_user(self, tg_id, trello_token, chosen_board_id,
                   chosen_board_name,
                   inbox_list_id=''):
        self._USER_SETUPS[tg_id] = {
            'telegram_id': tg_id,
            'trello_token': trello_token,
            'board_id': chosen_board_id,
            'board_name': chosen_board_name,
            'inbox_list_id': inbox_list_id,
        }
        pickle.dump(self._USER_SETUPS, open("./data/{}_user_setup.p".format(self.project_name), "wb"))

    def get_tg_id(self, update):
        return update.message.from_user.id

    def is_user_setup(self, update):
        return self.get_tg_id(update) in self._USER_SETUPS

    def status(self, bot, update):
        logger.info("Got to status")
        update.message.reply_text("I'm here listening.", reply_markup=None)
        return ConversationHandler.END

    def setup(self, bot, update):
        logger.info("Got to setup")
        update.message.reply_text("Hi there! Welcome. First, tell me your Trello token.")
        return _CONV_STATE_SETUP_TOKEN

    def process_wong_trello_token_conv(self, bot, update, user_data):
        logger.info("Got to process_wong_trello_token_conv")
        update.message.reply_text("The token is invalid. Restart the process using /setup "
                                  "and then choose a valid one.\nEND.")
        user_data.clear()
        return ConversationHandler.END

    def process_trello_token_conv(self, bot, update, user_data):
        logger.info("Got to process_trello_token")

        trello_token = update.message.text.strip()

        trello = Trello(trello_token)
        starred_boards = trello.get_starred_boards()

        if starred_boards is None:
            update.message.reply_text(
                "Sorry, the token looks invalid. "
                "Restart the process using /setup and then "
                "choose a new, valid one.\nEND."
            )
            return ConversationHandler.END

        user_data["trello_token"] = trello_token

        update.message.reply_text(
            "Token validated successfully. Please choose, among these, your preferred board for "
            "ideas collection. There are listed only starred boards. "
            "If it's not among them, star your preferred board, and then restart the process.",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [
                        '{name} ({part_id})'.format(name=x['name'], part_id=x['id'][:4])
                        for k, x in starred_boards.items()
                    ],
                    ['/cancel']
                ],
                one_time_keyboard=True,
            ),
        )

        return _CONV_STATE_SETUP_BOARD

    def process_wong_trello_board_conv(self, bot, update, user_data):
        logger.info("Got to process_wong_trello_board_conv")
        update.message.reply_text("The board was not in the list. "
                                  "Star your chosen one, restart using /setup "
                                  "and then choose it from the list.\nEND.")
        user_data.clear()
        return ConversationHandler.END

    def process_trello_board_conv(self, bot, update, user_data):
        logger.info("Got to process_trello_board")

        trello_token = user_data["trello_token"]

        chosen_board_name = update.message.text.split("(")[0].strip()
        chosen_board_id = update.message.text.split("(")[1].replace(")", "")

        trello = Trello(trello_token)
        starred_boards = trello.get_starred_boards()

        if starred_boards is None:
            return self.error(update, user_data, "invalid trello token")

        candidate_boards = [v for k, v in starred_boards.items() if chosen_board_id in k]
        final_board = None
        for candidate_board in candidate_boards:
            if candidate_board['name'] == chosen_board_name:
                final_board = candidate_board
                break
        if final_board is None:
            return self.error(update, user_data, "No valid board found")
        else:
            chosen_board_id = final_board['id']
            chosen_board_name = final_board['name']

        board_lists = trello.get_board_lists(chosen_board_id)
        if board_lists is None:
            return self.error(update, {}, "Trello token expired. Restart doing /setup and "
                                          "then saving your stuff again.")

        inbox_list_id = None
        for k, l in board_lists.items():
            if l['name'] == DEFAULT_LIST_NAME:
                inbox_list_id = l['id']
                break
        else:
            if len(board_lists.items()) > 0:
                inbox_list_id = [v for k, v in board_lists.items()][0]['id']

        self.setup_user(tg_id=update.message.from_user.id,
                        trello_token=trello_token,
                        chosen_board_id=chosen_board_id,
                        chosen_board_name=chosen_board_name,
                        inbox_list_id=inbox_list_id)

        update.message.reply_text("Setup completed. You can now fully use the bot.")
        return ConversationHandler.END

    def cancel_conv(self, bot, update, user_data):
        logger.info("Cancel")
        update.message.reply_text("I've been obliviated. Fear no more.")
        user_data.clear()
        return ConversationHandler.END

    def error(self, update, user_data, error_name):
        logger.info("Error")
        update.message.reply_text("Something wrong happened: {}. "
                                  "Restart the process please.\nEND.".format(error_name))
        user_data.clear()
        return ConversationHandler.END

    def get_setup_handler(self):
        return ConversationHandler(
            entry_points=[CommandHandler("setup", self.setup)],
            states={
                _CONV_STATE_SETUP_TOKEN: [RegexHandler('^((\s+)?[a-f0-9]{64}(\s+)?)$',
                                                       self.process_trello_token_conv,
                                                       pass_user_data=True),
                                          MessageHandler(Filters.text,
                                                         self.process_wong_trello_token_conv,
                                                         pass_user_data=True)]
                ,
                _CONV_STATE_SETUP_BOARD: [
                    RegexHandler('^(.*) \([a-f0-9]{4}\)$',
                                 self.process_trello_board_conv,
                                 pass_user_data=True),
                    MessageHandler(Filters.text,
                                   self.process_wong_trello_board_conv,
                                   pass_user_data=True)],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_conv, pass_user_data=True),
            ]
        )

    def append_card(self, update, content, card_name,
                    list_name=None,
                    list_id=None,
                    content_type='text'):

        if (list_name is None) & (list_id is None):
            raise Exception("No list provided!")

        trello = Trello(self._USER_SETUPS[self.get_tg_id(update)]['trello_token'])

        if list_id is not None:
            list_name = DEFAULT_LIST_NAME
        else:
            board_lists = trello.get_board_lists(self._USER_SETUPS[self.get_tg_id(update)]['board_id'])
            if board_lists is None:
                return self.error(update, {}, "Trello token expired. Restart doing /setup and "
                                              "then saving your stuff again.")

            if list_name[0] == "_":
                list_name = list_name[1:]
                # Check if it already exists
                for k, l in board_lists.items():
                    if l['name'] == list_name:
                        list_id = l['id']
                        break
                else:
                    # NEW LIST!
                    list_id = trello.create_list_in_board(list_name,
                                                          self._USER_SETUPS[self.get_tg_id(update)]['board_id'])
            else:
                for k, l in board_lists.items():
                    if l['name'] == list_name:
                        list_id = l['id']
                        break
                else:
                    return self.error(update, {}, "No list found matching your choice. Restart please.")

        result = trello.create_card_in_list(list_id, card_name, content, content_type)
        logger.info("Done! Created card with ID: {}".format(result))
        update.message.reply_text("Done! Put the {} into #{} as *{}".format(content_type,
                                                                            list_name,
                                                                            card_name))
