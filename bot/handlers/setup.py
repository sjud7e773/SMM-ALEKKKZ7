"""
Handler de Setup Inicial.
==========================
Configuração inicial: define admin via /setup.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from bot.config import sistema_configurado, set_config
from bot.keyboards.inline import setup_confirmar, menu_principal
from bot.utils.helpers import escape_html
from bot.utils.logger import logger

router = Router()


@router.message(Command("setup"))
async def cmd_setup(message: Message):
    """Comando /setup - configuração inicial."""
    if await sistema_configurado():
        from bot.config import is_admin
        if await is_admin(message.from_user.id):
            await message.answer(
                "✅ Bot já configurado! Use /admin para gerenciar.",
                reply_markup=menu_principal()
            )
        else:
            await message.answer(
                "⚠️ Este bot já foi configurado e possui um administrador.\n"
                "Se você precisa de acesso, entre em contato com o administrador."
            )
        return

    # Nenhum admin definido - oferecer setup
    nome = escape_html(message.from_user.full_name)
    await message.answer(
        "🔧 <b>CONFIGURAÇÃO INICIAL DO BOT</b>\n\n"
        "Este bot ainda não possui um administrador configurado.\n\n"
        f"👤 <b>Seu Telegram ID:</b> <code>{message.from_user.id}</code>\n"
        f"📛 <b>Seu nome:</b> {nome}\n\n"
        "⚠️ <b>ATENÇÃO:</b> Ao confirmar, você será definido como o administrador\n"
        "e terá acesso total ao painel de controle do bot.\n\n"
        "Deseja se tornar o administrador deste bot?",
        parse_mode='HTML',
        reply_markup=setup_confirmar(message.from_user.id)
    )


@router.callback_query(F.data.startswith("setup_confirm:"))
async def callback_setup_confirm(callback: CallbackQuery):
    """Confirma setup do admin."""
    telegram_id = int(callback.data.split(":")[1])

    if callback.from_user.id != telegram_id:
        await callback.answer("❌ Ação não permitida.", show_alert=True)
        return

    if await sistema_configurado():
        await callback.answer("⚠️ Bot já configurado!", show_alert=True)
        return

    await set_config('admin_id', str(telegram_id))
    await set_config('sistema_configurado', '1')

    logger.info(f"🔐 Admin configurado: {telegram_id} ({callback.from_user.full_name})")

    nome = escape_html(callback.from_user.full_name)
    await callback.message.edit_text(
        "✅ <b>CONFIGURAÇÃO CONCLUÍDA!</b>\n\n"
        f"👤 <b>Admin:</b> {nome}\n"
        f"🆔 <b>ID:</b> <code>{telegram_id}</code>\n\n"
        "📋 <b>Próximos passos:</b>\n"
        "1️⃣ Use /admin para acessar o painel\n"
        "2️⃣ Configure a API Key do painel SMM\n"
        "3️⃣ Configure os gateways de pagamento\n"
        "4️⃣ Sincronize os serviços\n"
        "5️⃣ Ative os gateways desejados\n\n"
        "🚀 Seu bot está pronto para configuração!",
        parse_mode='HTML',
        reply_markup=menu_principal()
    )
    await callback.answer("✅ Pronto!")
