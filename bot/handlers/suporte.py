"""
Handler de Suporte + Sistema de Tickets.
===========================================
Tickets com ID único, encaminhamento ao dono,
FAQ, promoções e cupons.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import get_config
from bot.keyboards.inline import suporte_teclado, menu_principal, voltar_menu
from bot.utils.helpers import escape_html, safe_edit_message, formatar_moeda
from bot.utils.logger import logger

router = Router()


class SuporteStates(StatesGroup):
    """Estados do suporte."""
    aguardando_mensagem = State()
    aguardando_cupom = State()


# ==========================================
# SUPORTE PRINCIPAL
# ==========================================

@router.message(Command("suporte"))
async def cmd_suporte(message: Message):
    """Comando /suporte."""
    await message.answer(
        "📞 <b>Suporte</b>\n\n"
        "Como podemos ajudá-lo?",
        parse_mode='HTML',
        reply_markup=suporte_teclado()
    )


@router.callback_query(F.data == "suporte")
async def callback_suporte(callback: CallbackQuery):
    """Callback suporte - TELA DEDICADA."""
    await callback.answer()
    # Envia NOVA mensagem ao invés de editar
    await callback.message.answer(
        "📞 <b>CENTRAL DE SUPORTE</b>\n\n"
        "Como podemos ajudá-lo hoje?\n\n"
        "❓ Consulte as perguntas frequentes (FAQ)\n"
        "💬 Ou envie uma mensagem para nossa equipe",
        reply_markup=suporte_teclado()
    )


# ==========================================
# TICKETS
# ==========================================

@router.callback_query(F.data == "sup:msg")
async def callback_suporte_msg(callback: CallbackQuery, state: FSMContext):
    """Inicia envio de mensagem ao suporte (ticket) - TELA DEDICADA."""
    await callback.answer()
    # Envia NOVA mensagem ao invés de editar
    await callback.message.answer(
        "💬 <b>ABRIR TICKET DE SUPORTE</b>\n\n"
        "Escreva sua mensagem abaixo e nossa equipe\n"
        "responderá o mais breve possível.\n\n"
        "📝 Digite sua mensagem:",
        reply_markup=voltar_menu()
    )
    await state.set_state(SuporteStates.aguardando_mensagem)


@router.message(SuporteStates.aguardando_mensagem)
async def receber_msg_suporte(message: Message, state: FSMContext):
    """Recebe mensagem e cria ticket."""
    from bot.database.connection import get_db
    import random

    user_id = message.from_user.id
    texto_msg = message.text or "(sem texto)"

    # Gerar ticket ID único
    ticket_id = f"T{random.randint(10000, 99999)}"

    # Salvar ticket no banco
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO tickets (ticket_id, telegram_id, tipo, mensagem, status)
               VALUES (?, ?, 'suporte', ?, 'aberto')""",
            (ticket_id, user_id, texto_msg)
        )
        await db.commit()
    except Exception as e:
        logger.error(f"❌ Erro ao criar ticket: {e}")
    finally:
        await db.close()

    # Encaminhar ao dono/admin
    admin_id = await get_config('admin_id', '')
    if not admin_id:
        # Buscar owner
        from bot.database.queries_owner import buscar_owner
        owner = await buscar_owner()
        if owner:
            admin_id = str(owner['telegram_id'])

    if admin_id:
        try:
            nome = escape_html(message.from_user.full_name)
            username = message.from_user.username or 'N/A'
            await message.bot.send_message(
                int(admin_id),
                f"📩 <b>Novo Ticket #{ticket_id}</b>\n\n"
                f"👤 <b>De:</b> {nome}\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"📛 <b>Username:</b> @{username}\n\n"
                f"💬 <b>Mensagem:</b>\n{escape_html(texto_msg)}",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Erro ao enviar ticket ao admin: {e}")

    await message.answer(
        f"✅ <b>Ticket criado!</b>\n\n"
        f"🎫 Número: <code>{ticket_id}</code>\n\n"
        f"O administrador receberá sua mensagem e\n"
        f"responderá assim que possível.\n\n"
        f"Obrigado pelo contato!",
        parse_mode='HTML',
        reply_markup=menu_principal()
    )
    await state.clear()


# ==========================================
# REPORTAR PROBLEMA (pós-entrega)
# ==========================================

@router.callback_query(F.data.startswith("reportar:"))
async def callback_reportar_problema(callback: CallbackQuery):
    """Mostra aviso antes de abrir ticket de problema."""
    await callback.answer()
    pedido_id = callback.data.split(":")[1]

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚠️ Sim, tenho um problema real",
            callback_data=f"confirmar_report:{pedido_id}"
        )],
        [InlineKeyboardButton(
            text="🔙 Voltar",
            callback_data=f"ped:{pedido_id}"
        )]
    ])

    await safe_edit_message(
        callback.message,
        "⚠️ <b>Reportar Problema — Atenção!</b>\n\n"
        "Falsos relatos de problemas podem resultar em\n"
        "<b>suspensão permanente</b> da sua conta.\n\n"
        "Só prossiga se você realmente teve um problema\n"
        "com a entrega do serviço.\n\n"
        "Deseja continuar?",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("confirmar_report:"))
