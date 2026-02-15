"""
Handler de Pedidos.
====================
Consulta de pedidos, status, refill e cancelamento.
Usa HTML parse mode e safe_edit_message.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.queries import (
    buscar_usuario, buscar_pedidos_usuario, buscar_pedido,
    atualizar_status_pedido, buscar_servico_por_api_id
)
from bot.services.smm_api import ver_status, refill as api_refill, cancelar as api_cancelar
from bot.keyboards.inline import lista_pedidos, detalhes_pedido, menu_principal, voltar_menu
from bot.utils.helpers import (
    formatar_moeda, formatar_numero, formatar_data,
    status_emoji, escape_html, safe_edit_message
)
from bot.utils.logger import logger

router = Router()


class PedidoStates(StatesGroup):
    """Estados para consulta direta."""
    aguardando_id = State()


@router.message(Command("pedidos"))
async def cmd_pedidos(message: Message):
    """Comando /pedidos."""
    user = await buscar_usuario(message.from_user.id)
    if not user:
        await message.answer("❌ Usuário não encontrado.", reply_markup=menu_principal())
        return

    pedidos = await buscar_pedidos_usuario(user['id'])
    if not pedidos:
        await message.answer(
            "📦 Você ainda não possui pedidos.\n\n"
            "Use /comprar para fazer seu primeiro pedido!",
            reply_markup=menu_principal()
        )
        return

    await message.answer(
        f"📦 <b>Seus Pedidos</b> ({len(pedidos)} total)\n\n"
        f"Clique em um pedido para ver detalhes:",
        parse_mode='HTML',
        reply_markup=lista_pedidos(pedidos)
    )


@router.callback_query(F.data == "meus_pedidos")
async def callback_meus_pedidos(callback: CallbackQuery):
    """Callback para Meus Pedidos - TELA DEDICADA."""
    await callback.answer()
    user = await buscar_usuario(callback.from_user.id)
    if not user:
        return

    pedidos = await buscar_pedidos_usuario(user['id'])
    if not pedidos:
        # Envia NOVA mensagem ao invés de editar
        await callback.message.answer(
            "📦 <b>MEUS PEDIDOS</b>\n\n"
            "Você ainda não possui pedidos.\n\n"
            "Comece fazendo sua primeira compra!",
            reply_markup=voltar_menu()
        )
        return

    # Envia NOVA mensagem ao invés de editar
    await callback.message.answer(
        f"📦 <b>MEUS PEDIDOS</b>\n\n"
        f"Total: <b>{len(pedidos)} pedido(s)</b>\n\n"
        f"Clique em um pedido para ver detalhes:",
        reply_markup=lista_pedidos(pedidos)
    )


@router.callback_query(F.data.startswith("peds_pag:"))
async def callback_pedidos_pag(callback: CallbackQuery):
    """Paginação de pedidos."""
    await callback.answer()
    pagina = int(callback.data.split(":")[1])
    user = await buscar_usuario(callback.from_user.id)
    pedidos = await buscar_pedidos_usuario(user['id'])

    await safe_edit_message(
        callback.message,
        "📦 <b>Seus Pedidos</b>\n\nClique para ver detalhes:",
        reply_markup=lista_pedidos(pedidos, pagina)
    )


def _montar_detalhes_pedido(pedido: dict, servico: dict = None) -> str:
    """Monta texto HTML de detalhes do pedido."""
    emoji = status_emoji(pedido.get('status_api') or pedido['status'])
    nome = escape_html(pedido.get('servico_nome', 'Serviço'))

    # Refill / Cancel flags
    pode_refill = bool(servico and servico.get('permite_refill'))
    pode_cancel = bool(servico and servico.get('permite_cancel'))

    texto = (
        f"📋 <b>Pedido #{pedido['id']}</b>\n\n"
        f"🔹 <b>Serviço:</b> {nome}\n"
        f"🔗 <b>Link:</b> <code>{escape_html(pedido['link'])}</code>\n"
        f"📊 <b>Quantidade:</b> {formatar_numero(pedido['quantidade'])}\n"
        f"💰 <b>Valor:</b> {formatar_moeda(pedido['preco_final'])}\n\n"
        f"{emoji} <b>Status:</b> {pedido.get('status_api') or pedido['status']}\n"
    )

    if pedido.get('order_id_api'):
        texto += f"📋 <b>ID API:</b> {pedido['order_id_api']}\n"

    if pedido.get('start_count'):
        texto += f"📈 <b>Início:</b> {formatar_numero(pedido['start_count'])}\n"

    if pedido.get('remains') and pedido['remains'] > 0:
        texto += f"⚠️ <b>Restantes:</b> {formatar_numero(pedido['remains'])}\n"

    texto += f"\n📅 <b>Criado em:</b> {formatar_data(pedido['criado_em'])}\n"

    # Mostrar flags de refill/cancel
    texto += f"\n🔁 Refill: {'🟢 Disponível' if pode_refill else '🔴 Indisponível'}\n"
    texto += f"❌ Cancel: {'🟢 Disponível' if pode_cancel else '🔴 Indisponível'}"

    return texto


@router.callback_query(F.data.startswith("ped:"))
async def callback_detalhe_pedido(callback: CallbackQuery):
    """Mostra detalhes de um pedido."""
    await callback.answer()
    pedido_id = int(callback.data.split(":")[1])
    pedido = await buscar_pedido(pedido_id)

    if not pedido:
        await callback.answer("❌ Pedido não encontrado.", show_alert=True)
        return

    servico = await buscar_servico_por_api_id(pedido.get('service_id_api', 0))
    pode_refill = bool(servico and servico.get('permite_refill'))
    pode_cancel = bool(servico and servico.get('permite_cancel'))

    texto = _montar_detalhes_pedido(pedido, servico)

    # Adicionar botão de reportar problema se pedido completado
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = [
        [InlineKeyboardButton(text="🔄 Atualizar Status", callback_data=f"refresh_ped:{pedido_id}")],
    ]
    if pedido.get('order_id_api'):
        acoes = []
        if pode_refill:
            acoes.append(InlineKeyboardButton(text="🔁 Refill", callback_data=f"refill:{pedido_id}"))
        if pode_cancel:
            acoes.append(InlineKeyboardButton(text="❌ Cancelar", callback_data=f"cancel_ped:{pedido_id}"))
        if acoes:
            buttons.append(acoes)

    # Botão reportar (só se pedido concluído ou em andamento)
    status = (pedido.get('status_api') or pedido['status']).lower()
    if status in ('completed', 'concluido', 'in progress', 'em_andamento', 'processing'):
        buttons.append([InlineKeyboardButton(
            text="⚠️ Reportar Problema",
            callback_data=f"reportar:{pedido_id}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Meus Pedidos", callback_data="meus_pedidos")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_message(callback.message, texto, reply_markup=kb)


@router.callback_query(F.data.startswith("refresh_ped:"))
async def callback_refresh_pedido(callback: CallbackQuery):
    """Atualiza status de um pedido específico."""
    await callback.answer("🔄 Atualizando...")
    pedido_id = int(callback.data.split(":")[1])
    pedido = await buscar_pedido(pedido_id)

    if not pedido or not pedido.get('order_id_api'):
        await callback.answer("❌ Sem ID da API para atualizar.", show_alert=True)
        return

    resultado = await ver_status(pedido['order_id_api'])

    if 'error' in resultado:
        await callback.answer(f"❌ Erro: {resultado['error']}", show_alert=True)
        return

    status_api = resultado.get('status', '')
    start_count = int(resultado.get('start_count', 0))
    remains = int(resultado.get('remains', 0))

    status_local = status_api
    if status_api in ('Completed',):
        status_local = 'concluido'
    elif status_api in ('Canceled', 'Refunded'):
        status_local = 'cancelado'
    elif status_api in ('In progress', 'Processing'):
        status_local = 'em_andamento'

    await atualizar_status_pedido(pedido_id, status_local, status_api, start_count, remains)

    # Recarregar detalhes
    pedido = await buscar_pedido(pedido_id)
    servico = await buscar_servico_por_api_id(pedido.get('service_id_api', 0))
    pode_refill = bool(servico and servico.get('permite_refill'))
    pode_cancel = bool(servico and servico.get('permite_cancel'))

    texto = _montar_detalhes_pedido(pedido, servico)
    texto = texto.replace(f"<b>Pedido #{pedido['id']}</b>",
                          f"<b>Pedido #{pedido['id']}</b> (Atualizado ✅)")

    await safe_edit_message(
        callback.message,
        texto,
        reply_markup=detalhes_pedido(
            pedido['id'], pedido.get('order_id_api', ''),
            permite_refill=pode_refill, permite_cancel=pode_cancel
        )
    )


@router.callback_query(F.data.startswith("refill:"))
async def callback_refill(callback: CallbackQuery):
    """Solicita refill de um pedido."""
    pedido_id = int(callback.data.split(":")[1])
    pedido = await buscar_pedido(pedido_id)

    if not pedido or not pedido.get('order_id_api'):
        await callback.answer("❌ Pedido sem ID da API.", show_alert=True)
        return

    # Verificar se serviço permite refill
    servico = await buscar_servico_por_api_id(pedido.get('service_id_api', 0))
    if not servico or not servico.get('permite_refill'):
        await callback.answer("🔴 Este serviço não suporta refill.", show_alert=True)
        return

    resultado = await api_refill(pedido['order_id_api'])

    if 'error' in resultado:
        await callback.answer(f"❌ {resultado['error']}", show_alert=True)
    else:
        await callback.answer("✅ Refill solicitado com sucesso!", show_alert=True)


@router.callback_query(F.data.startswith("cancel_ped:"))
async def callback_cancelar_pedido(callback: CallbackQuery):
    """Solicita cancelamento de um pedido."""
    pedido_id = int(callback.data.split(":")[1])
    pedido = await buscar_pedido(pedido_id)

    if not pedido or not pedido.get('order_id_api'):
        await callback.answer("❌ Pedido sem ID da API.", show_alert=True)
        return

    # Verificar se serviço permite cancel
    servico = await buscar_servico_por_api_id(pedido.get('service_id_api', 0))
    if not servico or not servico.get('permite_cancel'):
        await callback.answer("🔴 Este serviço não suporta cancelamento.", show_alert=True)
        return

    resultado = await api_cancelar(pedido['order_id_api'])

    if 'error' in resultado:
        await callback.answer(f"❌ {resultado['error']}", show_alert=True)
    else:
        await atualizar_status_pedido(pedido_id, 'cancelado', 'Canceled')
        await callback.answer("✅ Cancelamento solicitado!", show_alert=True)
        await safe_edit_message(
            callback.message,
            f"❌ <b>Pedido #{pedido_id} cancelado.</b>",
            reply_markup=menu_principal()
        )


@router.message(Command("status"))
async def cmd_status(message: Message, state: FSMContext):
    """Comando /status - pede ID do pedido."""
    await message.answer(
        "📈 <b>Consultar Status</b>\n\n"
        "Informe o número do pedido:",
        parse_mode='HTML'
    )
    await state.set_state(PedidoStates.aguardando_id)


@router.callback_query(F.data == "status_pedido")
async def callback_status_pedido(callback: CallbackQuery, state: FSMContext):
    """Callback para status do pedido - TELA DEDICADA."""
    await callback.answer()
    # Envia NOVA mensagem ao invés de editar
    await callback.message.answer(
        "📈 <b>CONSULTAR STATUS DO PEDIDO</b>\n\n"
        "Informe o número do pedido que deseja consultar:\n\n"
        "Exemplo: <code>123</code> ou <code>#123</code>",
        reply_markup=voltar_menu()
    )
    await state.set_state(PedidoStates.aguardando_id)


@router.message(PedidoStates.aguardando_id)
async def receber_id_pedido(message: Message, state: FSMContext):
    """Recebe ID do pedido e mostra status."""
    try:
        pedido_id = int(message.text.strip().replace("#", ""))
    except ValueError:
        await message.answer("❌ ID inválido! Digite apenas o número do pedido.")
        return

    pedido = await buscar_pedido(pedido_id)

    if not pedido:
        await message.answer(
            "❌ Pedido não encontrado.\n\n"
            "Verifique o número e tente novamente.",
            reply_markup=menu_principal()
        )
        await state.clear()
        return

    # Verificar se pertence ao usuário
    user = await buscar_usuario(message.from_user.id)
    if not user or pedido['usuario_id'] != user['id']:
        from bot.config import is_admin
        if not await is_admin(message.from_user.id):
            await message.answer("❌ Este pedido não pertence a você.", reply_markup=menu_principal())
            await state.clear()
            return

    servico = await buscar_servico_por_api_id(pedido.get('service_id_api', 0))
    pode_refill = bool(servico and servico.get('permite_refill'))
    pode_cancel = bool(servico and servico.get('permite_cancel'))

    texto = _montar_detalhes_pedido(pedido, servico)

    await message.answer(
        texto,
        parse_mode='HTML',
        reply_markup=detalhes_pedido(
            pedido['id'], pedido.get('order_id_api', ''),
            permite_refill=pode_refill, permite_cancel=pode_cancel
        )
    )
    await state.clear()
