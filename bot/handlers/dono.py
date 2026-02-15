"""
Handler do Painel do Dono (/dono).
=====================================
Comando oculto — gestão global do sistema SaaS.
Funcionalidades:
- Gerenciar admins (add/remove/block/planos)
- Estatísticas globais
- Configuração de licença
- Configuração de mensagem de revenda
- Segurança (backup, logs, hashes)
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.config import is_owner, gerar_hash_seguranca
from bot.database.queries_owner import (
    buscar_owner, atualizar_owner,
    criar_admin, buscar_admin_por_telegram_id, listar_admins,
    atualizar_admin, remover_admin, bloquear_admin, desbloquear_admin,
    definir_plano_admin, contar_admins, listar_planos,
    obter_estatisticas_globais
)
from bot.database.queries import registrar_log, buscar_logs
from bot.database.connection import fazer_backup
from bot.keyboards.inline_dono import (
    menu_dono, menu_admins, detalhe_admin, selecionar_plano,
    menu_planos_config, menu_licenca, menu_revenda_config,
    menu_seguranca, confirmar_acao, voltar_dono
)
from bot.utils.helpers import (
    formatar_moeda, formatar_numero, formatar_data,
    safe_edit_message, escape_html, paginar_lista
)
from bot.utils.logger import logger

router = Router()


# ==========================================
# STATES
# ==========================================

class DonoStates(StatesGroup):
    add_admin_id = State()
    add_admin_plano = State()
    editar_msg_revenda = State()
    editar_contato = State()
    editar_preco_plano = State()


# ==========================================
# COMANDO /dono
# ==========================================

@router.message(Command("dono"))
async def cmd_dono(message: Message):
    """Painel oculto do dono."""
    if not await is_owner(message.from_user.id):
        return  # Silenciosamente ignora

    owner = await buscar_owner()
    stats = await contar_admins()

    await message.answer(
        "👑 <b>PAINEL DO DONO</b>\n\n"
        f"📊 <b>Resumo rápido:</b>\n"
        f"👥 Admins: <b>{stats['total']}</b> "
        f"(🟢 {stats['ativos']} | 🔴 {stats['bloqueados']} | 🟡 {stats['vencidos']})\n"
        f"🔒 Licença: <b>{owner.get('license_type', 'PROTEGIDA')}</b>\n"
        f"📡 Instalação: <code>{owner.get('installation_id', 'N/A')[:8]}...</code>\n\n"
        "Escolha uma opção:",
        parse_mode='HTML',
        reply_markup=menu_dono()
    )


@router.callback_query(F.data == "dono:menu")
async def callback_menu_dono(callback: CallbackQuery, state: FSMContext):
    """Volta ao menu do dono."""
    if not await is_owner(callback.from_user.id):
        return
    await state.clear()
    await callback.answer()

    owner = await buscar_owner()
    stats = await contar_admins()

    await safe_edit_message(
        callback.message,
        "👑 <b>PAINEL DO DONO</b>\n\n"
        f"📊 <b>Resumo rápido:</b>\n"
        f"👥 Admins: <b>{stats['total']}</b> "
        f"(🟢 {stats['ativos']} | 🔴 {stats['bloqueados']} | 🟡 {stats['vencidos']})\n"
        f"🔒 Licença: <b>{owner.get('license_type', 'PROTEGIDA')}</b>\n\n"
        "Escolha uma opção:",
        reply_markup=menu_dono()
    )


@router.callback_query(F.data == "dono:fechar")
async def callback_fechar(callback: CallbackQuery, state: FSMContext):
    """Fecha o menu do dono."""
    if not await is_owner(callback.from_user.id):
        return
    await state.clear()
    await callback.answer()
    await callback.message.delete()


# ==========================================
# GERENCIAR ADMINS
# ==========================================

@router.callback_query(F.data == "dono:admins")
async def callback_admins(callback: CallbackQuery, state: FSMContext):
    """Lista de admins."""
    if not await is_owner(callback.from_user.id):
        return
    await state.clear()
    await callback.answer()

    admins = await listar_admins()
    itens, total_pgs, pg = paginar_lista(admins, 1, 8)

    if not admins:
        texto = (
            "👥 <b>GERENCIAR ADMINS</b>\n\n"
            "Nenhum admin cadastrado.\n"
            "Clique em <b>Adicionar Admin</b> para começar."
        )
    else:
        texto = (
            f"👥 <b>GERENCIAR ADMINS</b>\n\n"
            f"📊 Total: <b>{len(admins)}</b>\n\n"
            "Selecione um admin para gerenciar:"
        )

    await safe_edit_message(
        callback.message, texto,
        reply_markup=menu_admins(itens, pg, total_pgs)
    )


@router.callback_query(F.data.startswith("dono:admins_pg:"))
async def callback_admins_pagina(callback: CallbackQuery):
    """Paginação de admins."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    pg = int(callback.data.split(":")[2])
    admins = await listar_admins()
    itens, total_pgs, pg = paginar_lista(admins, pg, 8)

    await safe_edit_message(
        callback.message,
        f"👥 <b>GERENCIAR ADMINS</b> ({len(admins)} total)\n\n"
        "Selecione um admin:",
        reply_markup=menu_admins(itens, pg, total_pgs)
    )


