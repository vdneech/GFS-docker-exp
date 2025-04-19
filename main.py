import os
import sqlite3
import time
from datetime import datetime, timezone
import pytz
import telebot
from dotenv import load_dotenv, find_dotenv
from telebot import types
from telebot.types import LabeledPrice

from functions import check_user_in_db, PROVIDER_DATA, user_counter
from functions import create_db, create_table, delete_user_from_db, check_reg_session, save_receipt, closing

# Загрузка .env
load_dotenv(find_dotenv())

ADMINS = os.getenv('ADMINS').split(', ')
ADMINS = [int(admin) for admin in ADMINS]
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
print(f'===Конфигурация админов.. {ADMINS}===')


# Обработчики платежей
# @bot.message_handler(commands=['pay'])
def pay(message):
    try:
        prices = [LabeledPrice(label='Организационный взнос', amount=int(os.getenv('PRICE')) * 100)]  # Сумма в копейках
        bot.send_invoice(chat_id=message.chat.id,
                         title='Оплата организационного взноса',
                         description='Нажмите на кнопку ниже, чтобы перейти к оплате',
                         invoice_payload='botpaid',
                         provider_token=os.getenv('PROVIDER_TOKEN'),
                         currency=os.getenv('CURRENCY'),
                         prices=prices,
                         need_email=True,
                         send_email_to_provider=True,
                         provider_data=PROVIDER_DATA,
                         photo_url='https://i.ibb.co/7JcyzQBN/3.png',
                         photo_width=1200,
                         photo_height=1500)

    except Exception as e:
        print(f'=====Ошибка обработчика Pay у пользователя {message.chat.id}: {e}=====')
        bot.send_message(message.chat.id, f"Произошла ошибка. Оплата не была проведена, свяжитесь с администратором.")


# Пре-чекаут
@bot.pre_checkout_query_handler(func=lambda query: True)
def precheckoutqueryhandler(precheckout_query):
    bot.answer_pre_checkout_query(precheckout_query.id, ok=True, error_message="Произошла ошибка")


# Обработчик успешной оплаты
@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    save_receipt(message.chat.id)
    count_of_users = user_counter()
    for admin in ADMINS:
        bot.send_message(admin,
                         f'Пользователь {message.chat.id} оплатил вступление\n--Осталось мест: {int(os.getenv('MAXIMUM_USERS')) - count_of_users}')
    count_of_users = user_counter()
    print(
        f'=====Пользователь {message.chat.id} оплатил вступление=====\n--Осталось мест: {int(os.getenv('MAXIMUM_USERS')) - count_of_users}')
    return bot.send_message(message.chat.id,
                            "Спасибо за оплату! Скоро с вами свяжется организатор."), bot.delete_message(
        message.chat.id, message.id - 1)


# Выслать таблицу админу
@bot.message_handler(commands=['excel'])
def excel(message):
    if message.chat.id in ADMINS:
        file = create_table()
        try:
            with open(file, 'rb') as doc:
                bot.send_document(message.chat.id, doc,
                                  caption=f'Вот ваш документ!')
            os.remove(file)
        except:
            bot.send_message(message.chat.id, 'Ни один пользователь еще не зарегистрирован.')
    else:
        bot.send_message(message.chat.id, 'Такой команды не существует!')


