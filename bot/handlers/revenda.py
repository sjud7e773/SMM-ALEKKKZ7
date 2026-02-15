"""
Handler de Revenda / Ter Meu Próprio Bot.
============================================
Exibe @dono automaticamente, botões de contato, planos SaaS disponíveis.
Sistema completo de revenda/planos.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.database.connection import get_db
from bot.database.queries_owner import buscar_owner
from bot.utils.helpers import escape_html, formatar_moeda, safe_edit_message
from bot.keyboards.inline import voltar_menu

router = Router()


@router.callback_query(F.data == "revenda")
async def callback_revenda(callback: CallbackQuery):
    """Mostra área de revenda com @ do dono e botões de contato."""
    await callback.answer()
    
    # Buscar dados do dono
    owner = await buscar_owner()
    if not owner:
        await safe_edit_message(
            callback.message,
            "⚠️ Sistema não configurado.\nEntre em contato com o administrador.",
            reply_markup=voltar_menu()
        )
        return
    
    # Username do dono
    owner_username = owner.get('username', '')
    arroba_contato = owner.get('arroba_contato', '')
    
    # Priorizar arroba_contato se configurado, senão usar username
    arroba_display = arroba_contato if arroba_contato else owner_username
    
    # Buscar planos ativos
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM saas_plans WHERE ativo = 1 ORDER BY preco ASC"
        )
        planos = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
    
    # Montar texto
    texto = (
        "🚀 <b>TER MEU PRÓPRIO BOT</b>\n\n"
        "Tenha seu próprio bot de vendas SMM automatizado!\n\n"
    )
    
    if arroba_display:
        texto += f"👤 <b>Contato:</b> @{arroba_display}\n\n"
    
    if planos:
        texto += "💎 <b>Planos Disponíveis:</b>\n\n"
        for plano in planos[:5]:  # Máximo 5 planos no resumo
            nome = escape_html(plano['nome'])
            preco = formatar_moeda(plano['preco'])
            dias = plano['duracao_dias']
            texto += f"• <b>{nome}</b> - {preco} ({dias} dias)\n"
    
    # Botões
    buttons = []
    
    if arroba_display:
        buttons.append([InlineKeyboardButton(
            text="💬 Falar com o Dono",
            url=f"https://t.me/{arroba_display.replace('@', '')}"
        )])
    
    buttons.append([InlineKeyboardButton(text="📩 Abrir Ticket", callback_data="suporte")])
    
    if planos:
        buttons.append([InlineKeyboardButton(text="🛒 Ver Planos", callback_data="ver_planos")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await safe_edit_message(callback.message, texto, reply_markup=kb)


@router.callback_query(F.data == "ver_planos")
async def callback_ver_planos(callback: CallbackQuery):
    """Mostra lista completa de planos SaaS."""
    await callback.answer()
    
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM saas_plans WHERE ativo = 1 ORDER BY preco ASC"
        )
        planos = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
    
    if not planos:
        await safe_edit_message(
            callback.message,
            "⚠️ Nenhum plano disponível no momento.\nEntre em contato com o dono.",
            reply_markup=voltar_menu()
        )
        return
    
    texto = "💎 <b>PLANOS DISPONÍVEIS</b>\n\n"
    
    buttons = []
    for plano in planos:
        nome = escape_html(plano['nome'])
        descricao = plano.get('descricao', '')
        preco = formatar_moeda(plano['preco'])
        dias = plano['duracao_dias']
        features = plano.get('features', '')
        
        texto += f"📦 <b>{nome}</b>\n"
        if descricao:
            texto += f"{escape_html(descricao[:100])}\n"
        texto += f"💰 {preco} • ⏱️ {dias} dias\n"
        if features:
            texto += f"✨ {escape_html(features[:80])}\n"
        texto += "\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"📦 {nome} - {preco}",
            callback_data=f"plano:{plano['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="🔙 Voltar", callback_data="revenda")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_edit_message(callback.message, texto, reply_markup=kb)


@router.callback_query(F.data.startswith("plano:"))
async def callback_detalhes_plano(callback: CallbackQuery):
    """Mostra detalhes de um plano e opção de compra."""
    await callback.answer()
    plano_id = int(callback.data.split(":")[1])
    
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM saas_plans WHERE id = ?", (plano_id,))
        plano = await cursor.fetchone()
        plano = dict(plano) if plano else None
    finally:
        await db.close()
    
    if not plano or not plano['ativo']:
        await callback.answer("❌ Plano não disponível.", show_alert=True)
        return
    
    nome = escape_html(plano['nome'])
    descricao = plano.get('descricao', 'Sem descrição')
    preco = formatar_moeda(plano['preco'])
    dias = plano['duracao_dias']
    features = plano.get('features', '')
    
    texto = (
        f"💎 <b>{nome}</b>\n\n"
        f"📝 {escape_html(descricao)}\n\n"
        f"💰 <b>Preço:</b> {preco}\n"
        f"⏱️ <b>Duração:</b> {dias} dias\n\n"
    )
    
    if features:
        texto += f"✨ <b>Recursos:</b>\n{escape_html(features)}\n\n"
    
    texto += (
        "Para adquirir este plano, entre em contato com o dono\n"
        "ou abra um ticket de suporte."
    )
    
    buttons = [
        [InlineKeyboardButton(text="💬 Falar com o Dono", callback_data="revenda")],
        [InlineKeyboardButton(text="📩 Abrir Ticket", callback_data="suporte")],
        [InlineKeyboardButton(text="🔙 Ver Planos", callback_data="ver_planos")]
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_edit_message(callback.message, texto, reply_markup=kb)