# ---------- DETALHES DE UM ADMIN ----------

@router.callback_query(F.data.startswith("dono:adm_detail:"))
async def callback_admin_detail(callback: CallbackQuery):
    """Detalhes de um admin."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    tid = int(callback.data.split(":")[2])
    admin = await buscar_admin_por_telegram_id(tid)

    if not admin:
        await safe_edit_message(
            callback.message,
            "❌ Admin não encontrado.",
            reply_markup=voltar_dono()
        )
        return

    status_emoji = {
        'ativo': '🟢 Ativo', 'bloqueado': '🔴 Bloqueado',
        'vencido': '🟡 Vencido', 'suspenso': '🟠 Suspenso',
        'aguardando': '⏳ Aguardando'
    }.get(admin['status'], admin['status'])

    nome = escape_html(admin['nome'])
    texto = (
        f"👤 <b>ADMIN — {nome}</b>\n\n"
        f"🆔 ID: <code>{tid}</code>\n"
        f"📛 Username: @{admin.get('username') or 'N/A'}\n"
        f"📊 Status: {status_emoji}\n"
        f"📦 Plano: <b>{admin['plano'].title()}</b>\n"
        f"📅 Início: {formatar_data(admin.get('data_inicio', ''))}\n"
        f"⏰ Vencimento: {formatar_data(admin.get('data_vencimento', ''))}\n"
        f"📈 Pedidos mês: {admin['pedidos_mes_atual']}/{admin['limite_pedidos_mes']}\n"
        f"💹 Margem: {admin['margem_min']}% — {admin['margem_max']}%\n"
        f"🔑 API Key: {'✅ Configurada' if admin.get('api_key') else '❌ Não configurada'}\n"
    )

    await safe_edit_message(
        callback.message, texto,
        reply_markup=detalhe_admin(admin)
    )


# ---------- ADICIONAR ADMIN ----------

@router.callback_query(F.data == "dono:add_admin")
async def callback_add_admin(callback: CallbackQuery, state: FSMContext):
    """Solicita ID do nuovo admin."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "➕ <b>ADICIONAR ADMIN</b>\n\n"
        "Envie o <b>Telegram ID</b> do novo admin.\n\n"
        "💡 O admin pode descobrir seu ID enviando\n"
        "<code>/start</code> para @userinfobot",
        reply_markup=voltar_dono()
    )
    await state.set_state(DonoStates.add_admin_id)


@router.message(DonoStates.add_admin_id)
async def receber_admin_id(message: Message, state: FSMContext):
    """Recebe ID do novo admin."""
    if not await is_owner(message.from_user.id):
        await state.clear()
        return

    texto = message.text.strip()
    try:
        tid = int(texto)
    except ValueError:
        await message.answer(
            "❌ ID inválido. Envie um número.\nExemplo: <code>123456789</code>",
            parse_mode='HTML'
        )
        return

    # Verificar se já existe
    existing = await buscar_admin_por_telegram_id(tid)
    if existing:
        await message.answer(
            f"⚠️ Este ID já é um admin ({escape_html(existing['nome'])}).\n"
            "Use /dono para gerenciar.",
            parse_mode='HTML'
        )
        await state.clear()
        return

    # Salvar e pedir plano
    await state.update_data(new_admin_tid=tid)
    planos = await listar_planos()

    if not planos:
        # Criar com plano padrão
        admin = await criar_admin(
            telegram_id=tid,
            nome=f"Admin {tid}",
            plano='basico',
            dias=30,
            adicionado_por=message.from_user.id
        )
        await message.answer(
            f"✅ Admin <code>{tid}</code> adicionado com plano <b>Básico</b> (30 dias)!",
            parse_mode='HTML',
            reply_markup=voltar_dono()
        )
        await registrar_log('dono', f'Admin {tid} adicionado com plano basico')
        await state.clear()
    else:
        await message.answer(
            f"👤 Admin ID: <code>{tid}</code>\n\n"
            "Selecione o plano:",
            parse_mode='HTML',
            reply_markup=selecionar_plano(tid, planos)
        )
        await state.set_state(DonoStates.add_admin_plano)


