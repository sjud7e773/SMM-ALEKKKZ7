"""
Handler de Saldo e Pagamento.
===============================
Adicionar saldo via PIX, escolha de gateway, verificação.
Mínimo R$ 5,00. HTML parse mode. safe_edit_message.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import uuid

from bot.database.queries import (
    buscar_usuario, criar_pagamento, buscar_gateway_padrao, listar_gateways,
    buscar_pagamento_por_referencia, atualizar_pagamento, atualizar_saldo
)
from bot.services.mercadopago import criar_pagamento_pix as mp_criar_pix, verificar_pagamento as mp_verificar
from bot.services.hoopay import criar_pagamento_pix as hp_criar_pix, verificar_pagamento as hp_verificar
from bot.keyboards.inline import (
    escolha_gateway, escolha_valor, verificar_pagamento_btn, menu_principal, voltar_menu
)
from bot.utils.helpers import formatar_moeda, escape_html, safe_edit_message
from bot.utils.logger import logger

router = Router()

# Valor mínimo de depósito
DEPOSITO_MINIMO = 5.0
DEPOSITO_MAXIMO = 10000.0


class SaldoStates(StatesGroup):
    """Estados do fluxo de saldo."""
    escolhendo_gateway = State()
    escolhendo_valor = State()
    valor_custom = State()


@router.callback_query(F.data == "add_saldo")
async def callback_add_saldo(callback: CallbackQuery, state: FSMContext):
    """Inicia fluxo de adicionar saldo."""
    await callback.answer()
    await state.clear()

    # Verificar gateways ativos
    gateways = await listar_gateways()
    ativos = [g for g in gateways if g['ativo']]

    if not ativos:
        await safe_edit_message(
            callback.message,
            "⚠️ <b>Nenhum gateway de pagamento ativo.</b>\n\n"
            "Entre em contato com o administrador para ativar\n"
            "os métodos de pagamento.",
            reply_markup=voltar_menu()
        )
        return

    if len(ativos) == 1:
        # Apenas um gateway ativo, pular seleção
        await state.update_data(gateway=ativos[0]['nome'])
        await safe_edit_message(
            callback.message,
            f"💰 <b>Adicionar Saldo</b>\n\n"
            f"💳 Via: <b>{escape_html(ativos[0]['nome'].title())}</b> (PIX)\n\n"
            f"Escolha o valor ou digite um valor personalizado:",
            reply_markup=escolha_valor()
        )
        await state.set_state(SaldoStates.escolhendo_valor)
    else:
        await safe_edit_message(
            callback.message,
            "💰 <b>Adicionar Saldo</b>\n\n"
            "Escolha o método de pagamento:",
            reply_markup=escolha_gateway()
        )
        await state.set_state(SaldoStates.escolhendo_gateway)


@router.callback_query(F.data.startswith("gw:"), SaldoStates.escolhendo_gateway)
async def callback_escolher_gateway(callback: CallbackQuery, state: FSMContext):
    """Seleciona gateway de pagamento."""
    await callback.answer()
    gateway = callback.data.split(":")[1]
    await state.update_data(gateway=gateway)

    await safe_edit_message(
        callback.message,
        f"💰 <b>Adicionar Saldo</b>\n\n"
        f"💳 Via: <b>{escape_html(gateway.title())}</b> (PIX)\n\n"
        f"Escolha o valor ou digite personalizado:",
        reply_markup=escolha_valor()
    )
    await state.set_state(SaldoStates.escolhendo_valor)


@router.callback_query(F.data.startswith("valor:"), SaldoStates.escolhendo_valor)
async def callback_escolher_valor(callback: CallbackQuery, state: FSMContext):
    """Seleciona valor predefinido ou solicita custom."""
    await callback.answer()
    valor_str = callback.data.split(":")[1]

    if valor_str == "custom":
        await safe_edit_message(
            callback.message,
            "💰 <b>Valor Personalizado</b>\n\n"
            f"Digite o valor que deseja adicionar (em reais):\n"
            f"Mínimo: <b>R$ {DEPOSITO_MINIMO:.2f}</b>\n"
            f"Exemplo: <code>25.50</code>",
            reply_markup=voltar_menu()
        )
        await state.set_state(SaldoStates.valor_custom)
        return

    valor = float(valor_str)
    await _processar_pagamento(callback, state, valor)


@router.message(SaldoStates.valor_custom)
async def receber_valor_custom(message: Message, state: FSMContext):
    """Recebe valor personalizado."""
    try:
        texto = message.text.strip().replace(",", ".")
        valor = float(texto)
        if valor < DEPOSITO_MINIMO:
            await message.answer(
                f"❌ Valor mínimo: <b>R$ {DEPOSITO_MINIMO:.2f}</b>",
                parse_mode='HTML'
            )
            return
        if valor > DEPOSITO_MAXIMO:
            await message.answer(
                f"❌ Valor máximo: <b>R$ {DEPOSITO_MAXIMO:,.2f}</b>",
                parse_mode='HTML'
            )
            return
    except ValueError:
        await message.answer(
            "❌ Valor inválido! Digite apenas números.\n"
            "Exemplo: <code>25.50</code>",
            parse_mode='HTML'
        )
        return

    data = await state.get_data()
    gateway = data.get('gateway', 'mercadopago')
    user = await buscar_usuario(message.from_user.id)

    if not user:
        await message.answer("❌ Erro ao buscar usuário.", reply_markup=menu_principal())
        await state.clear()
        return

    referencia = f"smm_{user['id']}_{uuid.uuid4().hex[:8]}"
    resultado = None

    if gateway == 'mercadopago':
        resultado = await mp_criar_pix(
            valor=valor,
            descricao=f"Recarga SMM Bot - R$ {valor:.2f}",
            referencia=referencia,
            email_pagador=f"user{user['telegram_id']}@bot.com"
        )
    elif gateway == 'hoopay':
        resultado = await hp_criar_pix(
            valor=valor,
            descricao=f"Recarga SMM Bot - R$ {valor:.2f}",
            referencia=referencia
        )

    if resultado and resultado.get('sucesso'):
        pagamento = await criar_pagamento(
            usuario_id=user['id'],
            gateway=gateway,
            valor=valor,
            referencia_externa=resultado.get('id_pagamento', referencia),
            qr_code=resultado.get('qr_code', ''),
            link_pagamento=resultado.get('link_pagamento', '')
        )

        texto_pag = (
            f"✅ <b>Pagamento PIX Gerado!</b>\n\n"
            f"💰 Valor: <b>{formatar_moeda(valor)}</b>\n\n"
        )

        if resultado.get('qr_code'):
            texto_pag += (
                f"📋 <b>Código PIX (copia e cola):</b>\n"
                f"<code>{resultado['qr_code']}</code>\n\n"
            )

        if resultado.get('link_pagamento'):
            texto_pag += f"🔗 <a href=\"{resultado['link_pagamento']}\">Pagar via link</a>\n\n"

        texto_pag += "⏰ Após o pagamento, clique no botão abaixo para verificar\nou aguarde a confirmação automática."

        await message.answer(
            texto_pag,
            parse_mode='HTML',
            reply_markup=verificar_pagamento_btn(pagamento['id']),
            disable_web_page_preview=True
        )

        logger.info(f"💳 Pagamento #{pagamento['id']} gerado: R$ {valor:.2f} via {gateway} para user {user['telegram_id']}")
    else:
        erro = resultado.get('erro', 'Erro desconhecido') if resultado else 'Gateway indisponível'
        await message.answer(
            f"❌ <b>Erro ao gerar pagamento</b>\n\n"
            f"Motivo: {escape_html(str(erro))}\n\n"
            f"Tente novamente ou use outro método.",
            parse_mode='HTML',
            reply_markup=menu_principal()
        )

    await state.clear()


async def _processar_pagamento(callback: CallbackQuery, state: FSMContext, valor: float):
    """Processa criação do pagamento PIX."""
    data = await state.get_data()
    gateway = data.get('gateway', 'mercadopago')
    user = await buscar_usuario(callback.from_user.id)

    if not user:
        await safe_edit_message(callback.message, "❌ Erro.", reply_markup=menu_principal())
        await state.clear()
        return

    referencia = f"smm_{user['id']}_{uuid.uuid4().hex[:8]}"
    resultado = None

    await safe_edit_message(callback.message, "⏳ Gerando pagamento PIX...")

    if gateway == 'mercadopago':
        resultado = await mp_criar_pix(
            valor=valor,
            descricao=f"Recarga SMM Bot - R$ {valor:.2f}",
            referencia=referencia,
            email_pagador=f"user{user['telegram_id']}@bot.com"
        )
    elif gateway == 'hoopay':
        resultado = await hp_criar_pix(
            valor=valor,
            descricao=f"Recarga SMM Bot - R$ {valor:.2f}",
            referencia=referencia
        )

    if resultado and resultado.get('sucesso'):
        pagamento = await criar_pagamento(
            usuario_id=user['id'],
            gateway=gateway,
            valor=valor,
            referencia_externa=resultado.get('id_pagamento', referencia),
            qr_code=resultado.get('qr_code', ''),
            link_pagamento=resultado.get('link_pagamento', '')
        )

        texto_pag = (
            f"✅ <b>Pagamento PIX Gerado!</b>\n\n"
            f"💰 Valor: <b>{formatar_moeda(valor)}</b>\n\n"
        )

        if resultado.get('qr_code'):
            texto_pag += (
                f"📋 <b>Código PIX (copia e cola):</b>\n"
                f"<code>{resultado['qr_code']}</code>\n\n"
            )

        if resultado.get('link_pagamento'):
            texto_pag += f"🔗 <a href=\"{resultado['link_pagamento']}\">Pagar via link</a>\n\n"

        texto_pag += "⏰ Clique abaixo para verificar o pagamento."

        await safe_edit_message(
            callback.message,
            texto_pag,
            reply_markup=verificar_pagamento_btn(pagamento['id'])
        )

        logger.info(f"💳 Pagamento #{pagamento['id']} gerado: R$ {valor:.2f} via {gateway}")
    else:
        erro = resultado.get('erro', 'Erro desconhecido') if resultado else 'Gateway indisponível'
        await safe_edit_message(
            callback.message,
            f"❌ <b>Erro ao gerar pagamento</b>\n\nMotivo: {escape_html(str(erro))}",
            reply_markup=menu_principal()
        )

    await state.clear()


@router.callback_query(F.data.startswith("verif_pag:"))
async def callback_verificar_pagamento(callback: CallbackQuery):
    """Verifica status de um pagamento."""
    await callback.answer("🔄 Verificando...")
    pagamento_id = int(callback.data.split(":")[1])

    from bot.database.connection import get_db
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM pagamentos WHERE id = ?", (pagamento_id,))
        pag = await cursor.fetchone()
        if not pag:
            await callback.answer("❌ Pagamento não encontrado.", show_alert=True)
            return
        pag = dict(pag)
    finally:
        await db.close()

    if pag['status'] == 'aprovado':
        await safe_edit_message(
            callback.message,
            f"✅ <b>Pagamento já confirmado!</b>\n\n"
            f"💰 Valor: {formatar_moeda(pag['valor'])}\n"
            f"Seu saldo já foi creditado.",
            reply_markup=menu_principal()
        )
        return

    # Verificar externamente
    ref = pag['referencia_externa']
    resultado = None

    if pag['gateway'] == 'mercadopago':
        resultado = await mp_verificar(ref)
    elif pag['gateway'] == 'hoopay':
        resultado = await hp_verificar(ref)

    if resultado and resultado.get('aprovado'):
        await atualizar_pagamento(pagamento_id, 'aprovado')

        from bot.database.queries import buscar_usuario_por_id
        user = await buscar_usuario_por_id(pag['usuario_id'])
        if user:
            await atualizar_saldo(user['telegram_id'], pag['valor'])

        await safe_edit_message(
            callback.message,
            f"✅ <b>Pagamento Confirmado!</b>\n\n"
            f"💰 Valor creditado: <b>{formatar_moeda(pag['valor'])}</b>\n\n"
            f"Saldo atualizado! Use o menu para comprar serviços.",
            reply_markup=menu_principal()
        )

        logger.info(f"✅ Pagamento #{pagamento_id} confirmado via verificação manual.")
    else:
        status = resultado.get('status', 'pendente') if resultado else 'erro'
        await safe_edit_message(
            callback.message,
            f"⏳ <b>Pagamento ainda não confirmado.</b>\n\n"
            f"💰 Valor: {formatar_moeda(pag['valor'])}\n"
            f"📊 Status: {escape_html(str(status))}\n\n"
            f"Tente novamente em alguns segundos ou aguarde\n"
            f"a confirmação automática.",
            reply_markup=verificar_pagamento_btn(pagamento_id)
        )
