"""
Handler de Compra - Organizado por Plataformas.
================================================
Fluxo: Plataforma → Categoria → Serviço → Detalhes → Link → Quantidade → Confirmação.
Detecção inteligente de plataforma, sem truncamento de nomes.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.queries import (
    listar_categorias, listar_servicos_por_categoria, buscar_servico,
    buscar_usuario, criar_pedido, atualizar_pedido_api, atualizar_saldo
)
from bot.services.pricing import calcular_preco_completo, calcular_preco_minimo
from bot.services.smm_api import criar_pedido as api_criar_pedido
from bot.services.upsell import buscar_upsell
from bot.services.platform_detector import (
    agrupar_por_plataforma, obter_emoji_plataforma, detectar_plataforma
)
from bot.config import get_config
from bot.keyboards.inline import confirmar_compra, menu_principal, voltar_menu
from bot.utils.helpers import (
    formatar_moeda, formatar_numero, validar_link,
    escape_html, safe_edit_message, paginar_lista
)
from bot.utils.logger import logger

router = Router()


class CompraStates(StatesGroup):
    """Estados do fluxo de compra."""
    aguardando_link = State()
    aguardando_quantidade = State()
    confirmando = State()


# ==========================================
# PLATAFORMAS
# ==========================================

@router.message(Command("comprar"))
async def cmd_comprar(message: Message, state: FSMContext):
    """Comando /comprar - mostra plataformas."""
    await state.clear()
    
    # Buscar todos os serviços ativos
    from bot.database.queries import listar_servicos_ativos
    servicos = await listar_servicos_ativos()
    
    if not servicos:
        await message.answer(
            "⚠️ Nenhum serviço disponível no momento.\n"
            "Os serviços precisam ser sincronizados pelo administrador.",
            reply_markup=voltar_menu()
        )
        return
    
    # Agrupar por plataforma
    plataformas = agrupar_por_plataforma(servicos)
    
    # Criar teclado de plataformas
    kb = _criar_teclado_plataformas(plataformas)
    
    await message.answer(
        "🛒 <b>Escolha uma plataforma:</b>\n\n"
        "Selecione a rede social para visualizar os serviços disponíveis.",
        parse_mode='HTML',
        reply_markup=kb
    )


@router.callback_query(F.data == "comprar")
async def callback_comprar(callback: CallbackQuery, state: FSMContext):
    """Callback para iniciar compra."""
    await callback.answer()
    await state.clear()
    
    from bot.database.queries import listar_servicos_ativos
    servicos = await listar_servicos_ativos()
    
    if not servicos:
        await safe_edit_message(
            callback.message,
            "⚠️ Nenhum serviço disponível no momento.\n"
            "Os serviços precisam ser sincronizados pelo administrador.",
            reply_markup=voltar_menu()
        )
        return
    
    plataformas = agrupar_por_plataforma(servicos)
    kb = _criar_teclado_plataformas(plataformas)
    
    await safe_edit_message(
        callback.message,
        "🛒 <b>Escolha uma plataforma:</b>\n\n"
        "Selecione a rede social para visualizar os serviços disponíveis.",
        reply_markup=kb
    )


def _criar_teclado_plataformas(plataformas: dict, pagina: int = 0) -> InlineKeyboardMarkup:
    """Cria teclado de plataformas com paginação."""
    plataformas_list = list(plataformas.keys())
    plataformas_pag, total_pags, _ = paginar_lista(plataformas_list, pagina, 8)
    
    buttons = []
    for plat in plataformas_pag:
        emoji = obter_emoji_plataforma(plat)
        qtd = len(plataformas[plat])
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {plat} ({qtd})",
                callback_data=f"platform:{plat}"
            )
        ])
    
    # Paginação
    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton(text="◀️ Anterior", callback_data=f"plat_pag:{pagina-1}"))
    if pagina < total_pags - 1:
        nav.append(InlineKeyboardButton(text="Próxima ▶️", callback_data=f"plat_pag:{pagina+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("plat_pag:"))
async def callback_plataformas_pag(callback: CallbackQuery):
    """Paginação de plataformas."""
    await callback.answer()
    pagina = int(callback.data.split(":")[1])
    
    from bot.database.queries import listar_servicos_ativos
    servicos = await listar_servicos_ativos()
    plataformas = agrupar_por_plataforma(servicos)
    kb = _criar_teclado_plataformas(plataformas, pagina)
    
    await safe_edit_message(
        callback.message,
        "🛒 <b>Escolha uma plataforma:</b>\n\n"
        "Selecione a rede social para visualizar os serviços disponíveis.",
        reply_markup=kb
    )


# ==========================================
# CATEGORIAS (dentro da plataforma)
# ==========================================

@router.callback_query(F.data.startswith("platform:"))
async def callback_selecionar_plataforma(callback: CallbackQuery, state: FSMContext):
    """Seleciona plataforma e mostra categorias."""
    await callback.answer()
    plataforma = callback.data.split(":", 1)[1]
    
    await state.update_data(plataforma=plataforma)
    
    # Buscar serviços da plataforma
    from bot.database.queries import listar_servicos_ativos
    todos_servicos = await listar_servicos_ativos()
    
    # Filtrar por plataforma
    servicos_plataforma = []
    for s in todos_servicos:
        nome = s.get('nome') or s.get('nome_custom', '')
        categoria_api = s.get('category', '')
        if detectar_plataforma(nome, categoria_api) == plataforma:
            servicos_plataforma.append(s)
    
    if not servicos_plataforma:
        await safe_edit_message(
            callback.message,
            f"⚠️ Nenhum serviço disponível para {plataforma}.",
            reply_markup=voltar_menu()
        )
        return
    
    # Agrupar por categoria
    categorias = {}
    for s in servicos_plataforma:
        cat = s.get('category', 'Outros')
        if cat not in categorias:
            categorias[cat] = []
        categorias[cat].append(s)
    
    await state.update_data(categorias=categorias, servicos_plataforma=servicos_plataforma)
    
    # Criar teclado de categorias
    kb = _criar_teclado_categorias(plataforma, categorias)
    
    emoji = obter_emoji_plataforma(plataforma)
    await safe_edit_message(
        callback.message,
        f"{emoji} <b>{plataforma}</b>\n\n"
        f"Escolha a categoria de serviço:",
        reply_markup=kb
    )


def _criar_teclado_categorias(plataforma: str, categorias: dict, pagina: int = 0) -> InlineKeyboardMarkup:
    """Cria teclado de categorias."""
    cats_list = sorted(categorias.keys())
    cats_pag, total_pags, _ = paginar_lista(cats_list, pagina, 8)
    
    buttons = []
    for cat in cats_pag:
        qtd = len(categorias[cat])
        buttons.append([
            InlineKeyboardButton(
                text=f"📂 {cat} ({qtd})",
                callback_data=f"cat:{plataforma}:{cat}"
            )
        ])
    
    # Paginação
    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"cat_pag:{plataforma}:{pagina-1}"))
    if pagina < total_pags - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"cat_pag:{plataforma}:{pagina+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton(text="🔙 Plataformas", callback_data="comprar")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("cat_pag:"))
async def callback_categorias_pag(callback: CallbackQuery, state: FSMContext):
    """Paginação de categorias."""
    await callback.answer()
    parts = callback.data.split(":")
    plataforma = parts[1]
    pagina = int(parts[2])
    
    data = await state.get_data()
    categorias = data.get('categorias', {})
    
    kb = _criar_teclado_categorias(plataforma, categorias, pagina)
    emoji = obter_emoji_plataforma(plataforma)
    
    await safe_edit_message(
        callback.message,
        f"{emoji} <b>{plataforma}</b>\n\n"
        f"Escolha a categoria de serviço:",
        reply_markup=kb
    )


# ==========================================
# SERVIÇOS (dentro da categoria)
# ==========================================

@router.callback_query(F.data.startswith("cat:"))
async def callback_selecionar_categoria(callback: CallbackQuery, state: FSMContext):
    """Seleciona categoria e mostra serviços."""
    await callback.answer()
    parts = callback.data.split(":", 2)
    plataforma = parts[1]
    categoria = parts[2]
    
    data = await state.get_data()
    categorias = data.get('categorias', {})
    servicos = categorias.get(categoria, [])
    
    if not servicos:
        await callback.answer("❌ Categoria vazia.", show_alert=True)
        return
    
    await state.update_data(categoria_atual=categoria, servicos_categoria=servicos)
    
    # Calcular preços mínimos
    margem = float(await get_config('margem_lucro', '75'))
    gateway = await _get_gateway_padrao()
    
    for s in servicos:
        markup = s.get('markup_custom')
        m = markup if markup is not None else margem
        s['preco_min'] = calcular_preco_minimo(
            s['rate'], s['min_quantidade'], m, gateway
        )
    
    kb = _criar_teclado_servicos(plataforma, categoria, servicos)
    emoji = obter_emoji_plataforma(plataforma)
    
    await safe_edit_message(
        callback.message,
        f"{emoji} <b>{plataforma}</b> → <b>{categoria}</b>\n\n"
        f"Escolha o serviço:",
        reply_markup=kb
    )


def _criar_teclado_servicos(plataforma: str, categoria: str, servicos: list, pagina: int = 0) -> InlineKeyboardMarkup:
    """Cria teclado de serviços - SEM TRUNCAR NOMES."""
    servs_pag, total_pags, _ = paginar_lista(servicos, pagina, 6)
    
    buttons = []
    for s in servs_pag:
        nome = escape_html(s.get('nome_custom') or s['nome'])
        preco_min = formatar_moeda(s.get('preco_min', 0))
        
        # NUNCA truncar nome — sempre mostrar completo
        buttons.append([
            InlineKeyboardButton(
                text=f"{nome} - A partir de {preco_min}",
                callback_data=f"srv:{s['id']}"
            )
        ])
    
    # Paginação
    nav = []
    if pagina > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"srv_pag:{plataforma}:{categoria}:{pagina-1}"))
    if pagina < total_pags - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"srv_pag:{plataforma}:{categoria}:{pagina+1}"))
    if nav:
        buttons.append(nav)
    
    buttons.append([InlineKeyboardButton(text="🔙 Categorias", callback_data=f"platform:{plataforma}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("srv_pag:"))
async def callback_servicos_pag(callback: CallbackQuery, state: FSMContext):
    """Paginação de serviços."""
    await callback.answer()
    parts = callback.data.split(":")
    plataforma = parts[1]
    categoria = parts[2]
    pagina = int(parts[3])
    
    data = await state.get_data()
    servicos = data.get('servicos_categoria', [])
    
    kb = _criar_teclado_servicos(plataforma, categoria, servicos, pagina)
    emoji = obter_emoji_plataforma(plataforma)
    
    await safe_edit_message(
        callback.message,
        f"{emoji} <b>{plataforma}</b> → <b>{categoria}</b>\n\n"
        f"Escolha o serviço:",
        reply_markup=kb
    )


# ==========================================
# DETALHE DO SERVIÇO
# ==========================================

@router.callback_query(F.data.startswith("srv:"))
async def callback_detalhe_servico(callback: CallbackQuery, state: FSMContext):
    """Mostra detalhes do serviço."""
    await callback.answer()
    servico_id = int(callback.data.split(":")[1])
    servico = await buscar_servico(servico_id)
    
    if not servico or not servico['ativo']:
        await callback.answer("❌ Serviço indisponível.", show_alert=True)
        return
    
    await state.update_data(servico_id=servico_id, servico=servico)
    
    margem = float(await get_config('margem_lucro', '75'))
    markup = servico.get('markup_custom')
    m = markup if markup is not None else margem
    gateway = await _get_gateway_padrao()
    preco_min = calcular_preco_minimo(servico['rate'], servico['min_quantidade'], m, gateway)
    
    nome = escape_html(servico.get('nome_custom') or servico['nome'])
    descricao = servico.get('descricao', '') or 'Sem descrição'
    
    refill = '🟢 Sim' if servico.get('permite_refill') else '🔴 Não'
    cancel = '🟢 Sim' if servico.get('permite_cancel') else '🔴 Não'
    
    texto = (
        f"🔹 <b>{nome}</b>\n\n"
        f"📝 {escape_html(descricao[:300])}\n\n"
        f"📊 Mín: <b>{formatar_numero(servico['min_quantidade'])}</b>\n"
        f"📊 Máx: <b>{formatar_numero(servico['max_quantidade'])}</b>\n"
        f"💰 A partir de: <b>{formatar_moeda(preco_min)}</b>\n\n"
        f"🔁 Refill: {refill}\n"
        f"❌ Cancel: {cancel}"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Comprar este serviço", callback_data=f"buy:{servico_id}")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="comprar")]
    ])
    
    await safe_edit_message(callback.message, texto, reply_markup=kb)


@router.callback_query(F.data.startswith("buy:"))
async def callback_comprar_servico(callback: CallbackQuery, state: FSMContext):
    """Inicia compra: pede o link."""
    await callback.answer()
    servico_id = int(callback.data.split(":")[1])
    servico = await buscar_servico(servico_id)
    
    if not servico or not servico['ativo']:
        await callback.answer("❌ Serviço indisponível.", show_alert=True)
        return
    
    await state.update_data(servico_id=servico_id, servico=servico)
    
    nome = escape_html(servico.get('nome_custom') or servico['nome'])
    await safe_edit_message(
        callback.message,
        f"🛒 <b>Comprar: {nome}</b>\n\n"
        f"🔗 <b>Envie o link do perfil/post:</b>",
        reply_markup=voltar_menu()
    )
    await state.set_state(CompraStates.aguardando_link)


# ==========================================
# FLUXO: LINK → QUANTIDADE → CONFIRMAÇÃO → API
# ==========================================

@router.message(CompraStates.aguardando_link)
async def receber_link(message: Message, state: FSMContext):
    """Recebe o link do pedido."""
    link = message.text.strip()
    
    if not validar_link(link):
        await message.answer(
            "❌ <b>Link inválido!</b>\n\n"
            "O link deve começar com <code>http://</code> ou <code>https://</code>.\n"
            "Exemplo: <code>https://instagram.com/seuperfil</code>\n\n"
            "🔗 Envie o link correto:",
            parse_mode='HTML'
        )
        return
    
    await state.update_data(link=link)
    data = await state.get_data()
    servico = data['servico']
    
    await message.answer(
        f"🔗 Link: <code>{escape_html(link)}</code>\n\n"
        f"📊 <b>Informe a quantidade:</b>\n\n"
        f"⚠️ Mínimo: <b>{formatar_numero(servico['min_quantidade'])}</b>\n"
        f"⚠️ Máximo: <b>{formatar_numero(servico['max_quantidade'])}</b>",
        parse_mode='HTML'
    )
    await state.set_state(CompraStates.aguardando_quantidade)


@router.message(CompraStates.aguardando_quantidade)
async def receber_quantidade(message: Message, state: FSMContext):
    """Recebe a quantidade e mostra resumo."""
    try:
        quantidade = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Quantidade inválida! Digite apenas números.")
        return
    
    data = await state.get_data()
    servico = data['servico']
    
    if quantidade < servico['min_quantidade']:
        await message.answer(
            f"❌ <b>Quantidade abaixo do mínimo!</b>\n\n"
            f"Mínimo: <b>{formatar_numero(servico['min_quantidade'])}</b>\n\n"
            f"📊 Informe uma quantidade válida:",
            parse_mode='HTML'
        )
        return
    
    if quantidade > servico['max_quantidade']:
        await message.answer(
            f"❌ <b>Quantidade acima do máximo!</b>\n\n"
            f"Máximo: <b>{formatar_numero(servico['max_quantidade'])}</b>\n\n"
            f"📊 Informe uma quantidade válida:",
            parse_mode='HTML'
        )
        return
    
    gateway = await _get_gateway_padrao()
    margem = float(await get_config('margem_lucro', '75'))
    markup = servico.get('markup_custom')
    m = markup if markup is not None else margem
    
    preco = await calcular_preco_completo(
        rate=servico['rate'],
        quantidade=quantidade,
        gateway=gateway,
        margem_custom=m
    )
    
    await state.update_data(quantidade=quantidade, preco=preco, gateway=gateway)
    
    user = await buscar_usuario(message.from_user.id)
    saldo_atual = user['saldo'] if user else 0
    
    nome = escape_html(servico.get('nome_custom') or servico['nome'])
    link = data['link']
    
    saldo_str = formatar_moeda(saldo_atual)
    preco_final_str = formatar_moeda(preco['preco_final'])
    saldo_suficiente = saldo_atual >= preco['preco_final']
    
    texto = (
        f"📋 <b>RESUMO DO PEDIDO</b>\n\n"
        f"🔹 <b>Serviço:</b> {nome}\n"
        f"🔗 <b>Link:</b> <code>{escape_html(link[:50])}</code>\n"
        f"📊 <b>Quantidade:</b> {formatar_numero(quantidade)}\n\n"
        f"💰 <b>Preço final:</b> {preco_final_str}\n\n"
        f"📊 <b>Seu saldo:</b> {saldo_str}\n"
    )
    
    if not saldo_suficiente:
        falta = preco['preco_final'] - saldo_atual
        await message.answer(
            f"❌ <b>Saldo insuficiente!</b>\n\n"
            f"💰 <b>Seu saldo:</b> {formatar_moeda(saldo_atual)}\n"
            f"💳 <b>Valor necessário:</b> {formatar_moeda(preco['preco_final'])}\n"
            f"📊 <b>Faltam:</b> {formatar_moeda(falta)}\n\n"
            f"Adicione saldo para continuar com esta compra.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Adicionar Saldo", callback_data="saldo")],
                [InlineKeyboardButton(text="🔙 Voltar ao Menu", callback_data="menu")]
            ])
        )
        await state.clear()
        return
    
    texto += f"\n✅ Saldo suficiente!"
    await message.answer(texto, parse_mode='HTML', reply_markup=confirmar_compra(preco))
    await state.set_state(CompraStates.confirmando)


@router.callback_query(F.data == "confirmar_compra", CompraStates.confirmando)
async def callback_confirmar_compra(callback: CallbackQuery, state: FSMContext):
    """Confirma a compra, desconta saldo e envia para API."""
    await callback.answer("⏳ Processando...")
    data = await state.get_data()
    
    servico = data['servico']
    link = data['link']
    quantidade = data['quantidade']
    preco = data['preco']
    gateway = data['gateway']
    
    user = await buscar_usuario(callback.from_user.id)
    if not user or user['saldo'] < preco['preco_final']:
        await safe_edit_message(
            callback.message,
            "❌ <b>Saldo insuficiente!</b>\n"
            "Seu saldo mudou durante o processo.\n"
            "Adicione mais saldo e tente novamente.",
            reply_markup=menu_principal()
        )
        await state.clear()
        return
    
    # Descontar saldo
    novo_saldo = await atualizar_saldo(callback.from_user.id, preco['preco_final'], 'subtrair')
    
    # Criar pedido no banco
    pedido = await criar_pedido(
        usuario_id=user['id'],
        servico_id=servico['id'],
        service_id_api=servico['service_id_api'],
        link=link,
        quantidade=quantidade,
        preco_custo=preco['custo_base'],
        preco_com_lucro=preco['preco_com_lucro'],
        preco_final=preco['preco_final'],
        gateway=gateway
    )
    
    # Enviar para API SMM
    resultado_api = await api_criar_pedido(
        service_id=servico['service_id_api'],
        link=link,
        quantity=quantidade
    )
    
    nome = escape_html(servico.get('nome_custom') or servico['nome'])
    
    if 'order' in resultado_api:
        order_id = str(resultado_api['order'])
        await atualizar_pedido_api(pedido['id'], order_id, 'enviado')
        
        await safe_edit_message(
            callback.message,
            f"✅ <b>PEDIDO CRIADO COM SUCESSO!</b>\n\n"
            f"📋 <b>Pedido:</b> #{pedido['id']}\n"
            f"📋 <b>ID API:</b> #{order_id}\n"
            f"🔹 <b>Serviço:</b> {nome}\n"
            f"🔗 <b>Link:</b> <code>{escape_html(link[:40])}</code>\n"
            f"📊 <b>Quantidade:</b> {formatar_numero(quantidade)}\n"
            f"💰 <b>Valor:</b> {formatar_moeda(preco['preco_final'])}\n"
            f"💳 <b>Novo saldo:</b> {formatar_moeda(novo_saldo)}\n\n"
            f"📈 O status será atualizado automaticamente.\n"
            f"Use /pedidos para acompanhar.",
            reply_markup=voltar_menu()
        )
        
        # CRÍTICO: Disparar notificação de venda (se configurado)
        try:
            from bot.services.notifications import enviar_notificacao_venda
            bot = callback.bot
            user_username = callback.from_user.username or ''
            await enviar_notificacao_venda(
                bot=bot,
                user_id=callback.from_user.id,
                username=user_username,
                servico_nome=servico.get('nome_custom') or servico['nome'],
                valor=preco['preco_final']
            )
        except Exception:
            pass  # Não quebrar fluxo se notificação falhar
        
        # Upsell
        upsell_ativo = await get_config('upsell_ativo', '1')
        if upsell_ativo == '1':
            upsell = await buscar_upsell(servico['id'], servico.get('categoria', ''))
            if upsell:
                try:
                    dest = upsell['servico_destino']
                    dest_nome = escape_html(dest.get('nome_custom') or dest['nome'])
                    desc = upsell['desconto_pct']
                    
                    from bot.keyboards.inline import upsell_teclado
                    await callback.message.answer(
                        f"🎁 <b>{escape_html(upsell['mensagem'])}</b>\n\n"
                        f"🔹 {dest_nome}\n"
                        f"💰 Com <b>{desc}%</b> de desconto!\n\n"
                        f"Aproveite esta oferta especial:",
                        parse_mode='HTML',
                        reply_markup=upsell_teclado(upsell['regra_id'], dest['id'])
                    )
                except Exception:
                    pass
    else:
        # Erro na API - devolver saldo
        await atualizar_saldo(callback.from_user.id, preco['preco_final'], 'adicionar')
        erro = resultado_api.get('error', 'Erro desconhecido')
        await atualizar_pedido_api(pedido['id'], '', 'erro')
        
        await safe_edit_message(
            callback.message,
            f"❌ <b>ERRO AO CRIAR PEDIDO</b>\n\n"
            f"O pedido não pôde ser enviado para o painel.\n"
            f"Seu saldo foi devolvido.\n\n"
            f"📋 Erro: {escape_html(str(erro))}\n\n"
            f"Tente novamente ou entre em contato com o suporte.",
            reply_markup=menu_principal()
        )
    
    await state.clear()


@router.callback_query(F.data == "cancelar_compra")
async def callback_cancelar_compra(callback: CallbackQuery, state: FSMContext):
    """Cancela o fluxo de compra."""
    await callback.answer("❌ Compra cancelada.")
    await state.clear()
    await safe_edit_message(
        callback.message,
        "❌ Compra cancelada.\n\nVoltando ao menu principal...",
        reply_markup=menu_principal()
    )


async def _get_gateway_padrao() -> str:
    """Retorna o nome do gateway padrão ativo."""
    from bot.database.queries import buscar_gateway_padrao
    gw = await buscar_gateway_padrao()
    return gw['nome'] if gw else 'mercadopago'
