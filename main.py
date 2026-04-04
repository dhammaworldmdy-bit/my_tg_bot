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
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- Google Sheets Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_sheets():
    google_json_str = os.environ.get("GOOGLE_SHEETS_JSON")
    if google_json_str:
        creds_dict = json.loads(google_json_str)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Local test case
        creds = ServiceAccountCredentials.from_json_keyfile_name("mmtechlesson-4c42196bfedf.json", scope)
    
    client = gspread.authorize(creds)
    spreadsheet = client.open("mmtechlesson")
    return spreadsheet.worksheet("Products"), spreadsheet.worksheet("Orders")

product_sheet, order_sheet = get_sheets()

# --- Helper Function: Get Data ---
def get_product_data():
    return product_sheet.get_all_records()

# --- Telegram Bot Handlers ---

# 1. /start - Show Categories
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_product_data()
    categories = sorted(list(set(str(item['Category']) for item in data if item.get('Category'))))
    
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in categories]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("📦 **Code Master Shop**\nအမျိုးအစားတစ်ခု ရွေးချယ်ပေးပါ -", reply_markup=reply_markup, parse_mode='Markdown')

# 2. Button Interaction Logic
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_list = get_product_data()
    
    parts = query.data.split("_")
    action = parts[0] 
    
    # Step: Category -> Show Names
    if action == "cat":
        val = parts[1]
        names = sorted(list(set(item['Name'] for item in data_list if str(item['Category']) == val)))
        keyboard = [[InlineKeyboardButton(n, callback_data=f"name_{val}_{n}")] for n in names]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_start")])
        await query.edit_message_text(text=f"📌 **{val}** အောက်ရှိ Product များ -", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # Step: Name -> Show Plans
    elif action == "name":
        cat_v, name_v = parts[1], parts[2]
        plans = [item for item in data_list if str(item['Category']) == cat_v and str(item['Name']) == name_v]
        
        keyboard = [[InlineKeyboardButton(p['Plan'], callback_data=f"plan_{cat_v}_{name_v}_{p['Plan']}")] for p in plans]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"cat_{cat_v}")])
        await query.edit_message_text(text=f"💳 **{name_v}** အတွက် Plan ကို ရွေးပါ -", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # Step: Plan -> Show Detail & Wait for Message
    elif action == "plan":
        cat_v, name_v, plan_v = parts[1], parts[2], parts[3]
        final_item = next((i for i in data_list if str(i['Category']) == cat_v and str(i['Name']) == name_v and str(i['Plan']) == plan_v), None)
        
        if final_item:
            # Save selected product to user context
            context.user_data['last_order'] = final_item
            
            res = (f"✅ **{final_item['Name']}**\n"
                   f"📝 {final_item.get('Des', '-')}\n\n"
                   f"🔹 Plan: {final_item['Plan']}\n"
                   f"💰 Price: {final_item['Price']} MMK\n\n"
                   "⚠️ **အော်ဒါတင်ရန်**\n"
                   "လူကြီးမင်း၏ ဖုန်းနံပါတ် နှင့် ဆက်သွယ်ရမည့် လိပ်စာ (သို့မဟုတ်) Game ID ကို ရိုက်ပို့ပေးပါရှင်။")
            
            keyboard = [[InlineKeyboardButton("⬅️ Back to Plans", callback_data=f"name_{cat_v}_{name_v}")]]
            await query.edit_message_text(text=res, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    # Back to Main
    elif action == "back":
        await start(update, context)

# 3. Handle Order Message (Saving to Sheet)
async def handle_order_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    order_info = context.user_data.get('last_order')
    
    if order_info:
        # Profit Calculation
        try:
            price = int(order_info.get('Price', 0))
            cost = int(order_info.get('Cost', 0))
            profit = price - cost
        except:
            price, cost, profit = 0, 0, 0

        # No (Order ID) Calculation - Row count
        order_no = len(order_sheet.get_all_values())
        
        # Date & Time
        now = datetime.datetime.now().strftime("%d/%m/%Y %I:%M %p")

        # Column structure (12 Columns): 
        # No, Date, user_id, User_name, Phone, Contact, Product, Plan, Price, Cost, Profit, Status
        new_row = [
            order_no, 
            now, 
            user_id, 
            user_name, 
            user_text,    # Phone (as typed by user)
            "-",          # Contact (Optional extra field)
            order_info.get('Name'), 
            order_info.get('Plan'), 
            price, 
            cost, 
            profit, 
            "Pending"
        ]

        order_sheet.append_row(new_row)

        await update.message.reply_text(
            f"✅ **လူကြီးမင်း၏ အော်ဒါ (ID: {order_no}) ကို လက်ခံရရှိပါပြီ!**\n\n"
            f"Admin မှ အချက်အလက်များကို စစ်ဆေးပြီး အမြန်ဆုံး ဆက်သွယ်ဆောင်ရွက်ပေးပါမည်။ ကျေးဇူးတင်ပါတယ်ရှင်။",
            parse_mode='Markdown'
        )
        
        # Clear order data after saving
        context.user_data['last_order'] = None

# --- Main Entry ---
def main():
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TOKEN: return

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    # Filter text only (avoid commands)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_order_message))
    
    Thread(target=run_web_server).start()
    application.run_polling()

if __name__ == '__main__':
    main()