@router.callback_query(F.data.startswith("dono:set_plano:"))
async def callback_set_plano(callback: CallbackQuery, state: FSMContext):
    """Define plano para admin (novo ou existente)."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    parts = callback.data.split(":")
    tid = int(parts[2])
    slug = parts[3]

    # Verificar se admin já existe (atualizar plano) ou é novo (criar)
    existing = await buscar_admin_por_telegram_id(tid)

    if existing:
        # Atualizar plano
        await definir_plano_admin(tid, slug)
        await safe_edit_message(
            callback.message,
            f"✅ Plano de <code>{tid}</code> atualizado para <b>{slug.title()}</b>!",
            reply_markup=voltar_dono()
        )
        await registrar_log('dono', f'Plano do admin {tid} atualizado para {slug}')
    else:
        # Criar novo admin
        admin = await criar_admin(
            telegram_id=tid,
            nome=f"Admin {tid}",
            plano=slug,
            adicionado_por=callback.from_user.id
        )
        await safe_edit_message(
            callback.message,
            f"✅ Admin <code>{tid}</code> adicionado com plano <b>{slug.title()}</b>!\n\n"
            "📋 O admin pode usar /admin para configurar seu bot.",
            reply_markup=voltar_dono()
        )
        await registrar_log('dono', f'Admin {tid} adicionado com plano {slug}')

    await state.clear()


# ---------- BLOQUEAR/DESBLOQUEAR ADMIN ----------

@router.callback_query(F.data.startswith("dono:adm_block:"))
async def callback_block_admin(callback: CallbackQuery):
    """Bloqueia ou desbloqueia admin."""
    if not await is_owner(callback.from_user.id):
        return

    tid = int(callback.data.split(":")[2])
    admin = await buscar_admin_por_telegram_id(tid)

    if not admin:
        await callback.answer("❌ Admin não encontrado.", show_alert=True)
        return

    if admin['status'] == 'bloqueado':
        await desbloquear_admin(tid)
        await callback.answer("✅ Admin desbloqueado!", show_alert=True)
        await registrar_log('dono', f'Admin {tid} desbloqueado')
    else:
        await bloquear_admin(tid)
        await callback.answer("🔴 Admin bloqueado!", show_alert=True)
        await registrar_log('dono', f'Admin {tid} bloqueado')

    # Recarregar tela de detalhes
    callback.data = f"dono:adm_detail:{tid}"
    await callback_admin_detail(callback)


# ---------- REMOVER ADMIN ----------

@router.callback_query(F.data.startswith("dono:adm_remover:"))
async def callback_remover_admin(callback: CallbackQuery):
    """Confirma remoção de admin."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    tid = int(callback.data.split(":")[2])
    admin = await buscar_admin_por_telegram_id(tid)

    if not admin:
        return

    nome = escape_html(admin['nome'])
    await safe_edit_message(
        callback.message,
        f"⚠️ <b>REMOVER ADMIN?</b>\n\n"
        f"👤 {nome} (<code>{tid}</code>)\n"
        f"📦 Plano: {admin['plano'].title()}\n\n"
        "⚡ Esta ação é <b>irreversível</b>.",
        reply_markup=confirmar_acao("remover", tid)
    )


@router.callback_query(F.data.startswith("dono:confirm_remover:"))
async def callback_confirm_remover(callback: CallbackQuery):
    """Executa remoção de admin."""
    if not await is_owner(callback.from_user.id):
        return

    tid = int(callback.data.split(":")[2])
    await remover_admin(tid)
    await callback.answer("✅ Admin removido!", show_alert=True)
    await registrar_log('dono', f'Admin {tid} removido')

    await safe_edit_message(
        callback.message,
        f"✅ Admin <code>{tid}</code> removido com sucesso.",
        reply_markup=voltar_dono()
    )


