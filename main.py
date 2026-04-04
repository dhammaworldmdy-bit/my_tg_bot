import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from flask import Flask
from threading import Thread

# --- Flask Server ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive!"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_json_str = os.environ.get("GOOGLE_SHEETS_JSON")

def get_sheet():
    if google_json_str:
        creds_dict = json.loads(google_json_str)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("mmtechlesson-4c42196bfedf.json", scope)
    client = gspread.authorize(creds)
    return client.open("mmtechlesson").worksheet("Products")

# --- Helper Function to get data ---
def get_all_data():
    sheet = get_sheet()
    return sheet.get_all_records()

# --- Telegram Handlers ---

# 1. /start နှိပ်ရင် Category ခလုတ်တွေပြမယ်
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_all_data()
    # Unique ဖြစ်တဲ့ Categories တွေကို ယူမယ်
    categories = sorted(list(set(str(item['Category']) for item in data if item.get('Category'))))
    
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("အမျိုးအစား ရွေးချယ်ပါ -", reply_markup=reply_markup)

# 2. ခလုတ်နှိပ်လိုက်ရင် အဆင့်ဆင့်လုပ်ဆောင်မည့် Function
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_list = get_all_data()
    
    parts = query.data.split("_")
    action = parts[0] # cat, name, သို့မဟုတ် plan
    value = parts[1]

    # Category ရွေးပြီးရင် Name ပြမယ်
    if action == "cat":
        names = sorted(list(set(item['Name'] for item in data_list if str(item['Category']) == value)))
        keyboard = [[InlineKeyboardButton(n, callback_data=f"name_{value}_{n}")] for n in names]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_start")])
        await query.edit_message_text(text=f"📌 {value} အောက်ရှိ Product များ -", reply_markup=InlineKeyboardMarkup(keyboard))

    # Name ရွေးပြီးရင် Plan ပြမယ်
    elif action == "name":
        cat_val = parts[1]
        name_val = parts[2]
        plans = [item for item in data_list if str(item['Category']) == cat_val and str(item['Name']) == name_val]
        
        keyboard = [[InlineKeyboardButton(p['Plan'], callback_data=f"plan_{p['Category']}_{p['Name']}_{p['Plan']}")] for p in plans]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"cat_{cat_val}")])
        await query.edit_message_text(text=f"💳 {name_val} အတွက် Plan ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard))

    # Plan ရွေးပြီးရင် အသေးစိတ်စာသားပြမယ်
    elif action == "plan":
        cat_v, name_v, plan_v = parts[1], parts[2], parts[3]
        # အချက်အလက်အကုန်တိုက်စစ်ပြီး ရှာမယ်
        final_item = next((i for i in data_list if str(i['Category']) == cat_v and str(i['Name']) == name_v and str(i['Plan']) == plan_v), None)
        
        if final_item:
            res = (f"✅ **{final_item['Name']}**\n"
                   f"📝 {final_item.get('Des', 'No Description')}\n\n"
                   f"🔹 Plan: {final_item['Plan']}\n"
                   f"💰 Price: {final_item['Price']} MMK")
            
            keyboard = [[InlineKeyboardButton("⬅️ Back to Plans", callback_data=f"name_{cat_v}_{name_v}")]]
            await query.edit_message_text(text=res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # Back to Start
    elif action == "back":
        categories = sorted(list(set(str(item['Category']) for item in data_list)))
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
        await query.edit_message_text("အမျိုးအစား ပြန်လည်ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler)) # ခလုတ်တွေအတွက် handler
    
    Thread(target=run_web_server).start()
    application.run_polling()

if __name__ == '__main__':
    main()
