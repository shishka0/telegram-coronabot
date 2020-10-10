import logging

import telegram
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, Filters

import core
import constants

MARKDOWN = telegram.parsemode.ParseMode.MARKDOWN

# Conversation states
HOME, TRENDS, REPORTS, ERROR = range(4)


# Helper functions
def send_message(update: Update, context: CallbackContext, message, **kwargs):
    """Send a message in the chat that generated the update
    Args:
        update (Update)
        context (CallbackContext)
        message (str): textual message to be sent
        **kwargs: arbitrary keyword arguments
    """
    context.bot.send_message(update.effective_chat.id, message, **kwargs)


def send_photo(update: Update, context: CallbackContext, photo, **kwargs):
    """Send a photo in the chat that generated the update
    Args:
        update (Update)
        context (CallbackContext)
        photo (file-like): textual message to be sent
        **kwargs: arbitrary keyword arguments
    """
    context.bot.send_photo(update.effective_chat.id, photo, **kwargs)


# Generic callbacks
def cb_error_handler(update: Update, context: CallbackContext):
    """Error handler"""
    try:
        raise context.error
    except NotImplementedError as e:
        logging.warning("Request for a not implemented function", e)
        send_message(update, context, "Questa funzione non è ancora disponibile")
    except Exception as e:
        logging.error("An exception could not be handled", e)
        send_message(update, context,
                     "Si è verificato un errore. Consulta le informazioni del comando /help oppure "
                     "riavvia la conversazione con /start.")


def cb_not_implemented(update: Update, context: CallbackContext):
    """Placeholder for not implemented functions
    Args:
        update (Update)
        context (CallbackContext)
    Raise:
        NotImplementedError
    """
    raise NotImplementedError("Handler not implemented")


def cb_prompt_start(update: Update, context: CallbackContext):
    """Prompt the start of the conversation when bot is inactive."""
    send_message(update, context, "La conversazione non è attiva. Digita /start per avviarla.")


def cb_start(update: Update, context: CallbackContext):
    """Start the conversation"""
    keyboard = telegram.ReplyKeyboardMarkup(
        [['Aiuto', 'Info'],
         ['Report'],
         ['Andamento']],
        one_time_keyboard=True
    )
    send_message(update, context,
                 "Benvenuto! Sono un *bot* pensato per raccogliere e mostrare i dati e le statistiche dell'infezione "
                 "del *SARS-CoV-2* in *Italia* in maniera semplice e diretta."
                 "\n\nSeleziona una funzione.\n\n_Ricorda che in qualsiasi momento puoi consultare il comando /help dove "
                 "puoi ottenere informazioni sulle azioni disponibili e sui formati delle richieste._",
                 reply_markup=keyboard, parse_mode=MARKDOWN)
    return HOME


def cb_stop(update: Update, context: CallbackContext):
    """Stop bot"""
    cb_not_implemented(update, context)
    return ConversationHandler.END


# Home state
def cb_home_help(update: Update, context: CallbackContext):
    """Help for the HOME state"""
    send_message(update, context,
                 "Invia un messaggio contenente una delle seguenti azioni:\n"
                 " *Aiuto*: visualizza questo messaggio di aiuto\n"
                 " *Info*: ricevi informazioni sul bot, sulle fonti e sull'autore\n"
                 " *Report*: ottieni un report completo su una località ed una data a scelta\n"
                 " *Trend*: visualizza i grafici e gli andamenti dell'infezione in località e periodi a scelta.\n"
                 "\nPer selezionare un'azione puoi anche utilizzare la tastiera alternativa che, se non si è aperta "
                 "in automatico, può essere aperta dal pulsante con i quattro quadretti a fianco della barra del "
                 "testo.",
                 parse_mode=MARKDOWN
                 )
    return HOME


def cb_info(update: Update, context: CallbackContext):
    """Send info about the bot"""
    cb_not_implemented(update, context)
    return HOME


# Reports state
def cb_report(update: Update, context: CallbackContext):
    """Show a full report"""
    send_message(
        update, context,
        "Manda un messaggio contenente il *luogo* e la *data* di tuo interesse separati da una virgola come nei "
        "seguenti esempi:\n"
        "  Roma, ieri\n"
        "  Piemonte, 1 Giugno 2020\n"
        "  Italia, 08/08/2020\n\n"
        "_Consulta /help per più informazioni sui report e come scrivere la tua richiesta_",
        parse_mode=MARKDOWN
    )
    return REPORTS


def cb_reports_help(update: Update, context: CallbackContext):
    """Help for the REPORTS state"""
    cb_not_implemented(update, context)
    return REPORTS


def cb_report_request(update: Update, context: CallbackContext):
    """Process a full report request"""
    request = update.message.text.lower()
    parser = core.ReportRequestParser()
    parser.parse(request)
    if parser.status is True:
        location, date = parser.result
        report = core.get_report(location, date)
        send_message(update, context, report, parse_mode=MARKDOWN)
    else:
        send_message(update, context, parser.error)
    return REPORTS


# Trends state
def cb_trends(update: Update, context: CallbackContext):
    """Trends state"""
    send_message(update, context, "Che trends?")
    return TRENDS


def cb_trends_help(update: Update, context: CallbackContext):
    """Help for the TRENDS state"""
    cb_not_implemented(update, context)
    return TRENDS


def cb_trends_request(update: Update, context: CallbackContext):
    """Process a trend request"""
    request = update.message.text.lower()
    parser = core.TrendRequestParser()
    parser.parse(request)
    if parser.status is True:
        stat, location, interval = parser.result
        try:
            graph = core.plot_trend(stat, location, interval)
        except KeyError as e:
            available_stats = sorted(map(lambda s: s.replace('_', ' ').capitalize(), e.args[0]))
            available_stats = ', '.join(available_stats)
            send_message(
                update, context,
                f"Non ci sono dati su '{stat}' per '{location}'. Ricorda che i dati pubblicati dalla Protezione Civile"
                f"sulle province, regioni e lo stato sono diversi.\n\nI dati disponibili per '{location}' sono: "
                f"{available_stats}."
            )
            return
        send_photo(update, context, graph)
    else:
        send_message(update, context, parser.error)
    return TRENDS


# Always active handlers
start_handler = CommandHandler('start', cb_start)
stop_handler = CommandHandler('stop', cb_stop)

conversation = ConversationHandler(
    entry_points=[
        start_handler,
        MessageHandler(Filters.all, cb_prompt_start)
    ],
    states={
        HOME: [
            CommandHandler('help', cb_home_help),
            MessageHandler(Filters.text('Aiuto'), cb_home_help),
            MessageHandler(Filters.text('Report'), cb_report),
            MessageHandler(Filters.text('Andamento'), cb_trends)
        ],
        REPORTS: [
            CommandHandler('help', cb_reports_help),
            MessageHandler(Filters.regex(constants.report_request), cb_report_request)
        ],
        TRENDS: [
            CommandHandler('help', cb_trends_help),
            MessageHandler(Filters.regex(constants.trend_request), cb_trends_request)
        ]
    },
    fallbacks=[start_handler, stop_handler]
)
