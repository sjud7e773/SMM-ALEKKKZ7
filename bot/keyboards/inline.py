"""
Teclados Inline do Bot.
========================
Todos os teclados organizados por funcionalidade.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.helpers import formatar_moeda, truncar_texto, paginar_lista


# ==========================================
# MENU PRINCIPAL
# ==========================================

def menu_principal() -> InlineKeyboardMarkup:
    """Menu principal do bot."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Comprar Serviço", callback_data="comprar")],
        [InlineKeyboardButton(text="💰 Adicionar Saldo", callback_data="add_saldo"),
         InlineKeyboardButton(text="💳 Meu Saldo", callback_data="ver_saldo")],
        [InlineKeyboardButton(text="📊 Meus Pedidos", callback_data="meus_pedidos"),
         InlineKeyboardButton(text="📈 Status do Pedido", callback_data="status_pedido")],
        [InlineKeyboardButton(text="🎁 Promoções", callback_data="promocoes"),
         InlineKeyboardButton(text="🎟️ Cupom", callback_data="usar_cupom")],
        [InlineKeyboardButton(text="👥 Indicar Amigo", callback_data="indicar")],
        [InlineKeyboardButton(text="📞 Suporte", callback_data="suporte"),
         InlineKeyboardButton(text="📜 Termos", callback_data="termos")],
        [InlineKeyboardButton(text="🚀 Ter Meu Próprio Bot", callback_data="revenda")],
    ])


# ==========================================
# COMPRA
# ==========================================

def categorias(cats: list, pagina: int = 1) -> InlineKeyboardMarkup:
    """Lista de categorias com paginação."""
    cats_pagina, total_paginas, pagina_atual = paginar_lista(cats, pagina, 8)
    buttons = []
    for i, cat in enumerate(cats_pagina):
        nome = truncar_texto(cat, 40)
        buttons.append([InlineKeyboardButton(
            text=f"📂 {nome}",
            callback_data=f"cat:{pagina_atual}:{i}"
        )])

    # Navegação
    nav = []
    if pagina_atual > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"cats_pag:{pagina_atual - 1}"))
    if pagina_atual < total_paginas:
        nav.append(InlineKeyboardButton(text="Próxima ➡️", callback_data=f"cats_pag:{pagina_atual + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def servicos_lista(servicos: list, pagina: int = 1, gateway: str = 'mercadopago') -> InlineKeyboardMarkup:
    """Lista de serviços de uma categoria com paginação."""
    servs_pagina, total_paginas, pagina_atual = paginar_lista(servicos, pagina, 6)
    buttons = []
    for s in servs_pagina:
        nome = truncar_texto(s.get('nome_custom') or s['nome'], 35)
        preco_min = formatar_moeda(s.get('preco_min', 0))
        buttons.append([InlineKeyboardButton(
            text=f"🔹 {nome}",
            callback_data=f"srv:{s['id']}"
        )])

    # Navegação
    nav = []
    if pagina_atual > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Anterior", callback_data=f"srvs_pag:{pagina_atual - 1}"))
    if pagina_atual < total_paginas:
        nav.append(InlineKeyboardButton(text="Próxima ➡️", callback_data=f"srvs_pag:{pagina_atual + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 Categorias", callback_data="comprar")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirmar_compra(pedido_info: dict) -> InlineKeyboardMarkup:
    """Confirmação de compra."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirmar Compra", callback_data=f"confirmar_compra")],
        [InlineKeyboardButton(text="❌ Cancelar", callback_data="cancelar_compra")],
    ])


def upsell_teclado(regra_id: int, servico_id: int) -> InlineKeyboardMarkup:
    """Teclado de oferta upsell."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Aproveitar Oferta!", callback_data=f"upsell:{regra_id}:{servico_id}")],
        [InlineKeyboardButton(text="⏭️ Não, obrigado", callback_data="menu")],
    ])


# ==========================================
# SALDO E PAGAMENTO
# ==========================================

