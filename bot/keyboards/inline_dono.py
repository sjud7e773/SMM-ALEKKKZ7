"""
Teclados Inline — Painel do Dono.
===================================
Teclados para o menu /dono (administração global).
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def menu_dono() -> InlineKeyboardMarkup:
    """Menu principal do dono."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Gerenciar Admins", callback_data="dono:admins")],
        [InlineKeyboardButton(text="📊 Estatísticas Globais", callback_data="dono:stats")],
        [
            InlineKeyboardButton(text="💰 Planos", callback_data="dono:planos"),
            InlineKeyboardButton(text="🔒 Licença", callback_data="dono:licenca"),
        ],
        [InlineKeyboardButton(text="📢 Revenda Config", callback_data="dono:revenda")],
        [
            InlineKeyboardButton(text="🛡️ Segurança", callback_data="dono:seguranca"),
            InlineKeyboardButton(text="📋 Logs", callback_data="dono:logs"),
        ],
        [InlineKeyboardButton(text="🔙 Fechar", callback_data="dono:fechar")],
    ])


def menu_admins(admins: list, pagina: int = 1, total_paginas: int = 1) -> InlineKeyboardMarkup:
    """Lista de admins com paginação."""
    botoes = []

    for adm in admins:
        status_icon = {
            'ativo': '🟢', 'bloqueado': '🔴',
            'vencido': '🟡', 'suspenso': '🟠',
            'aguardando': '⏳'
        }.get(adm['status'], '❓')
        nome = adm['nome'][:20] if adm['nome'] else f"ID:{adm['telegram_id']}"
        botoes.append([InlineKeyboardButton(
            text=f"{status_icon} {nome} • {adm['plano'].title()}",
            callback_data=f"dono:adm_detail:{adm['telegram_id']}"
        )])

    # Paginação
    if total_paginas > 1:
        nav = []
        if pagina > 1:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"dono:admins_pg:{pagina-1}"))
        nav.append(InlineKeyboardButton(text=f"{pagina}/{total_paginas}", callback_data="noop"))
        if pagina < total_paginas:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"dono:admins_pg:{pagina+1}"))
        botoes.append(nav)

    botoes.append([InlineKeyboardButton(text="➕ Adicionar Admin", callback_data="dono:add_admin")])
    botoes.append([InlineKeyboardButton(text="🔙 Menu Dono", callback_data="dono:menu")])
    return InlineKeyboardMarkup(inline_keyboard=botoes)


def detalhe_admin(admin: dict) -> InlineKeyboardMarkup:
    """Menu de detalhes do admin."""
    tid = admin['telegram_id']
    bloqueado = admin['status'] == 'bloqueado'

    botoes = [
        [InlineKeyboardButton(text="📊 Plano", callback_data=f"dono:adm_plano:{tid}")],
        [
            InlineKeyboardButton(text="🔄 Renovar", callback_data=f"dono:adm_renovar:{tid}"),
            InlineKeyboardButton(
                text="✅ Desbloquear" if bloqueado else "🔴 Bloquear",
                callback_data=f"dono:adm_block:{tid}"
            ),
        ],
        [InlineKeyboardButton(text="🗑 Remover", callback_data=f"dono:adm_remover:{tid}")],
        [InlineKeyboardButton(text="🔙 Lista Admins", callback_data="dono:admins")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=botoes)


def selecionar_plano(tid: int, planos: list) -> InlineKeyboardMarkup:
    """Teclado para selecionar plano para um admin."""
    botoes = []
    for p in planos:
        preco = f"R$ {p['preco']:.2f}".replace('.', ',')
        botoes.append([InlineKeyboardButton(
            text=f"📦 {p['nome']} — {preco}/{p['dias']}d",
            callback_data=f"dono:set_plano:{tid}:{p['slug']}"
        )])
    botoes.append([InlineKeyboardButton(text="🔙 Voltar", callback_data=f"dono:adm_detail:{tid}")])
    return InlineKeyboardMarkup(inline_keyboard=botoes)


def menu_planos_config() -> InlineKeyboardMarkup:
    """Menu de configuração de planos."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Ver Planos", callback_data="dono:ver_planos")],
        [InlineKeyboardButton(text="✏️ Editar Preços", callback_data="dono:editar_precos")],
        [InlineKeyboardButton(text="🔙 Menu Dono", callback_data="dono:menu")],
    ])


def menu_licenca() -> InlineKeyboardMarkup:
    """Menu de configuração de licença."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Ver Licença", callback_data="dono:ver_licenca")],
        [InlineKeyboardButton(text="🔙 Menu Dono", callback_data="dono:menu")],
    ])


def menu_revenda_config() -> InlineKeyboardMarkup:
    """Menu de configuração da mensagem de revenda."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Editar Mensagem", callback_data="dono:editar_msg_revenda")],
        [InlineKeyboardButton(text="📱 Editar Contato", callback_data="dono:editar_contato")],
        [InlineKeyboardButton(text="👁 Preview", callback_data="dono:preview_revenda")],
        [InlineKeyboardButton(text="🔙 Menu Dono", callback_data="dono:menu")],
    ])


def menu_seguranca() -> InlineKeyboardMarkup:
    """Menu de segurança."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Backup Agora", callback_data="dono:backup")],
        [InlineKeyboardButton(text="📋 Logs Recentes", callback_data="dono:logs")],
        [InlineKeyboardButton(text="🔄 Revalidar Hashes", callback_data="dono:revalidar")],
        [InlineKeyboardButton(text="🔙 Menu Dono", callback_data="dono:menu")],
    ])


def confirmar_acao(acao: str, tid: int = 0, texto_sim: str = "✅ Sim",
                   texto_nao: str = "❌ Não") -> InlineKeyboardMarkup:
    """Teclado de confirmação genérico."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=texto_sim, callback_data=f"dono:confirm_{acao}:{tid}"),
            InlineKeyboardButton(text=texto_nao, callback_data="dono:admins"),
        ]
    ])


def voltar_dono() -> InlineKeyboardMarkup:
    """Botão simples de voltar ao menu dono."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Menu Dono", callback_data="dono:menu")]
    ])