async def callback_confirmar_report(callback: CallbackQuery, state: FSMContext):
    """Confirma e abre ticket de problema."""
    await callback.answer()
    pedido_id = callback.data.split(":")[1]

    from bot.database.connection import get_db
    import random

    ticket_id = f"P{random.randint(10000, 99999)}"

    # Salvar ticket
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO tickets (ticket_id, telegram_id, tipo, mensagem, pedido_id, status)
               VALUES (?, ?, 'problema', ?, ?, 'aberto')""",
            (ticket_id, callback.from_user.id,
             f"Problema reportado no pedido #{pedido_id}", int(pedido_id))
        )
        await db.commit()
    except Exception as e:
        logger.error(f"❌ Erro ao criar ticket de problema: {e}")
    finally:
        await db.close()

    # Notificar dono
    admin_id = await get_config('admin_id', '')
    if not admin_id:
        from bot.database.queries_owner import buscar_owner
        owner = await buscar_owner()
        if owner:
            admin_id = str(owner['telegram_id'])

    if admin_id:
        try:
            nome = escape_html(callback.from_user.full_name)
            await callback.bot.send_message(
                int(admin_id),
                f"🚨 <b>Problema Reportado #{ticket_id}</b>\n\n"
                f"👤 {nome} (ID: <code>{callback.from_user.id}</code>)\n"
                f"📦 Pedido: <b>#{pedido_id}</b>\n\n"
                f"Verifique o status deste pedido.",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"❌ Erro ao notificar problema: {e}")

    await safe_edit_message(
        callback.message,
        f"🎫 <b>Ticket #{ticket_id} aberto</b>\n\n"
        f"📦 Referente ao pedido <b>#{pedido_id}</b>\n\n"
        f"O administrador foi notificado e analisará\n"
        f"o problema o mais rápido possível.",
        reply_markup=menu_principal()
    )


# ==========================================
# FAQ
# ==========================================

@router.callback_query(F.data == "sup:faq")
async def callback_faq(callback: CallbackQuery):
    """FAQ."""
    await callback.answer()
    await safe_edit_message(
        callback.message,
        "❓ <b>Perguntas Frequentes</b>\n\n"
        "<b>1. Como comprar serviços?</b>\n"
        "Use o botão 🛒 Comprar Serviço no menu.\n\n"
        "<b>2. Como adicionar saldo?</b>\n"
        "Use 💰 Adicionar Saldo e pague via PIX.\n\n"
        "<b>3. Quanto tempo demora o pedido?</b>\n"
        "Depende do serviço. A maioria inicia em minutos.\n\n"
        "<b>4. Posso cancelar um pedido?</b>\n"
        "Sim, desde que ainda não tenha sido iniciado.\n\n"
        "<b>5. O que é refill?</b>\n"
        "Reposição gratuita caso o serviço sofra queda.\n\n"
        "<b>6. Como indicar amigos?</b>\n"
        "Use o botão 👥 Indicar Amigo no menu para\n"
        "obter seu link de indicação.\n\n"
        "Dúvidas? Use 💬 Enviar Mensagem.",
        reply_markup=suporte_teclado()
    )


# ==========================================
# PROMOÇÕES
# ==========================================

@router.callback_query(F.data == "promocoes")
async def callback_promocoes(callback: CallbackQuery):
    """Promoções ativas - TELA DEDICADA."""
    await callback.answer()
    from bot.database.connection import get_db
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM cupons WHERE ativo = 1 AND (validade IS NULL OR validade > datetime('now','localtime'))"
        )
        cupons = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()

    if cupons:
        texto = "🎁 <b>PROMOÇÕES ATIVAS</b>\n\n"
        for c in cupons:
            if c['desconto_pct'] > 0:
                texto += f"🎟️ <code>{c['codigo']}</code> — {c['desconto_pct']}% de desconto\n"
            elif c['desconto_fixo'] > 0:
                texto += f"🎟️ <code>{c['codigo']}</code> — {formatar_moeda(c['desconto_fixo'])} de desconto\n"
            restantes = c['usos_max'] - c['usos_atuais']
            texto += f"   Usos restantes: {restantes}\n\n"
        texto += "\n💡 Use o comando /cupom para aplicar."
    else:
        texto = "🎁 <b>PROMOÇÕES</b>\n\nNenhuma promoção ativa no momento.\nFique atento às novidades!"

    # Envia NOVA mensagem ao invés de editar
    await callback.message.answer(
        texto,
        reply_markup=voltar_menu()
    )


# ==========================================
# CUPONS
# ==========================================

@router.callback_query(F.data == "usar_cupom")
async def callback_usar_cupom(callback: CallbackQuery, state: FSMContext):
    """Usar cupom - TELA DEDICADA."""
    await callback.answer()
    # Envia NOVA mensagem ao invés de editar
    await callback.message.answer(
        "🎟️ <b>USAR CUPOM DE DESCONTO</b>\n\n"
        "Digite o código do cupom:",
        reply_markup=voltar_menu()
    )
    await state.set_state(SuporteStates.aguardando_cupom)


@router.message(SuporteStates.aguardando_cupom)
async def receber_cupom(message: Message, state: FSMContext):
    """Recebe código de cupom."""
    from bot.database.queries import buscar_cupom, usar_cupom, atualizar_saldo
    codigo = message.text.strip().upper()
    cupom = await buscar_cupom(codigo)

    if not cupom:
        await message.answer(
            "❌ Cupom inválido ou expirado.\n\n"
            "Verifique o código e tente novamente.",
            reply_markup=menu_principal()
        )
        await state.clear()
        return

    # Aplicar cupom como crédito de saldo
    if cupom['desconto_fixo'] > 0:
        valor = cupom['desconto_fixo']
        await atualizar_saldo(message.from_user.id, valor, 'adicionar')
        await usar_cupom(codigo)
        await message.answer(
            f"✅ <b>Cupom aplicado!</b>\n\n"
            f"💰 {formatar_moeda(valor)} adicionados ao seu saldo!",
            parse_mode='HTML',
            reply_markup=menu_principal()
        )
    elif cupom['desconto_pct'] > 0:
        await usar_cupom(codigo)
        await message.answer(
            f"✅ <b>Cupom ativado!</b>\n\n"
            f"🎟️ {cupom['desconto_pct']}% de desconto\n"
            f"será aplicado na próxima compra.",
            parse_mode='HTML',
            reply_markup=menu_principal()
        )

    await state.clear()