def escolha_gateway() -> InlineKeyboardMarkup:
    """Escolha de gateway de pagamento."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Mercado Pago (PIX)", callback_data="gw:mercadopago")],
        [InlineKeyboardButton(text="🔵 Hoopay (PIX)", callback_data="gw:hoopay")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="menu")],
    ])


def escolha_valor() -> InlineKeyboardMarkup:
    """Valores predefinidos para recarga."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="R$ 10,00", callback_data="valor:10"),
         InlineKeyboardButton(text="R$ 25,00", callback_data="valor:25")],
        [InlineKeyboardButton(text="R$ 50,00", callback_data="valor:50"),
         InlineKeyboardButton(text="R$ 100,00", callback_data="valor:100")],
        [InlineKeyboardButton(text="R$ 200,00", callback_data="valor:200"),
         InlineKeyboardButton(text="R$ 500,00", callback_data="valor:500")],
        [InlineKeyboardButton(text="💬 Outro Valor", callback_data="valor:custom")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="menu")],
    ])


def verificar_pagamento_btn(pagamento_id: int) -> InlineKeyboardMarkup:
    """Botão para verificar pagamento."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Verificar Pagamento", callback_data=f"verif_pag:{pagamento_id}")],
        [InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")],
    ])


# ==========================================
# PEDIDOS
# ==========================================

def lista_pedidos(pedidos: list, pagina: int = 1) -> InlineKeyboardMarkup:
    """Lista de pedidos do usuário."""
    peds_pagina, total_paginas, pagina_atual = paginar_lista(pedidos, pagina, 5)
    buttons = []
    for p in peds_pagina:
        from bot.utils.helpers import status_emoji
        emoji = status_emoji(p.get('status', ''))
        nome = truncar_texto(p.get('servico_nome', 'Serviço'), 25)
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} #{p['id']} - {nome}",
            callback_data=f"ped:{p['id']}"
        )])

    nav = []
    if pagina_atual > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"peds_pag:{pagina_atual - 1}"))
    if pagina_atual < total_paginas:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"peds_pag:{pagina_atual + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def detalhes_pedido(pedido_id: int, order_id_api: str = '',
                    permite_refill: bool = True, permite_cancel: bool = True) -> InlineKeyboardMarkup:
    """Detalhes de um pedido com ações.
    Mostra botões de refill/cancel apenas quando o serviço suporta."""
    buttons = [
        [InlineKeyboardButton(text="🔄 Atualizar Status", callback_data=f"refresh_ped:{pedido_id}")],
    ]
    if order_id_api:
        acoes = []
        if permite_refill:
            acoes.append(InlineKeyboardButton(text="🔁 Refill", callback_data=f"refill:{pedido_id}"))
        if permite_cancel:
            acoes.append(InlineKeyboardButton(text="❌ Cancelar", callback_data=f"cancel_ped:{pedido_id}"))
        if acoes:
            buttons.append(acoes)
    buttons.append([InlineKeyboardButton(text="🔙 Meus Pedidos", callback_data="meus_pedidos")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==========================================
# ADMIN
# ==========================================

def admin_principal() -> InlineKeyboardMarkup:
    """Menu principal do admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Estatísticas", callback_data="adm:stats")],
        [InlineKeyboardButton(text="💳 Gateways", callback_data="adm:gateways"),
         InlineKeyboardButton(text="⚙️ Configurações", callback_data="adm:config")],
        [InlineKeyboardButton(text="📦 Serviços", callback_data="adm:servicos"),
         InlineKeyboardButton(text="👥 Usuários", callback_data="adm:usuarios")],
        [InlineKeyboardButton(text="💰 Financeiro", callback_data="adm:financeiro"),
         InlineKeyboardButton(text="🎁 Upsell", callback_data="adm:upsell")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="adm:broadcast"),
         InlineKeyboardButton(text="🎟️ Cupons", callback_data="adm:cupons")],
        [InlineKeyboardButton(text="🛠 Sistema", callback_data="adm:sistema")],
        [InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")],
    ])