# ---------- RENOVAR PLANO ----------

@router.callback_query(F.data.startswith("dono:adm_renovar:"))
async def callback_renovar_admin(callback: CallbackQuery):
    """Renova plano do admin (mesmo plano, resets timer)."""
    if not await is_owner(callback.from_user.id):
        return

    tid = int(callback.data.split(":")[2])
    admin = await buscar_admin_por_telegram_id(tid)

    if not admin:
        await callback.answer("❌ Admin não encontrado.", show_alert=True)
        return

    await definir_plano_admin(tid, admin['plano'])
    await callback.answer("✅ Plano renovado!", show_alert=True)
    await registrar_log('dono', f'Plano do admin {tid} renovado ({admin["plano"]})')

    # Voltar ao detalhe
    callback.data = f"dono:adm_detail:{tid}"
    await callback_admin_detail(callback)


# ---------- ALTERAR PLANO ----------

@router.callback_query(F.data.startswith("dono:adm_plano:"))
async def callback_alterar_plano_admin(callback: CallbackQuery):
    """Mostra opções de plano para o admin."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    tid = int(callback.data.split(":")[2])
    planos = await listar_planos()

    await safe_edit_message(
        callback.message,
        f"📦 <b>ALTERAR PLANO</b>\n\n"
        f"Admin: <code>{tid}</code>\n\n"
        "Selecione o novo plano:",
        reply_markup=selecionar_plano(tid, planos)
    )


# ==========================================
# ESTATÍSTICAS GLOBAIS
# ==========================================

@router.callback_query(F.data == "dono:stats")
async def callback_stats(callback: CallbackQuery):
    """Mostra estatísticas globais."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    stats = await obter_estatisticas_globais()
    admin_stats = await contar_admins()

    await safe_edit_message(
        callback.message,
        "📊 <b>ESTATÍSTICAS GLOBAIS</b>\n\n"
        f"👥 <b>Admins:</b>\n"
        f"   Total: {admin_stats['total']}\n"
        f"   🟢 Ativos: {admin_stats['ativos']}\n"
        f"   🔴 Bloqueados: {admin_stats['bloqueados']}\n"
        f"   🟡 Vencidos: {admin_stats['vencidos']}\n\n"
        f"👤 <b>Usuários:</b> {formatar_numero(stats.get('total_usuarios', 0))}\n\n"
        f"📦 <b>Pedidos:</b>\n"
        f"   Total: {formatar_numero(stats.get('total_pedidos', 0))}\n"
        f"   Hoje: {formatar_numero(stats.get('pedidos_hoje', 0))}\n\n"
        f"💰 <b>Financeiro:</b>\n"
        f"   Receita: {formatar_moeda(stats.get('receita_total', 0))}\n"
        f"   Custo: {formatar_moeda(stats.get('custo_total', 0))}\n"
        f"   Lucro: {formatar_moeda(stats.get('lucro_total', 0))}",
        reply_markup=voltar_dono()
    )


# ==========================================
# CONFIGURAÇÃO DE PLANOS
# ==========================================

@router.callback_query(F.data == "dono:planos")
async def callback_planos(callback: CallbackQuery):
    """Menu de planos."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "💰 <b>GERENCIAR PLANOS</b>\n\n"
        "Configure os planos de revenda do sistema.",
        reply_markup=menu_planos_config()
    )


@router.callback_query(F.data == "dono:ver_planos")
async def callback_ver_planos(callback: CallbackQuery):
    """Lista planos com detalhes."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    planos = await listar_planos(apenas_ativos=False)
    texto = "📋 <b>PLANOS DISPONÍVEIS</b>\n\n"

    for p in planos:
        ativo = "✅" if p['ativo'] else "❌"
        preco = formatar_moeda(p['preco'])
        texto += (
            f"{ativo} <b>{p['nome']}</b> ({p['slug']})\n"
            f"   💰 {preco} / {p['dias']} dias\n"
            f"   📦 Até {formatar_numero(p['limite_pedidos'])} pedidos/mês\n"
            f"   🤖 Até {p['limite_bots']} bot(s)\n"
            f"   💹 Margem: {p['margem_min']}% — {p['margem_max']}%\n"
            f"   🏷 White Label: {'Sim' if p['permite_whitelabel'] else 'Não'}\n\n"
        )

    await safe_edit_message(
        callback.message, texto,
        reply_markup=menu_planos_config()
    )


