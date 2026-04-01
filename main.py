import os
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- ၁။ Configuration & Security ---

# Environment Variables ကနေ အချက်အလက်တွေ ယူမယ်
TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = "Your_Sheet_Name_Here" # သင့် Google Sheet နာမည်ကို ဒီမှာ ပြင်ပါ
ADMIN_URL = "https://t.me/Your_Admin_Username" # သင့် Telegram Username Link ကို ဒီမှာ ပြင်ပါ
JSON_CREDS = os.getenv("GOOGLE_SHEETS_JSON")

# Logging (Error တက်ရင် ကြည့်ဖို့)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Google Sheet ချိတ်ဆက်ခြင်း
try:
    if not JSON_CREDS:
        raise ValueError("GOOGLE_SHEETS_JSON environment variable မတွေ့ပါ!")
    
    creds_dict = json.loads(JSON_CREDS)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    product_sheet = client.open(SHEET_NAME).sheet1
except Exception as e:
    logging.error(f"Google Sheet ချိတ်ဆက်မှု Error: {e}")

# --- ၂။ Bot Functions ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """အစဆုံးအဆင့် - Category များကို ပြသသည်"""
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
    """ခလုတ်နှိပ်မှုများကို အဆင့်ဆင့် ကိုင်တွယ်သည်"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split("|")
    action = data[0]
    all_data = product_sheet.get_all_records()

    # (က) Category ရွေးပြီးနောက် -> Name ပြခြင်း
    if action == "cat":
        selected_cat = data[1]
        names = sorted(list(set([i['Name'] for i in all_data if i['Category'] == selected_cat])))
        
        keyboard = [[InlineKeyboardButton(n, callback_data=f"name|{selected_cat}|{n}")] for n in names]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")])
        
        await query.edit_message_text(
            f"📂 **Category:** {selected_cat}\n\nပစ္စည်းအမည် (Name) ကို ရွေးချယ်ပါ-",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # (ခ) Name ရွေးပြီးနောက် -> Plan ပြခြင်း
    elif action == "name":
        selected_cat = data[1]
        selected_name = data[2]
        plans = [i['Plan'] for i in all_data if i['Category'] == selected_cat and i['Name'] == selected_name]
        
        keyboard = [[InlineKeyboardButton(p, callback_data=f"plan|{selected_cat}|{selected_name}|{p}")] for p in plans]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"cat|{selected_cat}")])
        
        await query.edit_message_text(
            f"🛍 **Product:** {selected_name}\n\nလိုချင်သော Plan ကို ရွေးချယ်ပါ-",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # (ဂ) Plan ရွေးပြီးနောက် -> အသေးစိတ် Details နှင့် Buy Button ပြခြင်း
    elif action == "plan":
        selected_cat, selected_name, selected_plan = data[1], data[2], data[3]
        p = next((i for i in all_data if i['Category'] == selected_cat and i['Name'] == selected_name and i['Plan'] == selected_plan), None)
        
        if p:
            msg = (
                f"✅ **ပစ္စည်းအသေးစိတ် အချက်အလက်**\n\n"
                f"📁 **Category:** {p['Category']}\n"
                f"🏷 **Name:** {p['Name']}\n"
                f"💎 **Plan:** {p['Plan']}\n"
                f"💰 **Price:** {p['Price']} MMK\n\n"
                f"📝 **Details:**\n{p['Des']}"
            )
            keyboard = [
                [InlineKeyboardButton("🛒 Buy Now", url=ADMIN_URL)],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"name|{selected_cat}|{selected_name}")]
            ]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif action == "back_to_start":
        await start(update, context)

# --- ၃။ Main Entry ---
def main():
    if not TOKEN:
        print("Error: BOT_TOKEN environment variable မတွေ့ပါ!")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))

    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