def admin_gateways() -> InlineKeyboardMarkup:
    """Submenu de gateways do admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Mercado Pago", callback_data="adm:gw:mercadopago")],
        [InlineKeyboardButton(text="🔵 Hoopay", callback_data="adm:gw:hoopay")],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])


def admin_gateway_opcoes(gw_nome: str) -> InlineKeyboardMarkup:
    """Opções de um gateway específico."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Configurar Credenciais", callback_data=f"adm:gw_cred:{gw_nome}")],
        [InlineKeyboardButton(text="💸 Editar Taxas", callback_data=f"adm:gw_taxa:{gw_nome}")],
        [InlineKeyboardButton(text="✅ Ativar/Desativar", callback_data=f"adm:gw_toggle:{gw_nome}")],
        [InlineKeyboardButton(text="🌟 Definir como Padrão", callback_data=f"adm:gw_padrao:{gw_nome}")],
        [InlineKeyboardButton(text="🧪 Testar Conexão", callback_data=f"adm:gw_test:{gw_nome}")],
        [InlineKeyboardButton(text="🔙 Gateways", callback_data="adm:gateways")],
    ])


def admin_config() -> InlineKeyboardMarkup:
    """Submenu de configurações do admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Margem de Lucro", callback_data="adm:cfg:margem")],
        [InlineKeyboardButton(text="🤖 Token do Bot", callback_data="adm:cfg:bot_token")],
        [InlineKeyboardButton(text="🔑 API Key SMM", callback_data="adm:cfg:api_key")],
        [InlineKeyboardButton(text="🌐 URL da API", callback_data="adm:cfg:api_url")],
        [InlineKeyboardButton(text="👤 Admin ID", callback_data="adm:cfg:admin_id")],
        [InlineKeyboardButton(text="💬 Mensagem Inicial", callback_data="adm:cfg:msg_inicio")],
        [InlineKeyboardButton(text="🎁 Comissão Indicação", callback_data="adm:cfg:comissao")],
        [InlineKeyboardButton(text="⏰ Intervalo Sync (min)", callback_data="adm:cfg:sync_int")],
        [InlineKeyboardButton(text="⏰ Check Status (min)", callback_data="adm:cfg:status_int")],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])


def admin_servicos() -> InlineKeyboardMarkup:
    """Submenu de serviços do admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Sincronizar Serviços", callback_data="adm:srv_sync")],
        [InlineKeyboardButton(text="📋 Ver Serviços", callback_data="adm:srv_list")],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])


def admin_sistema() -> InlineKeyboardMarkup:
    """Submenu de sistema do admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Backup Banco", callback_data="adm:backup")],
        [InlineKeyboardButton(text="📋 Ver Logs", callback_data="adm:logs")],
        [InlineKeyboardButton(text="💰 Saldo API", callback_data="adm:saldo_api")],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])


def admin_financeiro() -> InlineKeyboardMarkup:
    """Submenu financeiro do admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Lucro Hoje", callback_data="adm:fin:1")],
        [InlineKeyboardButton(text="📊 Lucro 7 dias", callback_data="adm:fin:7")],
        [InlineKeyboardButton(text="📊 Lucro 30 dias", callback_data="adm:fin:30")],
        [InlineKeyboardButton(text="📊 Lucro Total", callback_data="adm:fin:9999")],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])


def admin_usuarios_opcoes(telegram_id: int) -> InlineKeyboardMarkup:
    """Opções para um usuário específico (admin)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Ajustar Saldo", callback_data=f"adm:usr_saldo:{telegram_id}")],
        [InlineKeyboardButton(text="🚫 Banir/Desbanir", callback_data=f"adm:usr_ban:{telegram_id}")],
        [InlineKeyboardButton(text="📋 Ver Pedidos", callback_data=f"adm:usr_pedidos:{telegram_id}")],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])


def voltar_admin() -> InlineKeyboardMarkup:
    """Botão voltar para admin."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])


def voltar_menu() -> InlineKeyboardMarkup:
    """Botão voltar para menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")],
    ])


# ==========================================
# SUPORTE
# ==========================================

def suporte_teclado() -> InlineKeyboardMarkup:
    """Teclado de suporte."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Enviar Mensagem", callback_data="sup:msg")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="sup:faq")],
        [InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")],
    ])


# ==========================================
# SETUP
# ==========================================

def setup_confirmar(telegram_id: int) -> InlineKeyboardMarkup:
    """Confirmação de setup."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Sim, quero ser admin!", callback_data=f"setup_confirm:{telegram_id}")],
        [InlineKeyboardButton(text="❌ Cancelar", callback_data="menu")],
    ])
