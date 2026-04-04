import os
import json
import gspread
import datetime
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from flask import Flask
from threading import Thread

# --- Flask Server for Render Keep-Alive ---
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

def get_product_data():
    return product_sheet.get_all_records()

# --- Admin Reply Logic ---
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ADMIN_ID = 8736423254  # သင့်ရဲ့ Admin ID
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ သင်သည် Admin မဟုတ်သဖြင့် ဤ Command ကို သုံးခွင့်မရှိပါ။")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ အသုံးပြုပုံ - `/reply [User_ID] [စာသား]`")
        return

    target_user_id = context.args[0]
    reply_text = " ".join(context.args[1:])
    
    final_msg = f"💌 **Admin ထံမှ အကြောင်းပြန်စာ ရရှိပါသည်**\n\n{reply_text}\n\n✨ **အဆင်ပြေပါစေရှင်။**"

    try:
        await context.bot.send_message(chat_id=target_user_id, text=final_msg, parse_mode='Markdown')
        await update.message.reply_text(f"✅ User ID: {target_user_id} ထံသို့ စာပို့ပြီးပါပြီ။")
    except Exception as e:
        await update.message.reply_text(f"❌ စာပို့၍မရပါ။ Error: {e}")

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_product_data()
    categories = sorted(list(set(str(item['Category']) for item in data if item.get('Category'))))
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📦 **Code Master Shop**\nအမျိုးအစားတစ်ခု ရွေးချယ်ပေးပါ -", reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_list = get_product_data()
    parts = query.data.split("_")
    action = parts[0] 

    if action == "cat":
        val = parts[1]
        names = sorted(list(set(item['Name'] for item in data_list if str(item['Category']) == val)))
        keyboard = [[InlineKeyboardButton(n, callback_data=f"name_{val}_{n}")] for n in names]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_start")])
        await query.edit_message_text(text=f"📌 **{val}** အောက်ရှိ Product များ -", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif action == "name":
        cat_v, name_v = parts[1], parts[2]
        plans = [item for item in data_list if str(item['Category']) == cat_v and str(item['Name']) == name_v]
        keyboard = [[InlineKeyboardButton(p['Plan'], callback_data=f"plan_{cat_v}_{name_v}_{p['Plan']}")] for p in plans]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"cat_{cat_v}")])
        await query.edit_message_text(text=f"💳 **{name_v}** အတွက် Plan ကို ရွေးပါ -", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif action == "plan":
        cat_v, name_v, plan_v = parts[1], parts[2], parts[3]
        final_item = next((i for i in data_list if str(i['Category']) == cat_v and str(i['Name']) == name_v and str(i['Plan']) == plan_v), None)
        if final_item:
            context.user_data['last_order'] = final_item
            res = (f"✅ **{final_item['Name']}**\n"
                   f"📝 {final_item.get('Des', '-')}\n\n"
                   f"🔹 Plan: {final_item['Plan']}\n"
                   f"💰 Price: {final_item['Price']} MMK\n\n"
                   "⚠️ **အော်ဒါတင်ရန်**\n"
                   "လူကြီးမင်း၏ ဖုန်းနံပါတ် နှင့် ဆက်သွယ်ရမည့် လိပ်စာ (သို့မဟုတ်) Game ID ကို ရိုက်ပို့ပေးပါရှင်။")
            keyboard = [[InlineKeyboardButton("⬅️ Back to Plans", callback_data=f"name_{cat_v}_{name_v}")]]
            await query.edit_message_text(text=res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif action == "back":
        await start(update, context)

async def handle_order_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    order_info = context.user_data.get('last_order')
    
    if order_info:
        try:
            price = int(order_info.get('Price', 0))
            cost = int(order_info.get('Cost', 0))
            profit = price - cost
        except:
            price, cost, profit = 0, 0, 0

        order_no = len(order_sheet.get_all_values())
        now = datetime.datetime.now().strftime("%d/%m/%Y %I:%M %p")

        new_row = [order_no, now, user_id, user_name, user_text, "-", 
                   order_info.get('Name'), order_info.get('Plan'), price, cost, profit, "Pending"]

        order_sheet.append_row(new_row)

        await update.message.reply_text(
            f"✅ **လူကြီးမင်း၏ အော်ဒါ (ID: {order_no}) ကို လက်ခံရရှိပါပြီ!**\n\n"
            f"Admin မှ အချက်အလက်များကို စစ်ဆေးပြီး အမြန်ဆုံး ဆက်သွယ်ဆောင်ရွက်ပေးပါမည်။ ကျေးဇူးတင်ပါတယ်ရှင်။",
            parse_mode='Markdown'
        )
        
        # --- Admin Notification ---
        ADMIN_ID = "8736423254" 
        admin_msg = (
            f"🔔 **အော်ဒါအသစ် ရရှိပါသည်!**\n"
            f"----------------------------\n"
            f"🆔 Order No: {order_no}\n"
            f"👤 Customer: {user_name}\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📱 Phone/Info: {user_text}\n"
            f"📦 Product: {order_info.get('Name')} ({order_info.get('Plan')})\n"
            f"💰 Price: {price} MMK\n"
            f"📈 Profit: {profit} MMK\n"
            f"----------------------------\n"
            f"💬 စာပြန်ရန်: `/reply {user_id} စာသားရေးပါ`"
        )

        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode='Markdown')
        except Exception as e:
            print(f"Admin Notification Error: {e}")

        context.user_data['last_order'] = None
    else:
        pass

# --- Main Entry ---
def main():
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN: return

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reply", admin_reply)) # Admin Reply Handler
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_order_message))
    
    Thread(target=run_web_server).start()
    application.run_polling()

if __name__ == '__main__':
    main()
