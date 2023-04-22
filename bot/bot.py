#!/usr/bin/env python3

from telebot.async_telebot import AsyncTeleBot
import configparser
import asyncio
from pypdf import PdfReader
import glob
import openai
import os

config = configparser.ConfigParser()
config.read("bot/config.ini")
tg_token = config["BOT"]["token"]
bot = AsyncTeleBot(tg_token)

openai.api_key = config["CHATGPT"]["token"]

CV_path = 'bot/CVs/'

async def something_wrong(id, append=""):
    try:
        await bot.send_message(id, 'Что то пошло не так, мы уже работает над этим')
        await bot.send_message(id, append)
        print('Админ, что то сломалось, посмотри!')
    except Exception as e:
        print(f'caught {type(e)}: {e}')
        print('Админ, что то сломалось, посмотри!')


@bot.message_handler(commands=['start'])
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
                     leave only relevant information(for example, delete projects that aren't needed for position),\
                     add some relevant information too, \
                     improve grammar, delete unread symbols,\
                     make it fit one page, \
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

def compile_latex(path, latex):
    try:
        with open(path + '.tex', 'w+') as f:
            f.write(latex)
        os.system(f"pdflatex --interaction=batchmode {path + '.tex'} -output_directory={CV_path} 2>&1 > /dev/null") #TODO why output-dir doesn't work + do not create temp files
    except:
        raise

@bot.message_handler(content_types=['text'])
async def create_resume(message):
    try:
        await bot.send_message(message.chat.id, 'Начинаю создавать идеальное резюме...')
        text = await upgrade_resume(message)
        path = CV_path + str(message.from_user.id) + '_upd'
        compile_latex(path, text)
        os.system(f"mv {str(message.from_user.id) + '_upd' + '.pdf'} {CV_path}")
        with open(path + '.pdf', 'rb') as f:
            await bot.send_message(message.chat.id, 'Готово! Вот твое резюме:')
            await bot.send_document(message.chat.id, f)
    except Exception as e:
        print(f'caught {type(e)}: {e}')
        await something_wrong(message.chat.id, append="Попробуйте перезадать запрос, иногда chatgpt может тупить")


asyncio.run(bot.polling(none_stop=True))

"""
global TODO's:
- make logging
"""