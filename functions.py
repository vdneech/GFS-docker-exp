import json
import os
import sqlite3
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv, find_dotenv
import pytz

load_dotenv(find_dotenv())


# Создание базы


def create_db():
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
            (telegram TEXT,
            chat_id INT,
            name TEXT DEFAULT NULL,
            study TEXT DEFAULT NULL,
            food_restriction TEXT DEFAULT NULL,
            phone INTEGER DEFAULT NULL,
            paid INT,
            from_where TEXT DEFAULT NULL,
            date_of_register TEXT DEFAULT NULL,
            date_of_payment TEXT DEFAULT NULL
            )''')
    cn.commit()
    cn.close()
    print('=====База создана=====')


# Выбрать всех из базы

def data_selector():
    try:
        cur = sqlite3.connect('data/GFS.db').cursor()
        cur.execute(
            'SELECT telegram, from_where, name, study, food_restriction, phone, paid, date_of_register, date_of_payment FROM users')
        users = cur.fetchall()
        return users
    except:
        return None


# Обновление датафрейма для добавления новых пользователей

def update_excel_with_values(file_path: str, values):
    values = values[:9]
    values = list(values)
    values[6] = 'Не оплатил(а)' if values[6] is None else 'Оплатил(а)'
    values = tuple(values)
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
    except FileNotFoundError:
        df = pd.DataFrame(
            columns=['Telegram', 'Откуда', 'ФИО', 'Деятельность', 'Пищ. ограничения', 'Телефон', 'Оплата',
                     'Регистрация',
                     'Время Оплаты'])

    new_row = pd.DataFrame([values],
                           columns=['Telegram', 'Откуда', 'ФИО', 'Деятельность', 'Пищ. ограничения', 'Телефон',
                                    'Оплата',
                                    'Регистрация', 'Время Оплаты'])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(file_path, index=False, engine='openpyxl')


# Создание эксель-таблицы


def create_table():
    file_path = 'Пользователи.xlsx'
    users = data_selector()
    if users is None:
        return None
    for user in users:
        update_excel_with_values(file_path, user)
    return file_path


# Удаление пользователя из базы

def delete_user_from_db(chat_id: int):
    cn = sqlite3.connect('data/GFS.db')
    cn.execute(f'DELETE FROM users WHERE chat_id = {chat_id}')
    cn.commit()
    cn.close()
    return print(f'=====Пользователь {chat_id} удален из базы данных=====')


# Проверка пользователя в базе по chat_id

def check_user_in_db(chat_id: int) -> bool:
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute(f'SELECT chat_id FROM users WHERE chat_id = {chat_id}')
    user = cursor.fetchone()
    if user:
        return False
    return True


# Выборка оплативших пользователей

def check_payment(chat_id: int) -> bool:
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute(f'SELECT paid FROM users WHERE chat_id == {chat_id}')
    status = cursor.fetchone()
    if status is None:
        return False
    if status[0] is not None:
        return True
    return False


# Проверка регистрационной сессии


def check_reg_session(telegram: int) -> bool:
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute(f'SELECT chat_id, name, food_restriction, study, phone FROM users WHERE chat_id = {telegram}')
    session = cursor.fetchone()
    cn.close()
    if session is None:
        return False
    for column in session[1:4]:
        if column is not None:
            return True
        else:
            return False


# Сохранение в базе статуса оплатившего


def save_receipt(chat_id):
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute(
        'UPDATE users SET paid = ?, date_of_payment = ? WHERE chat_id = ?',
        (1, datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M'), chat_id)
    )
    cn.commit()
    cn.close()


# Выбрать данные оплативших


def get_receipts():
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute(
        "SELECT telegram, name, paid, food_restriction, study, phone FROM users WHERE paid IS NOT NULL")
    data = cursor.fetchall()
    cn.close()
    return data


# Проверка на ограничение


def closing() -> bool:
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute("SELECT chat_id FROM users WHERE paid IS NOT NULL")
    data = cursor.fetchall()
    if len(data) == int(os.getenv('MAXIMUM_USERS')):  # <-- Ограничение
        return True
    return False


# Количество пользователей

def user_counter():
    cn = sqlite3.connect('data/GFS.db')
    cursor = cn.cursor()
    cursor.execute("SELECT chat_id FROM users WHERE paid IS NOT NULL")
    data = cursor.fetchall()
    return len(data)


# JSON-объект для связи с Юкассой

PROVIDER_DATA = json.dumps({
    "receipt": {
        "items": [
            {
                "description": "Оплата регистрации Guest Four Seasons",
                "quantity": 1.00,
                "amount": {
                    "value": int(os.getenv('PRICE')),
                    "currency": "RUB"
                },
                "vat_code": 1,
            }
        ]

    },
    "amount": {"value": int(os.getenv('PRICE')), "currency": "RUB"},
})
