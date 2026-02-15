"""
Sistema de Configurações - Bot SMM
===================================
Painel completo de configurações com:
- QR Code PIX (3 modos configuráveis)
- Notificações (novos usuários e vendas)
- Gateways de Pagamento
- Mensagens Personalizadas  
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import get_config, set_config
from bot.database.connection import get_db
from bot.keyboards.inline import voltar_menu
from bot.utils.helpers import safe_edit_message
from bot.utils.logger import logger

router = Router()


# ==========================================
# ESTADOS FSM
# ==========================================

class ConfigStates(StatesGroup):
    aguardando_token_mp = State()
    aguardando_mensagem_custom = State()
    aguardando_destino_notif = State()


# ==========================================
# CONFIGURAÇÃO QR CODE PIX
# ==========================================

def menu_qr_code() -> InlineKeyboardMarkup:
    """Menu de configuração do QR Code PIX."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 CONFIGURAR QR CODE PIX", callback_data="noop")],
        [InlineKeyboardButton(text="✅ Modo 1: QR Direto na Mensagem", callback_data="cfg_qr:direto")],
        [InlineKeyboardButton(text="⚡ Modo 2: Botão 'Gerar QR Code'", callback_data="cfg_qr:botao")],
        [InlineKeyboardButton(text="📋 Modo 3: Apenas Chave PIX", callback_data="cfg_qr:sem")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="adm_cat:config")],
    ])


@router.callback_query(F.data == "adm:cfg_qr_code")
async def callback_config_qr(callback: CallbackQuery):
    """Configuração do QR Code - TELA DEDICADA."""
    await callback.answer()
    
    # Busca configuração atual
    modo_atual = await get_config('qr_code_mode', 'direto')
    
    modo_desc = {
        'direto': '✅ QR Direto na Mensagem',
        'botao': '⚡ Botão "Gerar QR Code"',
        'sem': '📋 Apenas Chave PIX'
    }
    
    await callback.message.answer(
        "🎨 <b>CONFIGURAR QR CODE PIX</b>\n\n"
        f"Modo atual: <b>{modo_desc.get(modo_atual, 'Direto')}</b>\n\n"
        "<b>Escolha como o QR Code será exibido:</b>\n\n"
        "✅ <b>Modo 1: QR Direto</b>\n"
        "O QR Code é gerado automaticamente e enviado\n"
        "junto com a chave PIX na mesma mensagem.\n"
        "<i>→ Melhor experiência de usuário</i>\n\n"
        "⚡ <b>Modo 2: Botão</b>\n"
        "Aparece um botão 'Gerar QR Code'.\n"
        "O usuário clica para receber a imagem.\n"
        "<i>→ Economiza banda, usuário escolhe</i>\n\n"
        "📋 <b>Modo 3: Sem QR</b>\n"
        "Apenas a chave PIX é exibida.\n"
        "Usuário copia manualmente.\n"
        "<i>→ Mais simples, sem geração de imagens</i>",
        reply_markup=menu_qr_code()
    )


@router.callback_query(F.data.startswith("cfg_qr:"))
async def callback_setar_qr_mode(callback: CallbackQuery):
    """Define o modo de QR Code."""
    await callback.answer()
    modo = callback.data.split(":")[1]
    
    await set_config('qr_code_mode', modo)
    
    modo_nome = {
        'direto': 'QR Direto na Mensagem',
        'botao': 'Botão "Gerar QR Code"',
        'sem': 'Apenas Chave PIX'
    }
    
    await callback.message.answer(
        f"✅ <b>Configuração Salva!</b>\n\n"
        f"Modo de QR Code atualizado para:\n"
        f"<b>{modo_nome[modo]}</b>\n\n"
        f"Todos os próximos pagamentos PIX\n"
        f"usarão essa configuração.",
        reply_markup=voltar_menu()
    )
    logger.info(f"QR Code mode alterado para: {modo}")


# ==========================================
# CONFIGURAÇÃO DE NOTIFICAÇÕES
# ==========================================

