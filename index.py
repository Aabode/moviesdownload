import os
from io import BytesIO
import requests
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bs4 import BeautifulSoup

# تحميل الإعدادات من متغيرات البيئة
TOKEN = os.getenv('TOKEN')
URL = os.getenv('URL')

# إعداد البوت والتفاصيل الأخرى
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
url_list = {}

# وظيفة البحث عن الأفلام
def search_movies(query):
    movies_list = []
    website = BeautifulSoup(requests.get(f"https://mkvcinemas.cymru/?s={query.replace(' ', '+')}").text, "html.parser")
    movies = website.find_all("a", {'class': 'ml-mask jt'})
    for index, movie in enumerate(movies[:10], start=1):
        title = movie.find("span", {'class': 'mli-info'}).text.strip()
        url = movie['href']
        url_list[index] = url
        movies_list.append(f"{index}. {title}")
    return movies_list

# وظيفة جلب تفاصيل الفيلم
def get_movie(index):
    url = url_list.get(index)
    if not url:
        return None
    movie_details = {}
    movie_page = BeautifulSoup(requests.get(url).text, "html.parser")
    title = movie_page.find("div", {'class': 'mvic-desc'}).h3.text.strip()
    img = movie_page.find("div", {'class': 'mvic-thumb'})['data-bg']
    movie_details["title"] = title
    movie_details["img"] = img
    links = movie_page.find_all("a", {'rel': 'noopener', 'data-wpel-link': 'internal'})
    movie_details["links"] = {link.text.strip(): link['href'] for link in links[:10]}
    return movie_details

# روابط الويب هوك والتعامل مع تحديثات تليجرام
@app.route('/{}'.format(TOKEN), methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'ok', 200

# إزالة الويب هوك
@app.route('/remove_webhook', methods=['GET'])
def remove_webhook():
    bot.remove_webhook()
    return 'Webhook removed', 200

# تعيين الويب هوك
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    s = bot.set_webhook(f'{URL}/{TOKEN}')
    if s:
        return "Webhook setup ok"
    else:
        return "Webhook setup failed"

# التعامل مع أمر /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, "Welcome! Enter the movie name to search.")

# التعامل مع الرسائل النصية (البحث عن الأفلام)
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    query = message.text.strip()
    if query:
        movies_list = search_movies(query)
        if movies_list:
            bot.send_message(message.chat.id, "Search Results:\n" + "\n".join(movies_list))
        else:
            bot.send_message(message.chat.id, "No movies found for your query.")
    else:
        bot.send_message(message.chat.id, "Please enter a movie name to search.")

# التعامل مع اختيار الفيلم من النتائج
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    index = int(call.data)
    movie_details = get_movie(index)
    if movie_details:
        bot.send_photo(call.message.chat.id, photo=movie_details['img'], caption=movie_details['title'])
        links_text = "\n".join([f"{key}: {value}" for key, value in movie_details['links'].items()])
        bot.send_message(call.message.chat.id, f"Download Links:\n{links_text}")
    else:
        bot.send_message(call.message.chat.id, "Movie details not found.")

# تشغيل التطبيق
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv('PORT', 5000)))
