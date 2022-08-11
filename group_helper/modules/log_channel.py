
from functools import wraps
import logging as logging_m
from typing import Optional

from group_helper import CONFIG
from group_helper.modules.helper_funcs.chat_status import user_admin
# from group_helper.modules.database import log_channel_sql as sql
from group_helper.modules.database import log_channel_mongo as sql
from group_helper.modules.tr_engine.strings import tld

from telegram import Bot, Update, ParseMode, Message, Chat
from telegram.error import BadRequest, Unauthorized
from telegram.ext import CommandHandler
from telegram.ext.callbackcontext import CallbackContext
from telegram.utils.helpers import escape_markdown


def loggable(func):
    @wraps(func)
    def log_action(update: Update, context: CallbackContext, *args, **kwargs):
        try:
            result = func(update, context, *args, **kwargs)
        except Exception:
            return
        chat = update.effective_chat  # type: Optional[Chat]
        message = update.effective_message  # type: Optional[Message]
        if result:
            if chat.type == chat.SUPERGROUP and chat.username:
                result += tld(chat.id, "log_channel_link").format(
                    chat.username, message.message_id)
            log_chat = sql.get_chat_log_channel(chat.id)
            if log_chat:
                send_log(context.bot, log_chat, chat.id, result)
        elif result == "":
            pass
        else:
            logging_m.warning(
                "%s was set as loggable, but had no return statement.", func)

        return result

    return log_action


def send_log(bot: Bot, log_chat_id: str, orig_chat_id: str, result: str):
    try:
        bot.send_message(log_chat_id, result, parse_mode=ParseMode.HTML)
    except BadRequest as excp:
        if excp.message == "Chat not found":
            bot.send_message(orig_chat_id,
                             "This log channel has been deleted - unsetting.")
            sql.stop_chat_logging(orig_chat_id)
        else:
            logging_m.warning(excp.message)
            logging_m.warning(result)
            logging_m.exception("Could not parse")

            bot.send_message(
                log_chat_id, result +
                "\n\nFormatting has been disabled due to an unexpected error.")


@user_admin
def logging(update: Update, context: CallbackContext):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]

    log_channel = sql.get_chat_log_channel(chat.id)
    if log_channel:
        try:
            log_channel_info = context.bot.get_chat(log_channel)
            message.reply_text(tld(chat.id,
                                   "log_channel_grp_curr_conf").format(
                                       escape_markdown(log_channel_info.title),
                                       log_channel),
                               parse_mode=ParseMode.MARKDOWN)
        except Exception:
            return
    else:
        message.reply_text(tld(chat.id, "log_channel_none"))


@user_admin
def setlog(update: Update, context: CallbackContext):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    if chat.type == chat.CHANNEL:
        message.reply_text(tld(chat.id, "log_channel_fwd_cmd"))

    elif message.forward_from_chat:
        sql.set_chat_log_channel(chat.id, message.forward_from_chat.id)
        try:
            message.delete()
        except BadRequest as excp:
            if excp.message == "Message to delete not found":
                pass
            else:
                logging_m.exception(
                    "Error deleting message in log channel. Should work anyway though."
                )

        try:
            context.bot.send_message(
                message.forward_from_chat.id,
                tld(chat.id,
                    "log_channel_chn_curr_conf").format(chat.title
                                                        or chat.first_name))
        except Unauthorized as excp:
            if excp.message == "Forbidden: bot is not a member of the channel chat":
                context.bot.send_message(
                    chat.id, tld(chat.id, "log_channel_link_success"))
            else:
                logging_m.exception("ERROR in setting the log channel.")

        context.bot.send_message(chat.id,
                                 tld(chat.id, "log_channel_link_success"))

    else:
        message.reply_text(tld(chat.id, "log_channel_invalid_message"),
                           ParseMode.MARKDOWN)


@user_admin
def unsetlog(update: Update, context: CallbackContext):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]

    log_channel = sql.stop_chat_logging(chat.id)
    if log_channel:
        try:
            context.bot.send_message(
                log_channel,
                tld(chat.id, "log_channel_unlink_success").format(chat.title))
            message.reply_text(tld(chat.id, "Log channel has been un-set."))
        except Exception:
            print("Nut")
    else:
        message.reply_text(tld(chat.id, "log_channel_unlink_none"))


def __stats__():
    return "• `{}` log channels set.".format(sql.num_logchannels())


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = True

LOG_HANDLER = CommandHandler("logchannel", logging, run_async=True)
SET_LOG_HANDLER = CommandHandler("setlog", setlog, run_async=True)
UNSET_LOG_HANDLER = CommandHandler("unsetlog", unsetlog, run_async=True)

CONFIG.dispatcher.add_handler(LOG_HANDLER)
CONFIG.dispatcher.add_handler(SET_LOG_HANDLER)
CONFIG.dispatcher.add_handler(UNSET_LOG_HANDLER)
