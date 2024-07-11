import os
from io import BytesIO
import requests
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bs4 import BeautifulSoup

# إعدادات البوت والمفاتيح API
TOKEN = os.environ['TOKEN']
URL = os.environ['URL']
TRY2LINK_API_KEY = os.environ['TRY2LINK_API_KEY']
bot = telebot.TeleBot(TOKEN)

url_list = {}

# وظيفة لتقصير الروابط باستخدام Try2Link
def shorten_link(original_link):
    api_url = f"https://try2link.com/api?api={TRY2LINK_API_KEY}&url={original_link}"
    response = requests.get(api_url).json()
    if response["status"] == "success":
        return response["shortenedUrl"]
    else:
        return original_link  # في حال فشل الحصول على الرابط المختصر، ارجع للرابط الأصلي

# وظيفة البحث عن الأفلام
def search_movies(query):
    movies_list = []
    movies_details = {}
    website = BeautifulSoup(requests.get(f"https://mkvcinemas.cymru/?s={query.replace(' ', '+')}").text, "html.parser")
    movies = website.find_all("a", {'class': 'ml-mask jt'})[:10]  # قصر النتائج على أول 10 أفلام
    for movie in movies:
        if movie:
            movies_details["id"] = f"link{movies.index(movie)}"
            movies_details["title"] = movie.find("span", {'class': 'mli-info'}).text
            url_list[movies_details["id"]] = movie['href']
        movies_list.append(movies_details)
        movies_details = {}
    return movies_list

# وظيفة جلب تفاصيل الفيلم
def get_movie(query):
    movie_details = {}
    movie_page_link = BeautifulSoup(requests.get(f"{url_list[query]}").text, "html.parser")
    if movie_page_link:
        title = movie_page_link.find("div", {'class': 'mvic-desc'}).h3.text
        movie_details["title"] = title
        img = movie_page_link.find("div", {'class': 'mvic-thumb'})['data-bg']
        movie_details["img"] = img
        links = movie_page_link.find_all("a", {'rel': 'noopener', 'data-wpel-link': 'internal'})[:10]  # قصر الروابط على أول 10 روابط
        final_links = {}
        for i in links:
            shortened_link = shorten_link(i['href'])
            final_links[f"{i.text}"] = shortened_link
        movie_details["links"] = final_links
    return movie_details

# إعداد فلاسكات
app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello World!'

# استقبال التحديثات من تليجرام عبر الويب هوك
@app.route('/{}'.format(TOKEN), methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return 'ok'

# إعداد الويب هوك
@app.route('/setwebhook', methods=['GET', 'POST'])
def set_webhook():
    s = bot.set_webhook(f'{URL}/{TOKEN}')
    if s:
        return "webhook setup ok"
    else:
        return "webhook setup failed"

# التعامل مع أمر /start
@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(
        message.chat.id, 
        f"Hello {message.from_user.first_name}, Welcome to aj Movies.\n"
        f"🔥 Download Your Favourite Movies For 💯 Free And 🍿 Enjoy it.\n"
        f"👇 Enter Movie Name 👇"
    )

# التعامل مع الرسائل النصية (البحث عن الأفلام)
@bot.message_handler(func=lambda message: True)
def find_movie(message):
    search_results = bot.send_message(message.chat.id, "Processing...")
    query = message.text
    movies_list = search_movies(query)
    if movies_list:
        keyboards = InlineKeyboardMarkup()
        for movie in movies_list:
            keyboard = InlineKeyboardButton(movie["title"], callback_data=movie["id"])
            keyboards.add(keyboard)
        bot.edit_message_text('Search Results...', chat_id=message.chat.id, message_id=search_results.message_id, reply_markup=keyboards)
    else:
        bot.edit_message_text('Sorry 🙏, No Result Found!\nCheck If You Have Misspelled The Movie Name.', chat_id=message.chat.id, message_id=search_results.message_id)

# التعامل مع اختيار الفيلم من النتائج
@bot.callback_query_handler(func=lambda call: True)
def movie_result(call):
    s = get_movie(call.data)
    response = requests.get(s["img"])
    img = BytesIO(response.content)
    bot.send_photo(call.message.chat.id, photo=img, caption=f"🎥 {s['title']}")
    link = ""
    links = s["links"]
    for i in links:
        link += "🎬" + i + "\n" + links[i] + "\n\n"
    caption = f"⚡ Fast Download Links :-\n\n{link}"
    if len(caption) > 4095:
        for x in range(0, len(caption), 4095):
            bot.send_message(call.message.chat.id, text=caption[x:x+4095])
    else:
        bot.send_message(call.message.chat.id, text=caption)

# وظيفة إرسال اقتراحات الأفلام
@bot.message_handler(commands=['suggest'])
def suggest_movies(message):
    suggestions = ["Inception", "Interstellar", "The Dark Knight", "Titanic", "Avatar"]
    bot.send_message(message.chat.id, f"Suggested Movies:\n" + "\n".join(suggestions))

# بدء تشغيل التطبيق
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=5000)
