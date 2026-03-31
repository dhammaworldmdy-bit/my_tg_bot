import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
from threading import Thread

# --- Flask Server (Render မှာ Bot မအိပ်အောင် နှိုးပေးဖို့) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Alive!"

def run_web_server():
    # Render ကပေးတဲ့ Port မှာ run ဖို့ (Default ကတော့ 8080)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- Google Sheets Setup ---
# မင်းရဲ့ JSON file နာမည်ကို ဒီမှာ ပြောင်းပေးပါ (ဥပမာ- credentials.json)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("mmtechlesson-4c42196bfedf.json", scope)
client = gspread.authorize(creds)
sheet = client.open("mmtechlesson") # Sheet နာမည်
product_sheet = sheet.worksheet("Products")

# --- Telegram Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! Code Master Bot အဆင်သင့်ဖြစ်ပါပြီ။ /products လို့ ရိုက်ကြည့်ပါ။")

async def get_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_products = product_sheet.get_all_records()
    response = "📦 **Products List:**\n"
    for item in all_products:
        response += f"🔹 {item['Name']} - {item['Price']} MMK\n"
    await update.message.reply_text(response, parse_mode='Markdown')

# --- Bot ကို Run မည့် Function ---
def main():
    # Telegram Token ကို Render ရဲ့ Env Variable ကနေ ယူမှာဖြစ်ပါတယ်
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", get_products))
    
    # Flask ကို Thread တစ်ခုအနေနဲ့ background မှာ run မယ်
    Thread(target=run_web_server).start()
    
    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()