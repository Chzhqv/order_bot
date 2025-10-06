import os
import asyncio
import re
import logging

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))

if not BOT_TOKEN or not ADMIN_CHAT_ID:
    raise ValueError("BOT_TOKEN and ADMIN_CHAT_ID must be set in the environment.")

# Define your menu items
MENU_ITEMS = {
    "vodka - absolute": {"name": "Vodka", "price": 80.00},
    "jagermaister": {"name": "Jagermaister", "price": 80.50},
    "vvvisky": {"name": "VVVisky", "price": 80.00},
    "soda": {"name": "Soda Pop 🥤", "price": 3000.00},
}

# --- FSM States ---
class OrderForm(StatesGroup):
    waiting_for_address = State()
    waiting_for_item_selection = State()
    waiting_for_phone_number = State()

# v3: Using a Router for handlers
router = Router()

# --- Handlers ---

# v3: Handler registration uses the router and new filters like Command()
@router.message(Command("start", "help"))
async def send_welcome(message: types.Message, state: FSMContext):
    """
    Handler for /start and /help commands. Starts the order process.
    """
    await message.reply("Hello! Welcome to our ordering service. What's your delivery address?")
    # v3: Setting state is now done with state.set_state()
    await state.set_state(OrderForm.waiting_for_address)

# v3: State-based handlers are now registered directly with the state
@router.message(OrderForm.waiting_for_address)
async def process_address(message: types.Message, state: FSMContext):
    """
    Processes the user's address and asks for menu selection.
    """
    if not message.text or len(message.text) < 5:
        await message.reply("That doesn't look like a complete address. Please provide a more detailed address.")
        return

    # v3: Storing data is done with state.update_data()
    await state.update_data(address=message.text)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{item_data['name']} - ${item_data['price']:.2f}",
                callback_data=f"select_item_{item_id}"
            )] for item_id, item_data in MENU_ITEMS.items()
        ]
    )

    await message.reply("Great! Now, what would you like to order?", reply_markup=keyboard)
    await state.set_state(OrderForm.waiting_for_item_selection)

# v3: Callback handlers use magic filters (F) for checking callback_data
@router.callback_query(OrderForm.waiting_for_item_selection, F.data.startswith("select_item_"))
async def process_item_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Processes the user's item selection from the inline keyboard.
    """
    item_id = callback_query.data.split('_')[2]
    
    if item_id not in MENU_ITEMS:
        await callback_query.message.answer("Sorry, that item is not available. Please choose from the menu.")
        return

    selected_item = MENU_ITEMS[item_id]
    
    await state.update_data(item_name=selected_item['name'], item_price=selected_item['price'])

    await callback_query.message.edit_text(f"You've selected: {selected_item['name']}.") # Remove keyboard and update text
    await callback_query.message.answer("What is your Canadian phone number (e.g., 123-456-7890)?")
    await state.set_state(OrderForm.waiting_for_phone_number)
    await callback_query.answer() # Acknowledge the callback

@router.message(OrderForm.waiting_for_phone_number)
async def process_phone_number(message: types.Message, state: FSMContext, bot: Bot):
    """
    Processes the user's phone number, validates it, and finalizes the order.
    """
    phone_number_pattern = r"^(?:\+1|1)?[\s.-]?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})$"
    if not message.text or not re.match(phone_number_pattern, message.text):
        await message.reply("That doesn't look like a valid Canadian phone number. Please try again.")
        return

    await state.update_data(phone_number=message.text)
    
    # v3: Getting all stored data is done with state.get_data()
    user_data = await state.get_data()
    
    order_summary = f"""
✨ New Order Received! ✨

👤 User: @{message.from_user.username or message.from_user.full_name} (ID: {message.from_user.id})
🏡 Address: {user_data['address']}
🛒 Item: {user_data['item_name']} (${user_data['item_price']:.2f})
📞 Phone: {user_data['phone_number']}

-----------------------------------
Please contact the customer to confirm the order.
"""
    
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=order_summary)
        await message.reply("Thank you! Your order has been placed. We will contact you shortly to confirm.")
    except Exception as e:
        logging.error(f"Error sending order to admin: {e}")
        await message.reply("Sorry, there was an issue placing your order. Please try again later.")

    # v3: Finishing a state is done with state.clear()
    await state.clear()

# --- Main function to start the bot ---
async def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Bot and Dispatcher initialization
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # v3: Include the router in the dispatcher
    dp.include_router(router)

    # Before starting polling, drop pending updates
    await bot.delete_webhook(drop_pending_updates=True)

    print("Bot is starting...")
    # v3: The bot object is passed to start_polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())