def menu_notif_novos_usuarios() -> InlineKeyboardMarkup:
    """Menu config notificações novos usuários."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 NOTIFICAÇÕES: NOVOS USUÁRIOS", callback_data="noop")],
        [InlineKeyboardButton(text="✅ Ativar", callback_data="notif_new_users:ativar")],
        [InlineKeyboardButton(text="❌ Desativar", callback_data="notif_new_users:desativar")],
        [InlineKeyboardButton(text="🎯 Escolher Destino", callback_data="notif_new_users:destino")],
        [InlineKeyboardButton(text="🧪 Enviar Teste", callback_data="notif_new_users:teste")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="adm_cat:notificacoes")],
    ])


def menu_notif_vendas() -> InlineKeyboardMarkup:
    """Menu config notificações vendas."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 NOTIFICAÇÕES: VENDAS", callback_data="noop")],
        [InlineKeyboardButton(text="✅ Ativar", callback_data="notif_sales:ativar")],
        [InlineKeyboardButton(text="❌ Desativar", callback_data="notif_sales:desativar")],
        [InlineKeyboardButton(text="🎯 Escolher Destino", callback_data="notif_sales:destino")],
        [InlineKeyboardButton(text="🔘 Configurar Botões", callback_data="notif_sales:botoes")],
        [InlineKeyboardButton(text="🧪 Enviar Teste", callback_data="notif_sales:teste")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="adm_cat:notificacoes")],
    ])


@router.callback_query(F.data == "adm:notif_new_users")
async def callback_config_notif_users(callback: CallbackQuery):
    """Config notificações novos usuários - TELA DEDICADA."""
    await callback.answer()
    
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM notification_settings WHERE chave = 'new_user'"
        )
        config = await cursor.fetchone()
        
        if config:
            ativo = "✅ Ativado" if config['ativo'] else "❌ Desativado"
            destino = config.get('destino', 'Não configurado')
        else:
            ativo = "❌ Desativado"
            destino = "Não configurado"
    finally:
        await db.close()
    
    await callback.message.answer(
        "👤 <b>NOTIFICAÇÕES: NOVOS USUÁRIOS</b>\n\n"
        f"Status: <b>{ativo}</b>\n"
        f"Destino: <code>{destino}</code>\n\n"
        "<b>O que são notificações de novos usuários?</b>\n"
        "Sempre que alguém se cadastrar no bot,\n"
        "você receberá uma mensagem com os dados\n"
        "do novo usuário (nome, username, ID).\n\n"
        "<i>💡 Útil para acompanhar o crescimento da base</i>",
        reply_markup=menu_notif_novos_usuarios()
    )


@router.callback_query(F.data == "adm:notif_sales")
async def callback_config_notif_sales(callback: CallbackQuery):
    """Config notificações vendas - TELA DEDICADA."""
    await callback.answer()
    
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM notification_settings WHERE chave = 'sale'"
        )
        config = await cursor.fetchone()
        
        if config:
            ativo = "✅ Ativado" if config['ativo'] else "❌ Desativado"
            destino = config.get('destino', 'Não configurado')
        else:
            ativo = "❌ Desativado"
            destino = "Não configurado"
    finally:
        await db.close()
    
    await callback.message.answer(
        "💰 <b>NOTIFICAÇÕES: VENDAS REALIZADAS</b>\n\n"
        f"Status: <b>{ativo}</b>\n"
        f"Destino: <code>{destino}</code>\n\n"
        "<b>O que são notificações de vendas?</b>\n"
        "A cada compra realizada no bot, você\n"
        "receberá uma mensagem com detalhes:\n"
        "• Cliente\n"
        "• Serviço comprado\n"
        "• Valor\n"
        "• Link do pedido\n\n"
        "<i>💡 Acompanhe cada venda em tempo real!</i>",
        reply_markup=menu_notif_vendas()
    )


@router.callback_query(F.data.startswith("notif_new_users:"))
async def callback_toggle_notif_users(callback: CallbackQuery):
    """Ativa/desativa notificações novos usuários."""
    await callback.answer()
    acao = callback.data.split(":")[1]
    
    if acao == "ativar":
        # Lógica para ativar
        db = await get_db()
        try:
            await db.execute(
                """INSERT OR REPLACE INTO notification_settings (chave, ativo)
                   VALUES ('new_user', 1)"""
            )
            await db.commit()
        finally:
            await db.close()
        
        await callback.message.answer(
            "✅ <b>Notificações Ativadas!</b>\n\n"
            "Você será notificado sobre\n"
            "cada novo usuário cadastrado.",
            reply_markup=voltar_menu()
        )
    
    elif acao == "desativar":
        db = await get_db()
        try:
            await db.execute(
                """INSERT OR REPLACE INTO notification_settings (chave, ativo)
                   VALUES ('new_user', 0)"""
            )
            await db.commit()
        finally:
            await db.close()
        
        await callback.message.answer(
            "❌ <b>Notificações Desativadas!</b>\n\n"
            "Você não receberá mais avisos\n"
            "de novos cadastros.",
            reply_markup=voltar_menu()
        )


