"""
Handler de Start / Menu Principal.
====================================
Comando /start, /menu, e navegação do menu principal.
Incluí sistema de referral (indicação via deep link).
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart

from bot.config import get_config, sistema_configurado
from bot.database.queries import buscar_usuario, criar_usuario, registrar_indicacao, atualizar_saldo
from bot.keyboards.inline import menu_principal, voltar_menu
from bot.utils.helpers import formatar_moeda, escape_html, safe_edit_message, safe_send_message
from bot.utils.logger import logger

router = Router()


@router.message(CommandStart(deep_link=True))
async def cmd_start_referral(message: Message):
    """Start com deep link (indicação)."""
    args = message.text.split()
    referral_code = args[1] if len(args) > 1 else None

    # Verificar se sistema está configurado
    if not await sistema_configurado():
        await message.answer(
            "🔧 Este bot ainda não foi configurado.\n"
            "Use /setup para realizar a configuração inicial."
        )
        return

    # Processar indicação
    if referral_code and referral_code.startswith("ref_"):
        try:
            referrer_id = int(referral_code.replace("ref_", ""))
            # Verificar se o indicador existe
            referrer = await buscar_usuario(referrer_id)
            if referrer and referrer['telegram_id'] != message.from_user.id:
                # Criar usuário com indicação
                user = await criar_usuario(
                    message.from_user.id,
                    message.from_user.full_name or "Sem Nome",
                    message.from_user.username or "",
                    indicado_por=referrer['id']
                )
                # Registrar indicação (comissão será paga depois)
                comissao_pct = float(await get_config('comissao_indicacao', '5'))
                await registrar_indicacao(referrer['id'], user['id'], comissao_pct)
                logger.info(f"👥 Indicação registrada: {referrer_id} -> {message.from_user.id}")
                
                # Enviar notificação de novo usuário
                from bot.services.notifications import enviar_notificacao_novo_usuario
                await enviar_notificacao_novo_usuario(
                    bot=message.bot,
                    user_id=message.from_user.id,
                    username=message.from_user.username or '',
                    first_name=message.from_user.full_name or 'Sem Nome'
                )
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Código de indicação inválido: {referral_code} - {e}")

    await _enviar_menu_principal(message)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Comando /start sem deep link."""
    if not await sistema_configurado():
        await message.answer(
            "🔧 <b>Bem-vindo!</b>\n\n"
            "Este bot ainda não foi configurado.\n"
            "Use /setup para realizar a configuração inicial.",
            parse_mode='HTML'
        )
        return
    
    # Enviar notificação de novo usuário
    from bot.services.notifications import enviar_notificacao_novo_usuario
    await enviar_notificacao_novo_usuario(
        bot=message.bot,
        user_id=message.from_user.id,
        username=message.from_user.username or '',
        first_name=message.from_user.full_name or 'Sem Nome'
    )
    
    await _enviar_menu_principal(message)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Comando /menu."""
    await _enviar_menu_principal(message)


@router.message(Command("saldo"))
async def cmd_saldo(message: Message):
    """Comando /saldo."""
    user = await buscar_usuario(message.from_user.id)
    if user:
        saldo = formatar_moeda(user['saldo'])
        await message.answer(
            f"💰 <b>Seu Saldo</b>\n\n"
            f"📊 Saldo disponível: <b>{saldo}</b>\n\n"
            f"Use o menu para adicionar saldo ou comprar serviços.",
            parse_mode='HTML',
            reply_markup=menu_principal()
        )


@router.callback_query(F.data == "menu")
async def callback_menu(callback: CallbackQuery):
    """Volta ao menu principal."""
    await callback.answer()
    user = await buscar_usuario(callback.from_user.id)
    saldo = formatar_moeda(user['saldo']) if user else "R$ 0,00"
    msg_inicio = await get_config('mensagem_inicio',
                                   '🤖 Bem-vindo ao Bot de Serviços SMM!\n\nEscolha uma opção:')
    # Substituir \\n por \n real


    nome = escape_html(callback.from_user.full_name)
    texto = (
        f"{escape_html(msg_inicio)}\n\n"
        f"👤 {nome}\n"
        f"💰 Saldo: <b>{saldo}</b>"
    )

    await safe_edit_message(callback.message, texto, reply_markup=menu_principal())


@router.callback_query(F.data == "ver_saldo")
async def callback_ver_saldo(callback: CallbackQuery):
    """Mostra saldo detalhado - TELA DEDICADA."""
    await callback.answer()
    user = await buscar_usuario(callback.from_user.id)
    if user:
        saldo = formatar_moeda(user['saldo'])
        total_gasto = formatar_moeda(user['total_gasto'])
        texto = (
            f"💰 <b>SUAS FINANÇAS</b>\n\n"
            f"📊 Saldo atual: <b>{saldo}</b>\n"
            f"💸 Total gasto: {total_gasto}\n"
            f"📦 Total de pedidos: {user['total_pedidos']}\n\n"
            f"💡 Use o menu para adicionar saldo ou fazer uma compra."
        )
        # Envia NOVA mensagem ao invés de editar
        await callback.message.answer(texto, reply_markup=voltar_menu())


@router.callback_query(F.data == "indicar")
async def callback_indicar(callback: CallbackQuery):
    """Mostra link de indicação - TELA DEDICADA."""
    await callback.answer()
    from bot.config import get_config
    bot_info = await callback.bot.me()
    bot_username = bot_info.username
    comissao = await get_config('comissao_indicacao', '5')

    link = f"https://t.me/{bot_username}?start=ref_{callback.from_user.id}"

    texto = (
        f"👥 <b>INDICAR AMIGO</b>\n\n"
        f"Convide amigos e ganhe <b>{comissao}%</b> de comissão\n"
        f"sobre a primeira compra de cada indicado!\n\n"
        f"🔗 <b>Seu link de indicação:</b>\n"
        f"<code>{link}</code>\n\n"
        f"📋 Copie e compartilhe com seus amigos!"
    )

    # Envia NOVA mensagem ao invés de editar
    await callback.message.answer(texto, reply_markup=voltar_menu())


async def _enviar_menu_principal(message: Message):
    """Envia menu principal."""
    user = await buscar_usuario(message.from_user.id)
    saldo = formatar_moeda(user['saldo']) if user else "R$ 0,00"

    msg_inicio = await get_config('mensagem_inicio',
                                   '🤖 Bem-vindo ao Bot de Serviços SMM!\n\nEscolha uma opção:')
    msg_inicio = msg_inicio.replace('\\n', '\n')

    nome = escape_html(message.from_user.full_name)
    texto = (
        f"{escape_html(msg_inicio)}\n\n"
        f"👤 {nome}\n"
        f"💰 Saldo: <b>{saldo}</b>"
    )

    await message.answer(
        texto,
        parse_mode='HTML',
        reply_markup=menu_principal()
    )