# Старт
@bot.message_handler(commands=['start'])
@bot.message_handler()
def start(message, interrupt=False):
    if message.text in ['/start', 'Вернуться в меню']:
        keyboard = types.InlineKeyboardMarkup()
        register_button, format_button, ceo_button = (types.InlineKeyboardButton(text="Регистрация",
                                                                                 callback_data="register"),
                                                      types.InlineKeyboardButton(
                                                          text="Формат мероприятия",
                                                          callback_data='format'),
                                                      types.InlineKeyboardButton(text="Сотрудничество",
                                                                                 callback_data="ceo"))
        keyboard.row(register_button, format_button)
        keyboard.row(ceo_button)
        con = sqlite3.connect('/data/GFS.db')
        if check_user_in_db(message.chat.id):
            con.execute(f'INSERT INTO users (chat_id, telegram, date_of_register) VALUES (?, ?, ?);',
                        (message.chat.id, message.from_user.username,
                         datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M')))

            print(f'=====Пользователь {message.chat.id} добавлен в базу=====')
        con.commit()
        con.close()
        text = f'''Здравствуйте, {message.from_user.first_name}.
                             \nЭто команда Гостевых сезонов!
                             \nВыберите интересующее вас действие: '''
        if interrupt:
            bot.send_message(message.chat.id,
                             text='<b>Регистрация была прервана командой.</b>\n\n' + text,
                             parse_mode='HTML',
                             reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id,
                             text=text,
                             parse_mode='HTML',
                             reply_markup=keyboard)


def from_where(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    instagram = types.KeyboardButton("Instagram")
    telegram = types.KeyboardButton("Telegram")
    not_first = types.KeyboardButton("Уже был на мероприятии")
    recomendations = types.KeyboardButton("Рекомендации коллег/друзей")

    cancel = types.KeyboardButton("Отмена")
    markup.add(cancel, instagram, telegram, not_first, recomendations)

    if message.text is None:
        mesg = bot.send_message(message.chat.id, "Пришлите данные сообщением", reply_markup=markup)
        return bot.register_next_step_handler(mesg, reg_name)
    if message.text[0] == '/':
        delete_user_from_db(message.chat.id)
        return start(message, interrupt=True)
    elif message.text not in [None, 'Отмена', 'Вернуться в меню']:
        # typing(message)
        con = sqlite3.connect('/data/GFS.db')
        con.execute(f'UPDATE users SET from_where = ? WHERE chat_id = {message.chat.id};', (message.text,))
        con.commit()
        con.close()
        msg = bot.send_message(message.chat.id,
                               'Откуда вы узнали о нас?',
                               reply_markup=markup)
        bot.register_next_step_handler(msg, reg_name)


# Добавление имени и запрос пищ. ограничений
def reg_name(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    prompt = types.KeyboardButton("-")
    cancel = types.KeyboardButton("Отмена")
    markup.add(cancel, prompt)
    if message.text is None:
        mesg = bot.send_message(message.chat.id, "Пришлите данные сообщением", reply_markup=markup)
        return bot.register_next_step_handler(mesg, reg_name)
    if message.text[0] == '/':
        delete_user_from_db(message.chat.id)
        return start(message, interrupt=True)
    elif message.text not in [None, 'Отмена', 'Вернуться в меню']:
        # typing(message)
        con = sqlite3.connect('/data/GFS.db')
        con.execute(f'UPDATE users SET name = ? WHERE chat_id = {message.chat.id};', (message.text,))
        con.commit()
        con.close()
        msg = bot.send_message(message.chat.id,
                               'Продолжим. Укажите информацию о наличии пищевых ограничений.\n\nЕсли ограничений нет, пришлите минус "-"',
                               reply_markup=markup)
        bot.register_next_step_handler(msg, food_restriction)

    elif message.text in ['Отмена']:
        check_cancel(message)
        try:
            for i in range(0, 2):
                bot.delete_message(message.chat.id, message.id - i)
        except:
            print('--Не удалось удалить сообщение--')


# Добавление пищевого ограничения и просьба прислать уч. зав
def food_restriction(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel = types.KeyboardButton("Отмена")
    markup.add(cancel)
    if message.text is None:
        mesg = bot.send_message(message.chat.id,
                                "Пришлите данные сообщением", reply_markup=markup)
        return bot.register_next_step_handler(mesg, food_restriction)
    if message.text[0] == '/':
        delete_user_from_db(message.chat.id)
        return start(message, interrupt=True)
    elif message.text not in [None, 'Отмена', 'Вернуться в меню']:
        con = sqlite3.connect('/data/GFS.db')
        con.execute(
            f'UPDATE users SET food_restriction = "{message.text}" WHERE chat_id = {message.chat.id}')
        con.commit()
        con.close()
        mesg = bot.send_message(message.chat.id,
                                "Давайте уточним Ваше место работы (или учебы) и специализацию.\n\nЭто необходимо нам для некоторой статистики.\n\nПример:\n<b>Hollywood Smile ортодонт / КубГМУ 5 курс</b>",
                                parse_mode='HTML', reply_markup=markup)
        bot.register_next_step_handler(mesg, study)
    elif message.text in ['Отмена']:
        check_cancel(message)
        try:
            for i in range(0, 4):
                bot.delete_message(message.chat.id, message.id - i)
        except:
            print('--Не удалось удалить сообщение--')


# Добавление уч. заведения и просьба прислать номер
def study(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_phone = types.KeyboardButton(text='Прислать номер', request_contact=True)
    cancel = types.KeyboardButton("Отмена")
    markup.row(cancel, button_phone)
    if message.text is None:
        mesg = bot.send_message(message.chat.id, "Пришлите данные сообщением", reply_markup=markup)
        return bot.register_next_step_handler(mesg, study)
    if message.text[0] == '/':
        delete_user_from_db(message.chat.id)
        return start(message, interrupt=True)
    elif message.text not in [None, 'Отмена', 'Вернуться в меню']:
        con = sqlite3.connect('/data/GFS.db')
        con.execute(f'UPDATE users SET study = "{message.text}" WHERE chat_id = {message.chat.id}')
        con.commit()
        con.close()
        keyboard = types.ReplyKeyboardMarkup()
        cancel = types.KeyboardButton("Отмена")
        button_phone = types.KeyboardButton(text='Прислать номер', request_contact=True)
        keyboard.row(button_phone, cancel)

        mesg = bot.send_message(message.chat.id,
                                "Далее укажите номер телефона для связи с Вами.\n\nДля этого нажмите на кнопку «Прислать номер» или напишите его в виде «7XXXXXXXXXX»",
                                reply_markup=markup)
        bot.register_next_step_handler(mesg, contact)
    elif message.text in ['Отмена']:
        check_cancel(message)
        try:
            for i in range(0, 6):
                bot.delete_message(message.chat.id, message.id - i)
        finally:
            print('--Не удалось удалить сообщение--')


# Добавление контакта и переход к оплате
def contact(message):
    keyboard = types.InlineKeyboardMarkup()
    payment_button = types.InlineKeyboardButton(text="Оплатил", callback_data="successful_payment")
    con = sqlite3.connect('/data/GFS.db')
    if closing():
        return bot.send_message(message.chat.id,
                                'Номер добавлен, но…\n\nК сожалению, места закончились. Оплата невозможна.\n\nНе расстраивайтесь, мы можем внести Вас список ожидания. При освобождении места, мы непременно свяжемся.\n\nСледите за нашими новостями, чтобы первыми узнать о новом сезоне.')
    if message.contact:
        keyboard.row(payment_button)
        con.execute(
            f'UPDATE users SET phone = "{message.contact.phone_number}" WHERE chat_id = {message.chat.id}')
        con.commit()
        con.close()
        return bot.send_message(message.chat.id,
                                'Стоимость организационного взноса — 5000₽.\n\nОплатить можно нажатием на кнопку ниже.',
                                parse_mode='HTML'), pay(message)
    if message.text:
        if message.text[0] == '/':
            delete_user_from_db(message.chat.id)
            return start(message, interrupt=True)
        elif len(str(message.text)) == 11 and str(message.text[0]) == '7':
            keyboard.row(payment_button)
            con.execute(
                f'UPDATE users SET phone = {message.text} WHERE chat_id = {message.chat.id}')
            con.commit()
            con.close()
            bot.send_message(message.chat.id,
                             'Стоимость организационного взноса — 5000₽.\n\nОплатить можно нажатием на кнопку ниже.',
                             parse_mode='HTML')
            pay(message)
        elif message.text == 'Отмена':
            check_cancel(message)
            try:
                for i in range(0, 8):
                    bot.delete_message(message.chat.id, message.id - i)
            finally:
                print('--Не удалось удалить сообщение--')
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            button_phone = types.KeyboardButton(text='Прислать номер', request_contact=True)
            cancel = types.KeyboardButton("Отмена")
            markup.row(cancel, button_phone)
            mesg = bot.send_message(message.chat.id,
                                    "Пришлите корректный номер телефона", reply_markup=markup)
            return bot.register_next_step_handler(mesg, contact)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        button_phone = types.KeyboardButton(text='Прислать номер', request_contact=True)
        cancel = types.KeyboardButton("Отмена")
        markup.row(cancel, button_phone)
        mesg = bot.send_message(message.chat.id,
                                "Пришлите корректный номер телефона", reply_markup=markup)
        return bot.register_next_step_handler(mesg, contact)


# Коллбэки
@bot.callback_query_handler(func=lambda call: True)
def callbacks(callback):
    keyboard = types.InlineKeyboardMarkup()
    register_button, ceo_button, format_button = (types.InlineKeyboardButton(text="Регистрация",
                                                                             callback_data="register"),
                                                  types.InlineKeyboardButton(text="Сотрудничество",
                                                                             callback_data="ceo"),
                                                  types.InlineKeyboardButton(text='Формат мероприятия',
                                                                             callback_data='format'))
    if callback.message:
        # Регистрация
        if callback.data == 'register':
            # Проверка есть ли в базе
            if check_user_in_db(callback.message.chat.id):
                con = sqlite3.connect('/data/GFS.db')
                print(datetime.now(pytz.timezone('Europe/Moscow')))
                con.execute(f'INSERT INTO users (chat_id, telegram, date_of_register) VALUES (?, ?, ?);',
                            (callback.message.chat.id, callback.from_user.username,
                             datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M')))

                print(f'=====Пользователь {callback.message.chat.id} добавлен в базу=====',
                      datetime.now(pytz.timezone('Europe/Moscow')))
                con.commit()
                con.close()
            # Проверка регистрационной сессии
            if check_reg_session(callback.message.chat.id):
                bot.edit_message_text(chat_id=callback.message.chat.id,
                                      text='Процесс регистрации уже идет или пройден. Пожалуйста, прочтите сообщения от бота.',
                                      message_id=callback.message.id)
                text_to_paste = callback.message.text
                keyboard = types.InlineKeyboardMarkup()
                register_button, format_button, ceo_button, miniapp_button = types.InlineKeyboardButton(
                    text="Регистрация", callback_data="register"), types.InlineKeyboardButton(text="Формат мероприятия",
                                                                                              callback_data='format'), types.InlineKeyboardButton(
                    text="Сотрудничество", callback_data="ceo"), types.InlineKeyboardButton(text='Мини-приложение',
                                                                                            url='https://miniapp-quicksilver.amvera.io/')
                keyboard.row(register_button, format_button)
                keyboard.row(ceo_button)

                return time.sleep(5), bot.edit_message_text(chat_id=callback.message.chat.id, text=text_to_paste,
                                                            message_id=callback.message.id, reply_markup=keyboard)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            prompt = types.KeyboardButton("Отмена")
            markup.add(prompt)
            mesg = bot.send_message(callback.message.chat.id,
                                    '<b>Регистрация</b>\n\nПеред тем, как зарегистрироваться, нам необходимы некоторые данные.\n\nНачнём с фамилии и имени.\n\nПример: <b>Питер Доусон</b>',
                                    parse_mode='HTML', reply_markup=markup)
            bot.register_next_step_handler(mesg, from_where)
    # Формат мероприятия
    if callback.data == 'format':
        keyboard.row(register_button)
        keyboard.row(ceo_button)
        bot.send_message(callback.message.chat.id,
                         '<b>Формат мероприятия</b>\n\nМы запускаем цикл открытых образовательных мероприятий с уникальной возможностью как получить знания, так и поделиться ими. Иными словами выступить гостем в роли слушателя, либо спикера.\n\n«Гостевые сезоны» — стартовый проект по типу открытого микрофона, который стоит использовать для улучшения уже существующих, а так же создания новых продуктов.\n\nВерим, что у нас получится сформировать новое отношение к образованию в стоматологии и повысить стандарты в индустрии. Ведь то, что мы потребляем, формирует нас.\n\nНа мероприятии можно открыто обсуждать и дискуссировать, оспаривать и критиковать. Мы за открытое общение и поиск наиболее оптимального подхода к решению проблем.',
                         parse_mode='HTML', reply_markup=keyboard)
    # Сотрудничество
    if callback.data == 'ceo':
        keyboard.row(register_button)
        keyboard.row(format_button)
        bot.send_message(callback.message.chat.id,
                         '<b>Сотрудничество</b>\n\nНаше сообщество принимает различные предложения по сотрудничеству. Все вопросы и готовые предложения можете отправлять Владимиру Чепурняку.\n\nКонтакты:\n\nTelegram — @vchepurnyak\nПочта — vm@chepurnyak.ru\nТелефон — +7(988)285-84-84',
                         parse_mode='HTML', reply_markup=keyboard)


# Отмена регистрации
def check_cancel(message):
    delete_user_from_db(message.chat.id)
    keyboard = types.InlineKeyboardMarkup()
    register_button, format_button, ceo_button = (
        types.InlineKeyboardButton(text="Регистрация", callback_data="register"),
        types.InlineKeyboardButton(text="Формат мероприятия", callback_data='format'),
        types.InlineKeyboardButton(text="Сотрудничество", callback_data="ceo"))
    keyboard.row(register_button, format_button)
    msg = bot.send_message(message.chat.id, 'Отменяю')
    dots = '.'
    canceling = 'Отменяю'
    for i in range(3):
        canceling = canceling + dots
        bot.edit_message_text(text=canceling, chat_id=message.chat.id, message_id=msg.id)
        time.sleep(0.2)
    start(message)
    bot.edit_message_text(
        'Предыдущая регистрация была отменена вами, данные не сохранены. Чтобы начать заново, нажмите кнопку ниже.',
        chat_id=message.chat.id, message_id=msg.id, reply_markup=keyboard)


if __name__ == '__main__':
    time.sleep(30)
    print('--Запуск...')
    create_db()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
