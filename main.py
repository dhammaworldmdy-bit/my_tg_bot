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
    # Render Dashboard က PORT variable (10000) ကို ယူသုံးဖို့ဖြစ်သည်
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
        # Local test (Environment မရှိလျှင် JSON file ကို သုံးမည်)
        creds = ServiceAccountCredentials.from_json_keyfile_name("mmtechlesson-4c42196bfedf.json", scope)
    
    client = gspread.authorize(creds)
    spreadsheet = client.open("mmtechlesson")
    return spreadsheet.worksheet("Products"), spreadsheet.worksheet("Orders")

product_sheet, order_sheet = get_sheets()

def get_product_data():
    return product_sheet.get_all_records()

# --- Telegram Bot Handlers ---

# 1. /start - အမျိုးအစားများ ပြသရန်
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_product_data()
    categories = sorted(list(set(str(item['Category']) for item in data if item.get('Category'))))
    
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("📦 **Code Master Shop**\nအမျိုးအစားတစ်ခု ရွေးချယ်ပေးပါ -", reply_markup=reply_markup, parse_mode='Markdown')

# 2. ခလုတ်များ နှိပ်သည့်အခါ လုပ်ဆောင်ချက် (Button Logic)
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
                   "လူကြီးမင်း၏ ဖုန်းနံပါတ် နှင့် အချက်အလက်များကို ရိုက်ပို့ပေးပါရှင်။")
            
            keyboard = [[InlineKeyboardButton("⬅️ Back to Plans", callback_data=f"name_{cat_v}_{name_v}")]]
            await query.edit_message_text(text=res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif action == "back":
        await start(update, context)

# 3. Admin စာပြန်ခြင်း နှင့် User အော်ဒါလက်ခံခြင်း ပေါင်းစပ်ထားသော Function
async def handle_combined_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ADMIN_ID = 8736423254  # သင်၏ Admin ID
    user_id = update.effective_user.id
    user_text = update.message.text
    user_name = update.effective_user.full_name

    # --- အပိုင်း (က) Admin မှ Reply ပြန်ခြင်းဖြစ်ပါက ---
    if user_id == ADMIN_ID and update.message.reply_to_message:
        reply_msg = update.message.reply_to_message.text
        try:
            if "User ID:" in reply_msg:
                # User ID ကို ရှာထုတ်ခြင်း
                target_user_id = reply_msg.split("User ID:")[1].split("\n")[0].strip()
                final_msg = f"💌 **Admin ထံမှ အကြောင်းပြန်စာ ရရှိပါသည်**\n\n{user_text}\n\n✨ **အဆင်ပြေပါစေရှင်။**"
                
                await context.bot.send_message(chat_id=target_user_id, text=final_msg, parse_mode='Markdown')
                await update.message.reply_text(f"✅ User `{target_user_id}` ထံသို့ စာပို့ပြီးပါပြီ။")
                return # စာပို့ပြီးလျှင် ရပ်မည်
        except Exception as e:
            print(f"Reply Error: {e}")

    # --- အပိုင်း (ခ) User မှ အော်ဒါတင်ခြင်းဖြစ်ပါက ---
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

        # Column ၁၂ ခု စာရင်း
        new_row = [
            order_no, now, user_id, user_name, user_text, "-", 
            order_info.get('Name'), order_info.get('Plan'), price, cost, profit, "Pending"
        ]

        order_sheet.append_row(new_row)

        # User ထံ Reply ပြန်ခြင်း
        await update.message.reply_text(
            f"✅ **လူကြီးမင်း၏ အော်ဒါ (ID: {order_no}) ကို လက်ခံရရှိပါပြီ!**\n\n"
            f"Admin မှ အချက်အလက်များကို စစ်ဆေးပြီး အမြန်ဆုံး ဆက်သွယ်ဆောင်ရွက်ပေးပါမည်။",
            parse_mode='Markdown'
        )

        # Admin ထံ Notification ပို့ခြင်း
        admin_msg = (
            f"🔔 **အော်ဒါအသစ် ရရှိပါသည်!**\n"
            f"----------------------------\n"
            f"🆔 Order No: {order_no}\n"
            f"👤 Customer: {user_name}\n"
            f"🆔 User ID: {user_id}\n"
            f"📱 Phone/Info: {user_text}\n"
            f"📦 Product: {order_info.get('Name')} ({order_info.get('Plan')})\n"
            f"💰 Price: {price} MMK\n"
            f"📈 Profit: {profit} MMK\n"
            f"----------------------------\n"
            f"💬 စာပြန်ရန် ဤစာကို Reply ပြန်ပြီး စာရိုက်လိုက်ပါ။"
        )

        try:
            await context.bot.send_message(chat_id=str(ADMIN_ID), text=admin_msg, parse_mode='Markdown')
        except Exception as e:
            print(f"Admin Notification Error: {e}")

        # Context ရှင်းထုတ်ခြင်း
        context.user_data['last_order'] = None

# --- Main Entry ---
def main():
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN:
        print("Error: No Token found!")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers အစီအစဉ်
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # MessageHandler က Admin ရော User ရော အလုပ်လုပ်ပေးမည်
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_combined_messages))
    
    # Flask Server ကို Thread ဖြင့် Run ရန်
    Thread(target=run_web_server).start()
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
