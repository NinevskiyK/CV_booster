#!/usr/bin/env python3

from telebot.async_telebot import AsyncTeleBot
import configparser
import asyncio
from pypdf import PdfReader
import glob
import openai
import os
import json
import aioconsole

config = configparser.ConfigParser()
config.read("bot/config.ini")
tg_token = config["BOT"]["token"]
bot = AsyncTeleBot(tg_token)

openai.api_key = config["CHATGPT"]["token"]

CV_path = 'bot/CVs/'
def check_whitelist(func):
    def is_known(id):
        with open('bot/whitelist.json') as f:
            known = json.load(f)
        return str(id) in known

    async def inner(message):
        if not is_known(message.from_user.id):
            await bot.send_message(message.chat.id, "Я тебя не знаю - попроси админов добавить тебя в whitelist!")
            print(f"User {message.from_user.first_name} {message.from_user.last_name} (@{message.from_user.username}, id {message.from_user.id}) tried to the bot, I've denied. Type id to add to the whitelist")
        else:
            await func(message)
    return inner

async def something_wrong(id, append=""):
    try:
        await bot.send_message(id, 'Что то пошло не так, мы уже работает над этим')
        await bot.send_message(id, append)
        print('Админ, что то сломалось, посмотри!')
    except Exception as e:
        print(f'caught {type(e)}: {e}')
        print('Админ, что то сломалось, посмотри!')


@bot.message_handler(commands=['start'])
@check_whitelist
async def hello(message):
    try:
        await bot.send_message(message.chat.id, 'Привет! Я помогу тебе сделать уникальное резюме под вакансию! Для начала - пришли мне твое текущее резюме в pdf')
    except Exception as e:
        print(f'caught {type(e)}: {e}')
        something_wrong(message.chat.id)


def parse_file(path2read):
    try:
        reader = PdfReader(path2read)
        text = []
        for page in reader.pages:
            text.append(page.extract_text())
        return "\n".join(text)
    except Exception as e:
        raise
    

async def download_file(name2save, doc_id):
    try:
        file_info = await bot.get_file(doc_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        with open(name2save, 'wb+') as f:
            f.write(downloaded_file)
    except Exception as e:
        raise


async def proccess_file(user_id, doc_id):
    try:
        was = False
        path = CV_path + str(user_id)
        if len(glob.glob(path + '*')) > 0:
            was = True
        await download_file(path + '.pfd', doc_id)
        text = parse_file(path + '.pfd')
        with open(path + '.txt', 'w+') as f:
            f.write(text)
        return was
    except Exception as e:
        raise
    

@bot.message_handler(content_types=['document'])
@check_whitelist
async def doc_saver(message):
    try:
        await bot.send_message(message.chat.id, 'Начинаю процесс обработки резюме!')
        resp = await proccess_file(message.from_user.id, message.document.file_id)
        if resp == 0:
            await bot.send_message(message.chat.id, 'Сохранил!')
        elif resp == 1:
            await bot.send_message(message.chat.id, 'Обновил резюме!')
        await bot.send_message(message.chat.id, 'Теперь жду от тебя вакансий - укажи, что требуется, и я пришлю тебе крутое резюме!')
    except Exception as e:
        print(f'caught {type(e)}: {e}')
        await something_wrong(message.chat.id)


def get_text(path):
    try:
        with open(path, 'r') as f:
            text = ''.join(f.readlines())
        return text
    except FileNotFoundError:
        raise

async def upgrade_resume(message):
    try:
        resume_text = get_text(CV_path + str(message.from_user.id) + '.txt')
        vacancy_text = message.text
        await bot.send_message(message.chat.id, 'Жду ответа от ChatGPT, это может занять время...') # TODO: find reliable awiat
        message = "Can you rewrite this resume for a job vacancy:\
                     delete irrelevant information, leave only relevant staff(for example, delete projects that aren't relevant to this position)\
                     add some relevant information, \
                     highlight skills asked in vacancy,\
                     improve grammar, delete unread symbols,\
                     make it fit one page. Don't make up anything, use information only from CV, but you can and should aggregate it. \
                I want to compile it with latex, so write only latex code. Don't use any non-standart packages \
                - make sure I can compile it with pdflatex\
                \nHere is Vacancy:\n\n" + vacancy_text + "\n\nAnd here is Resume:\n" + resume_text
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=
                [
                    {
                    "role": "user",
                    "content": message
                    },
                ]
            )
        return completion.choices[0].message.content
    except FileNotFoundError:
        await bot.send_message(message.chat.id, 'Сначала надо загрузить свое резюме!')
    except:
        raise

def compile_latex(name, latex):
    try:
        with open(CV_path + name + '.tex', 'w+') as f:
            f.write(latex)
        os.system(f"cd {CV_path} && pdflatex --interaction=batchmode {name + '.tex'} 2>&1 > /dev/null")
        os.system(f"find {CV_path} -not -name '*.pdf' -not -name  '*.txt' -not -name  '*.tex' -type f -delete")
    except:
        raise

@bot.message_handler(content_types=['text'])
@check_whitelist
async def create_resume(message):
    try:
        await bot.send_message(message.chat.id, 'Начинаю создавать идеальное резюме...')
        text = await upgrade_resume(message)
        name = str(message.from_user.id) + '_upd'
        compile_latex(name, text)
        with open(CV_path + name + '.pdf', 'rb') as f:
            await bot.send_message(message.chat.id, 'Готово! Вот твое резюме:')
            await bot.send_document(message.chat.id, f)
    except Exception as e:
        print(f'caught {type(e)}: {e}')
        await something_wrong(message.chat.id, append="Попробуйте перезадать запрос, иногда chatgpt может тупить")


async def admin_handler():
    while True:
        id = await aioconsole.ainput()
        a = {}
        with open('bot/whitelist.json', 'r') as f:
            a = json.load(f)
        a.append(id)
        with open('bot/whitelist.json', 'w') as f:
            json.dump(a, f)
        print(f"Добавил в разрешенный список {id}!")

async def main():
    await asyncio.gather(
        bot.polling(none_stop=True),
        admin_handler()
    )


asyncio.run(main())

"""
global TODO's:
- make logging
"""