# ==========================================
# LICENÇA
# ==========================================

@router.callback_query(F.data == "dono:licenca")
async def callback_licenca(callback: CallbackQuery):
    """Menu de licença."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "🔒 <b>LICENCIAMENTO</b>\n\n"
        "Gerencie a licença e proteção do sistema.",
        reply_markup=menu_licenca()
    )


@router.callback_query(F.data == "dono:ver_licenca")
async def callback_ver_licenca(callback: CallbackQuery):
    """Mostra detalhes da licença."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    owner = await buscar_owner()
    if not owner:
        return

    await safe_edit_message(
        callback.message,
        "🔒 <b>DETALHES DA LICENÇA</b>\n\n"
        f"📋 Tipo: <b>{owner['license_type']}</b>\n"
        f"🏷 White Label: {'✅ Sim' if owner['white_label_enabled'] else '❌ Não'}\n"
        f"📡 Instalação: <code>{owner['installation_id']}</code>\n"
        f"🔑 Hash: <code>{owner['hash_verificacao'][:16]}...</code>\n"
        f"📅 Criado em: {formatar_data(owner['criado_em'])}",
        reply_markup=menu_licenca()
    )


# ==========================================
# REVENDA
# ==========================================

@router.callback_query(F.data == "dono:revenda")
async def callback_revenda(callback: CallbackQuery):
    """Menu de configuração da revenda."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    owner = await buscar_owner()
    msg = owner.get('msg_revenda', '') or 'Não configurada'
    contato = owner.get('arroba_contato', '') or 'Não configurado'

    await safe_edit_message(
        callback.message,
        "📢 <b>CONFIGURAÇÃO DE REVENDA</b>\n\n"
        f"💬 <b>Mensagem:</b>\n{escape_html(msg[:200])}\n\n"
        f"📱 <b>Contato:</b> {escape_html(contato)}\n\n"
        "Configure a mensagem que aparece quando um\n"
        "usuário clica em  '🚀 Ter Meu Próprio Bot'.",
        reply_markup=menu_revenda_config()
    )


@router.callback_query(F.data == "dono:editar_msg_revenda")
async def callback_editar_msg_revenda(callback: CallbackQuery, state: FSMContext):
    """Solicita nova mensagem de revenda."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "✏️ <b>EDITAR MENSAGEM DE REVENDA</b>\n\n"
        "Envie a mensagem que será exibida quando\n"
        "alguém clicar em '🚀 Ter Meu Próprio Bot'.\n\n"
        "💡 Máximo: 2000 caracteres.\n"
        "Suporte: HTML (<b>, <i>, <code>)",
        reply_markup=voltar_dono()
    )
    await state.set_state(DonoStates.editar_msg_revenda)


@router.message(DonoStates.editar_msg_revenda)
async def receber_msg_revenda(message: Message, state: FSMContext):
    """Recebe e salva mensagem de revenda."""
    if not await is_owner(message.from_user.id):
        await state.clear()
        return

    texto = message.text or ""
    if len(texto) > 2000:
        await message.answer(
            f"❌ Mensagem muito longa ({len(texto)}/2000 caracteres).\n"
            "Reduza e envie novamente.",
            parse_mode='HTML'
        )
        return

    await atualizar_owner(msg_revenda=texto)
    await message.answer(
        "✅ Mensagem de revenda atualizada!\n\n"
        f"📋 Preview:\n{texto[:500]}",
        parse_mode='HTML',
        reply_markup=voltar_dono()
    )
    await registrar_log('dono', 'Mensagem de revenda atualizada')
    await state.clear()


