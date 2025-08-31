from aiogram.fsm.state import StatesGroup, State


class PurchaseState(StatesGroup):
    choosing_quantity = State()
    choosing_price = State()
    waiting_promo_code = State()  # <--- НОВОЕ СОСТОЯНИЕ
    waiting_payment_confirm = State()
    waiting_payment_proof = State()
    on_review = State()
