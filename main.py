import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
from threading import Thread

# --- Flask Server (Render Keep-Alive အတွက်) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Alive!"

def run_web_server():
    # Render ရဲ့ Dynamic Port ကို သုံးဖို့ os.environ.get သုံးရပါမယ်
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- Google Sheets Setup ---
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Render ရဲ့ Environment Variable (GOOGLE_SHEETS_JSON) ကနေ ဒေတာဖတ်ခြင်း
    google_json_str = os.environ.get("GOOGLE_SHEETS_JSON")
    
    if google_json_str:
        # JSON စာသားကို Dictionary အဖြစ်ပြောင်းလဲခြင်း
        creds_dict = json.loads(google_json_str)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    else:
        # Local မှာ စမ်းသပ်နေစဉ်အတွက် (File ရှိလျှင်)
        try:
            return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name("mmtechlesson-4c42196bfedf.json", scope))
        except FileNotFoundError:
            print("Error: GOOGLE_SHEETS_JSON variable or local file not found!")
            return None

# Google Sheet ချိတ်ဆက်ခြင်း
client = get_gspread_client()
if client:
    sheet = client.open("mmtechlesson")
    product_sheet = sheet.worksheet("Products")
else:
    print("Warning: Could not connect to Google Sheets.")

# --- Telegram Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("မင်္ဂလာပါ! Code Master Bot အဆင်သင့်ဖြစ်ပါပြီ။ /products လို့ ရိုက်ကြည့်ပါ။")

async def get_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not client:
        await update.message.reply_text("Database ချိတ်ဆက်မှု အဆင်မပြေဖြစ်နေပါသည်။")
        return

    all_products = product_sheet.get_all_records()
    response = "📦 **Products List:**\n\n"
    
    for item in all_products:
        # Column Name တွေကို Spreadsheet ထဲကအတိုင်း (Name, Price) သေချာစစ်ပါ
        name = item.get('Name', 'Unknown')
        price = item.get('Price', '0')
        response += f"🔹 {name} - {price} MMK\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

# --- Main Logic ---
def main():
    # Telegram Token ကို Render ရဲ့ Env Variable ကနေ ယူပါမယ်
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    
    if not TOKEN:
        print("Error: TELEGRAM_TOKEN not found in Environment Variables!")
        return

    # Application တည်ဆောက်ခြင်း
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Command များထည့်သွင်းခြင်း
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", get_products))
    
    # Flask Server ကို Background မှာ Run ခြင်း
    Thread(target=run_web_server).start()
    
    print("Bot is starting...")
    # Bot ကို စတင် Run ခြင်း
    application.run_polling()

if __name__ == '__main__':
    main()