@router.callback_query(F.data == "dono:editar_contato")
async def callback_editar_contato(callback: CallbackQuery, state: FSMContext):
    """Solicita novo @contato."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "📱 <b>EDITAR CONTATO</b>\n\n"
        "Envie o @ de contato para revenda.\n"
        "Exemplo: <code>@seunome</code>",
        reply_markup=voltar_dono()
    )
    await state.set_state(DonoStates.editar_contato)


@router.message(DonoStates.editar_contato)
async def receber_contato(message: Message, state: FSMContext):
    """Recebe e salva @contato."""
    if not await is_owner(message.from_user.id):
        await state.clear()
        return

    contato = message.text.strip()
    if not contato.startswith("@"):
        contato = f"@{contato}"

    await atualizar_owner(arroba_contato=contato)
    await message.answer(
        f"✅ Contato atualizado para <b>{escape_html(contato)}</b>",
        parse_mode='HTML',
        reply_markup=voltar_dono()
    )
    await registrar_log('dono', f'Contato atualizado para {contato}')
    await state.clear()


@router.callback_query(F.data == "dono:preview_revenda")
async def callback_preview_revenda(callback: CallbackQuery):
    """Preview da mensagem de revenda."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    owner = await buscar_owner()
    msg = owner.get('msg_revenda', '')
    contato = owner.get('arroba_contato', '')

    if not msg:
        msg = (
            "🚀 <b>TENHA SEU PRÓPRIO BOT DE SMM!</b>\n\n"
            "Venda serviços de redes sociais automaticamente\n"
            "com seu próprio bot no Telegram.\n\n"
            "✅ Painel completo de administração\n"
            "✅ Integração com provedores SMM\n"
            "✅ Pagamentos automatizados\n"
            "✅ Suporte contínuo\n\n"
        )

    preview = msg
    if contato:
        preview += f"\n\n📱 Contate: <b>{escape_html(contato)}</b>"

    await safe_edit_message(
        callback.message,
        f"👁 <b>PREVIEW DA MENSAGEM</b>\n\n"
        f"{'─' * 30}\n{preview}\n{'─' * 30}",
        reply_markup=menu_revenda_config()
    )


# ==========================================
# SEGURANÇA
# ==========================================

@router.callback_query(F.data == "dono:seguranca")
async def callback_seguranca(callback: CallbackQuery):
    """Menu de segurança."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "🛡️ <b>SEGURANÇA</b>\n\n"
        "Gerencie backup, logs e integridade do sistema.",
        reply_markup=menu_seguranca()
    )


@router.callback_query(F.data == "dono:backup")
async def callback_backup_dono(callback: CallbackQuery):
    """Faz backup do banco."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer("💾 Criando backup...")

    try:
        caminho = await fazer_backup()
        await safe_edit_message(
            callback.message,
            f"✅ <b>Backup criado!</b>\n\n"
            f"📁 Arquivo: <code>{escape_html(caminho)}</code>",
            reply_markup=menu_seguranca()
        )
        await registrar_log('dono', f'Backup criado: {caminho}')
    except Exception as e:
        await safe_edit_message(
            callback.message,
            f"❌ Erro ao criar backup: <code>{escape_html(str(e))}</code>",
            reply_markup=menu_seguranca()
        )


@router.callback_query(F.data == "dono:logs")
async def callback_logs_dono(callback: CallbackQuery):
    """Mostra logs recentes."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    logs = await buscar_logs(limite=15)
    texto = "📋 <b>LOGS RECENTES</b>\n\n"

    if logs:
        for log in logs:
            texto += (
                f"<code>[{log['criado_em'][:16]}]</code> "
                f"[{log['tipo']}] {escape_html(log['mensagem'][:50])}\n"
            )
    else:
        texto += "Nenhum log registrado."

    await safe_edit_message(
        callback.message,
        texto[:4000],
        reply_markup=menu_seguranca()
    )


@router.callback_query(F.data == "dono:revalidar")
async def callback_revalidar(callback: CallbackQuery):
    """Revalida hashes de integridade."""
    if not await is_owner(callback.from_user.id):
        return
    await callback.answer()

    owner = await buscar_owner()
    if not owner:
        return

    # Revalidar hashes
    hash_esperado = gerar_hash_seguranca(str(owner['telegram_id']))
    hash_atual = owner.get('hash_verificacao', '')

    if hash_atual == hash_esperado:
        status = "✅ <b>INTEGRIDADE OK</b>"
    else:
        status = "❌ <b>INTEGRIDADE COMPROMETIDA!</b>\nHashes não coincidem."
        # Auto-corrigir
        await atualizar_owner(hash_verificacao=hash_esperado)
        status += "\n🔄 Hash recalculado automaticamente."

    await safe_edit_message(
        callback.message,
        f"🔄 <b>VALIDAÇÃO DE INTEGRIDADE</b>\n\n{status}",
        reply_markup=menu_seguranca()
    )
    await registrar_log('dono', 'Revalidação de integridade executada')


# Callback noop para paginação label
@router.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery):
    await callback.answer()