@router.callback_query(F.data.startswith("notif_sales:"))
async def callback_toggle_notif_sales(callback: CallbackQuery):
    """Ativa/desativa notificações vendas."""
    await callback.answer()
    acao = callback.data.split(":")[1]
    
    if acao == "ativar":
        db = await get_db()
        try:
            await db.execute(
                """INSERT OR REPLACE INTO notification_settings (chave, ativo)
                   VALUES ('sale', 1)"""
            )
            await db.commit()
        finally:
            await db.close()
        
        await callback.message.answer(
            "✅ <b>Notificações de Vendas Ativadas!</b>\n\n"
            "Você será notificado sobre\n"
            "cada compra realizada no bot.",
            reply_markup=voltar_menu()
        )
    
    elif acao == "desativar":
        db = await get_db()
        try:
            await db.execute(
                """INSERT OR REPLACE INTO notification_settings (chave, ativo)
                   VALUES ('sale', 0)"""
            )
            await db.commit()
        finally:
            await db.close()
        
        await callback.message.answer(
            "❌ <b>Notificações de Vendas Desativadas!</b>\n\n"
            "Você não receberá mais avisos\n"
            "de compras realizadas.",
            reply_markup=voltar_menu()
        )


# ==========================================
# GATEWAY MERCADOPAGO/PIX
# ==========================================

def menu_gateway_mercadopago() -> InlineKeyboardMarkup:
    """Menu MercadoPago/PIX."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 MERCADOPAGO / PIX", callback_data="noop")],
        [InlineKeyboardButton(text="🔑 Alterar Token", callback_data="cfg_mp:token")],
        [InlineKeyboardButton(text="🎨 Configurar QR Code", callback_data="adm:cfg_qr_code")],
        [InlineKeyboardButton(text="🧪 Testar Conexão", callback_data="cfg_mp:test")],
        [InlineKeyboardButton(text="✅ Ativar", callback_data="cfg_mp:ativar")],
        [InlineKeyboardButton(text="❌ Desativar", callback_data="cfg_mp:desativar")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="adm_cat:config")],
    ])


@router.callback_query(F.data == "adm:cfg_gateways")
async def callback_config_gateways(callback: CallbackQuery):
    """Menu gateways - TELA DEDICADA."""
    await callback.answer()
    
    await callback.message.answer(
        "💳 <b>GATEWAYS DE PAGAMENTO</b>\n\n"
        "Escolha qual gateway deseja configurar:\n\n"
        "🟢 <b>MercadoPago/PIX</b>\n"
        "Pagamentos via PIX com QR Code\n\n"
        "🔵 <b>HooPay</b>\n"
        "Gateway alternativo de PIX\n\n"
        "🟡 <b>Yampi</b>\n"
        "Checkout profissional",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🟢 MercadoPago/PIX", callback_data="cfg_gw:mercadopago")],
            [InlineKeyboardButton(text="🔵 HooPay", callback_data="cfg_gw:hoopay")],
            [InlineKeyboardButton(text="🔙 Voltar", callback_data="adm_cat:config")],
        ])
    )


@router.callback_query(F.data == "cfg_gw:mercadopago")
async def callback_config_mp(callback: CallbackQuery):
    """Config MercadoPago - TELA DEDICADA."""
    await callback.answer()
    
    token = await get_config('mercadopago_access_token', '')
    token_display = token[:20] + "..." if len(token) > 20 else "(não configurado)"
    
    await callback.message.answer(
        "💳 <b>MERCADOPAGO / PIX</b>\n\n"
        f"Token: <code>{token_display}</code>\n"
        f"Status: ✅ Configurado\n\n"
        "<b>Funcionalidades:</b>\n"
        "• Geração de PIX instantânea\n"
        "• QR Code configurável (3 modos)\n"
        "• Webhooks automáticos\n\n"
        "<i>💡 Configure o modo de QR Code para\n"
        "personalizar a experiência</i>",
        reply_markup=menu_gateway_mercadopago()
    )
