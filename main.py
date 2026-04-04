import os
import json
import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from flask import Flask
from threading import Thread

# --- Flask Server ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive!"

def run_web_server():
    port = int(os.environ.get('PORT', 10000)) 
    app.run(host='0.0.0.0', port=port)

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_sheets():
    google_json_str = os.environ.get("GOOGLE_SHEETS_JSON")
    if google_json_str:
        creds_dict = json.loads(google_json_str)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("mmtechlesson-4c42196bfedf.json", scope)
    
    client = gspread.authorize(creds)
    spreadsheet = client.open("mmtechlesson")
    return spreadsheet.worksheet("Products"), spreadsheet.worksheet("Orders")

product_sheet, order_sheet = get_sheets()

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = product_sheet.get_all_records()
    categories = sorted(list(set(str(item['Category']) for item in data if item.get('Category'))))
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
    await update.message.reply_text("📦 **Code Master Shop**\nအမျိုးအစား ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_list = product_sheet.get_all_records()
    parts = query.data.split("_")
    action = parts[0] 

    if action == "cat":
        val = parts[1]
        names = sorted(list(set(item['Name'] for item in data_list if str(item['Category']) == val)))
        keyboard = [[InlineKeyboardButton(n, callback_data=f"name_{val}_{n}")] for n in names]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_start")])
        await query.edit_message_text(text=f"📌 **{val}** Products:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif action == "name":
        cat_v, name_v = parts[1], parts[2]
        plans = [item for item in data_list if str(item['Category']) == cat_v and str(item['Name']) == name_v]
        keyboard = [[InlineKeyboardButton(p['Plan'], callback_data=f"plan_{cat_v}_{name_v}_{p['Plan']}")] for p in plans]
        await query.edit_message_text(text=f"💳 **{name_v}** Plan:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif action == "plan":
        cat_v, name_v, plan_v = parts[1], parts[2], parts[3]
        final_item = next((i for i in data_list if str(i['Category']) == cat_v and str(i['Name']) == name_v and str(i['Plan']) == plan_v), None)
        if final_item:
            context.user_data['last_order'] = final_item
            await query.edit_message_text(text=f"✅ **{final_item['Name']}**\n💰 {final_item['Price']} MMK\n\n⚠️ ဖုန်းနံပါတ် သို့မဟုတ် Game ID ရိုက်ပို့ပေးပါရှင်။", parse_mode='Markdown')

async def handle_combined_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ADMIN_ID = 8736423254  
    user_id = update.effective_user.id
    user_text = update.message.text

    # --- (A) Admin Reply Logic ---
    if user_id == ADMIN_ID and update.message.reply_to_message:
        reply_msg = update.message.reply_to_message.text
        if "User ID:" in reply_msg:
            try:
                target_user_id = reply_msg.split("User ID:")[1].split("\n")[0].strip()
                final_msg = f"💌 **Admin ထံမှ အကြောင်းပြန်စာ**\n\n{user_text}\n\n✨ **အဆင်ပြေပါစေရှင်။**"
                await context.bot.send_message(chat_id=target_user_id, text=final_msg, parse_mode='Markdown')
                await update.message.reply_text(f"✅ စာပို့ပြီးပါပြီ။")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
                return

    # --- (B) User Order Logic ---
    order_info = context.user_data.get('last_order')
    if order_info:
        now = datetime.datetime.now().strftime("%d/%m/%Y %I:%M %p")
        order_no = len(order_sheet.get_all_values())
        price, cost = int(order_info.get('Price', 0)), int(order_info.get('Cost', 0))
        
        # Sheet သိမ်းမယ်
        new_row = [order_no, now, user_id, update.effective_user.full_name, user_text, "-", 
                   order_info.get('Name'), order_info.get('Plan'), price, cost, price-cost, "Pending"]
        order_sheet.append_row(new_row)

        await update.message.reply_text("✅ အော်ဒါတင်ခြင်း အောင်မြင်ပါသည်။")

        # Admin Notification with ForceReply
        admin_noti = (
            f"🔔 **အော်ဒါအသစ် (ID: {order_no})**\n"
            f"👤 Customer: {update.effective_user.full_name}\n"
            f"🆔 User ID: {user_id}\n"
            f"📱 Info: {user_text}\n"
            f"📦 Product: {order_info.get('Name')} ({order_info.get('Plan')})\n"
            f"----------------------------\n"
            f"💬 စာပြန်ရန် အောက်က အကွက်လေးမှာ တန်းရိုက်လိုက်ပါ။"
        )
        # Admin ဆီကို စာပြန်ဖို့ အကွက်လေး တစ်ခါတည်း ဖွင့်ပေးလိုက်ခြင်း
        await context.bot.send_message(
            chat_id=ADMIN_ID, 
            text=admin_noti, 
            reply_markup=ForceReply(selective=True),
            parse_mode='Markdown'
        )
        context.user_data['last_order'] = None

# --- Main ---
def main():
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_combined_messages))
    Thread(target=run_web_server).start()
    application.run_polling()

if __name__ == '__main__':
    main()
