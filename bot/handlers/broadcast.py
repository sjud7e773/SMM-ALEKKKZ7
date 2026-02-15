"""
Handler de Broadcast.
======================
Envio de mensagem em massa a todos os usuários.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

from bot.config import is_admin
from bot.database.queries import buscar_todos_telegram_ids
from bot.keyboards.inline import voltar_admin
from bot.utils.logger import logger

router = Router()


class BroadcastStates(StatesGroup):
    """Estados do broadcast."""
    aguardando_mensagem = State()


@router.callback_query(F.data == "adm:broadcast")
async def callback_broadcast(callback: CallbackQuery, state: FSMContext):
    """Inicia broadcast."""
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Acesso negado.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Envie a mensagem que deseja enviar a todos os usuários.\n\n"
        "⚠️ A mensagem será enviada para TODOS os usuários ativos.\n"
        "Suporta texto com formatação HTML.",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.set_state(BroadcastStates.aguardando_mensagem)


@router.message(BroadcastStates.aguardando_mensagem)
async def enviar_broadcast(message: Message, state: FSMContext):
    """Envia mensagem para todos os usuários."""
    if not await is_admin(message.from_user.id):
        await state.clear()
        return

    texto = message.text
    if not texto:
        await message.answer("❌ Envie uma mensagem de texto.")
        return

    telegram_ids = await buscar_todos_telegram_ids()
    total = len(telegram_ids)
    enviados = 0
    falhas = 0

    await message.answer(f"📢 Enviando broadcast para {total} usuários...")

    for tid in telegram_ids:
        try:
            await message.bot.send_message(tid, texto, parse_mode='HTML')
            enviados += 1
        except Exception:
            falhas += 1

        # Rate limit do Telegram (30 msg/s)
        if enviados % 25 == 0:
            await asyncio.sleep(1)

    await message.answer(
        f"📢 <b>Broadcast concluído!</b>\n\n"
        f"✅ Enviados: {enviados}\n"
        f"❌ Falhas: {falhas}\n"
        f"📊 Total: {total}",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )

    logger.info(f"📢 Broadcast enviado: {enviados}/{total} (falhas: {falhas})")
    await state.clear()
