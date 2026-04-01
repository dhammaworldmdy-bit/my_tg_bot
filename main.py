import os
import json
import logging
import gspread
import threading
from flask import Flask
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- ၁။ Flask Server Setup (Render Port Binding အတွက်) ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    # Render က ပေးတဲ့ PORT ကို ယူမယ်၊ မရှိရင် 10000 သုံးမယ်
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ၂။ Configuration & Security ---
TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = "Your_Sheet_Name_Here" # သင့် Sheet နာမည်
ADMIN_URL = "https://t.me/Your_Admin_Username" # သင့် Admin Link
JSON_CREDS = os.getenv("GOOGLE_SHEETS_JSON")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Google Sheet ချိတ်ဆက်ခြင်း
try:
    if not JSON_CREDS:
        raise ValueError("GOOGLE_SHEETS_JSON variable မတွေ့ပါ!")
    creds_dict = json.loads(JSON_CREDS)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    product_sheet = client.open(SHEET_NAME).sheet1
except Exception as e:
    logging.error(f"Google Sheet Error: {e}")

# --- ၃။ Bot Functions ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_data = product_sheet.get_all_records()
    categories = sorted(list(set([item['Category'] for item in all_data if item['Category']])))
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat|{cat}")] for cat in categories]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "📦 **ကြည့်ရှုလိုသော ကဏ္ဍ (Category) ကို ရွေးချယ်ပါ**"
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action = data[0]
    all_data = product_sheet.get_all_records()

    if action == "cat":
        selected_cat = data[1]
        names = sorted(list(set([i['Name'] for i in all_data if i['Category'] == selected_cat])))
        keyboard = [[InlineKeyboardButton(n, callback_data=f"name|{selected_cat}|{n}")] for n in names]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")])
        await query.edit_message_text(f"📂 **Category:** {selected_cat}\n\nပစ္စည်းအမည်ကို ရွေးပါ-", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "name":
        selected_cat, selected_name = data[1], data[2]
        plans = [i['Plan'] for i in all_data if i['Category'] == selected_cat and i['Name'] == selected_name]
        keyboard = [[InlineKeyboardButton(p, callback_data=f"plan|{selected_cat}|{selected_name}|{p}")] for p in plans]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"cat|{selected_cat}")])
        await query.edit_message_text(f"🛍 **Product:** {selected_name}\n\nPlan ကို ရွေးချယ်ပါ-", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "plan":
        selected_cat, selected_name, selected_plan = data[1], data[2], data[3]
        p = next((i for i in all_data if i['Category'] == selected_cat and i['Name'] == selected_name and i['Plan'] == selected_plan), None)
        if p:
            msg = f"✅ **အသေးစိတ်အချက်အလက်**\n\n📁 **Cat:** {p['Category']}\n🏷 **Name:** {p['Name']}\n💎 **Plan:** {p['Plan']}\n💰 **Price:** {p['Price']} MMK\n\n📝 **Details:**\n{p['Des']}"
            keyboard = [[InlineKeyboardButton("🛒 Buy Now", url=ADMIN_URL)], [InlineKeyboardButton("⬅️ Back", callback_data=f"name|{selected_cat}|{selected_name}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "back_to_start":
        await start(update, context)

# --- ၄။ Main Application ---
def main():
    if not TOKEN:
        print("Error: BOT_TOKEN မတွေ့ပါ!")
        return

    # Flask ကို Thread တစ်ခုအနေနဲ့ Background မှာ run မယ်
    threading.Thread(target=run_flask, daemon=True).start()

    # Telegram Bot ကို ပုံမှန်အတိုင်း run မယ်
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))

    print("Bot is running with Flask Health Check...")
    application.run_polling()

if __name__ == "__main__":
    main()
