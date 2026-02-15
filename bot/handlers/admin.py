"""
Painel Admin Completo.
=======================
Acesso restrito por ID de admin.
Todas as funcionalidades de administração dentro do Telegram.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json

from bot.config import is_admin, get_config, set_config
from bot.database.queries import (
    obter_estatisticas, obter_estatisticas_periodo, buscar_usuario,
    buscar_gateway, atualizar_gateway, listar_gateways, listar_categorias,
    contar_servicos_ativos, sincronizar_servicos, buscar_servico,
    atualizar_servico, banir_usuario, atualizar_saldo, buscar_pedidos_usuario,
    buscar_logs, registrar_log
)
from bot.services.smm_api import listar_servicos as api_listar_servicos, ver_saldo as api_ver_saldo, limpar_cache
from bot.services.mercadopago import testar_conexao as mp_testar
from bot.services.hoopay import testar_conexao as hp_testar
from bot.database.connection import fazer_backup
from bot.keyboards.inline import (
    admin_principal, admin_gateways, admin_gateway_opcoes, admin_config,
    admin_servicos, admin_sistema, admin_financeiro, admin_usuarios_opcoes,
    voltar_admin, menu_principal
)
from bot.utils.helpers import formatar_moeda, formatar_numero, escape_html, safe_edit_message
from bot.utils.logger import logger

router = Router()


# ==========================================
# OWNER PERMISSION BYPASS
# ==========================================

async def is_owner_or_admin(user_id: int) -> bool:
    """
    Verifica se usuário é owner OU admin.
    Owner tem acesso automático total sem precisar estar na tabela admin.
    """
    from bot.database.queries_owner import buscar_owner
    
    # Owner bypass - acesso total automático
    try:
        owner = await buscar_owner()
        if owner and owner['telegram_id'] == user_id:
            return True
    except Exception:
        pass  # Tabela owner pode não existir ainda
    
    # Se não é owner, verificar admin
    return await is_admin(user_id)


class AdminStates(StatesGroup):
    """Estados do admin."""
    # Gateway
    gw_cred_esperando = State()
    gw_taxa_esperando = State()
    # Config
    cfg_esperando = State()
    # Usuários
    usr_busca = State()
    usr_saldo = State()
    # Serviços
    srv_busca = State()
    srv_editar_nome = State()
    srv_editar_markup = State()


# ==========================================
# COMANDO /admin
# ==========================================

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Comando /admin - abre painel de administração."""
    if not await is_owner_or_admin(message.from_user.id):
        await message.answer("🚫 Acesso negado. Somente o administrador pode usar este comando.")
        return

    await message.answer(
        "🛠 <b>PAINEL DE ADMINISTRAÇÃO</b>\n\n"
        "Selecione uma opção:",
        parse_mode='HTML',
        reply_markup=admin_principal()
    )


@router.callback_query(F.data == "adm:menu")
async def callback_admin_menu(callback: CallbackQuery, state: FSMContext):
    """Volta ao menu admin."""
    if not await is_owner_or_admin(callback.from_user.id):
        await callback.answer("🚫 Acesso negado.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🛠 <b>PAINEL DE ADMINISTRAÇÃO</b>\n\n"
        "Selecione uma opção:",
        parse_mode='HTML',
        reply_markup=admin_principal()
    )


# ==========================================
# ESTATÍSTICAS
# ==========================================

@router.callback_query(F.data == "adm:stats")
async def callback_stats(callback: CallbackQuery):
    """Mostra estatísticas gerais."""
    if not await is_owner_or_admin(callback.from_user.id):
        await callback.answer("🚫 Acesso negado.", show_alert=True)
        return
    await callback.answer()

    stats = await obter_estatisticas()
    servicos_ativos = await contar_servicos_ativos()

    taxas_texto = ""
    for gw, taxa in stats.get('taxas_por_gateway', {}).items():
        taxas_texto += f"  • {gw.title()}: {formatar_moeda(taxa)}\n"
    if not taxas_texto:
        taxas_texto = "  Nenhuma\n"

    texto = (
        f"📊 <b>ESTATÍSTICAS GERAIS</b>\n\n"
        f"👥 <b>Usuários</b>\n"
        f"  • Total: {formatar_numero(stats['total_usuarios'])}\n"
        f"  • Ativos: {formatar_numero(stats['usuarios_ativos'])}\n"
        f"  • Conversão: {stats['conversao']}%\n\n"
        f"📦 <b>Pedidos</b>\n"
        f"  • Total: {formatar_numero(stats['total_pedidos'])}\n"
        f"  • Concluídos: {formatar_numero(stats['pedidos_concluidos'])}\n\n"
        f"💳 <b>Pagamentos</b>\n"
        f"  • Gerados: {formatar_numero(stats['total_pagamentos'])}\n"
        f"  • Aprovados: {formatar_numero(stats['pagamentos_aprovados'])}\n"
        f"  • Pendentes: {formatar_numero(stats['pagamentos_pendentes'])}\n\n"
        f"💰 <b>Financeiro</b>\n"
        f"  • Receita bruta: {formatar_moeda(stats['receita_bruta'])}\n"
        f"  • Custo total: {formatar_moeda(stats['custo_total'])}\n"
        f"  • Lucro líquido: {formatar_moeda(stats['lucro_liquido'])}\n\n"
        f"💸 <b>Taxas por Gateway</b>\n{taxas_texto}\n"
        f"📦 <b>Serviços ativos:</b> {formatar_numero(servicos_ativos)}"
    )

    await callback.message.edit_text(
        texto, parse_mode='HTML', reply_markup=voltar_admin()
    )


# ==========================================
# GATEWAYS
# ==========================================

@router.callback_query(F.data == "adm:gateways")
async def callback_gateways(callback: CallbackQuery):
    """Menu de gateways."""
    if not await is_owner_or_admin(callback.from_user.id):
        await callback.answer("🚫", show_alert=True)
        return
    await callback.answer()

    gws = await listar_gateways()
    texto = "💳 <b>GATEWAYS DE PAGAMENTO</b>\n\n"
    for gw in gws:
        status = "✅ Ativo" if gw['ativo'] else "❌ Inativo"
        padrao = " ⭐" if gw.get('padrao') else ""
        if gw['taxa_tipo'] == 'percentual':
            taxa = f"{gw['taxa_venda']}%"
        else:
            taxa = f"R$ {gw['taxa_venda']:.2f} + R$ {gw['taxa_saque']:.2f}"
        texto += f"  • <b>{gw['nome'].title()}</b>: {status}{padrao} (Taxa: {taxa})\n"

    await callback.message.edit_text(
        texto, parse_mode='HTML', reply_markup=admin_gateways()
    )


@router.callback_query(F.data.startswith("adm:gw:"))
async def callback_gw_opcoes(callback: CallbackQuery):
    """Opções de um gateway."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    gw_nome = callback.data.split(":")[2]
    gw = await buscar_gateway(gw_nome)

    if not gw:
        await callback.answer("❌ Gateway não encontrado.", show_alert=True)
        return

    status = "✅ Ativo" if gw['ativo'] else "❌ Inativo"
    padrao = "⭐ Sim" if gw.get('padrao') else "Não"

    texto = (
        f"💳 <b>{gw_nome.upper()}</b>\n\n"
        f"📊 Status: {status}\n"
        f"⭐ Padrão: {padrao}\n"
        f"💸 Taxa venda: {gw['taxa_venda']}"
    )

    if gw['taxa_tipo'] == 'percentual':
        texto += "%\n"
    else:
        texto += f"\n💸 Taxa saque: {gw['taxa_saque']}\n"

    # Mostrar se credenciais estão configuradas
    config = gw.get('config', {})
    creds_ok = bool(config)
    texto += f"🔑 Credenciais: {'✅ Configuradas' if creds_ok else '❌ Não configuradas'}\n"

    await callback.message.edit_text(
        texto, parse_mode='HTML', reply_markup=admin_gateway_opcoes(gw_nome)
    )


@router.callback_query(F.data.startswith("adm:gw_cred:"))
async def callback_gw_credenciais(callback: CallbackQuery, state: FSMContext):
    """Pede credenciais do gateway."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    gw_nome = callback.data.split(":")[2]
    await state.update_data(gw_nome=gw_nome)

    if gw_nome == 'mercadopago':
        await callback.message.edit_text(
            "🔑 <b>Configurar Mercado Pago</b>\n\n"
            "Envie o <b>Access Token</b> do Mercado Pago.\n\n"
            "Você encontra em:\n"
            "Mercado Pago → Configurações → Credenciais → Access Token\n\n"
            "Envie o token:",
            parse_mode='HTML',
            reply_markup=voltar_admin()
        )
    elif gw_nome == 'hoopay':
        await callback.message.edit_text(
            "🔑 <b>Configurar Hoopay</b>\n\n"
            "Envie as credenciais no formato:\n"
            "<code>api_key|api_url</code>\n\n"
            "Exemplo:\n"
            "<code>sua_api_key_aqui|https://api.hoopay.com.br</code>\n\n"
            "Se não souber a URL, envie apenas a API Key.",
            parse_mode='HTML',
            reply_markup=voltar_admin()
        )

    await state.set_state(AdminStates.gw_cred_esperando)


@router.message(AdminStates.gw_cred_esperando)
async def receber_gw_credenciais(message: Message, state: FSMContext):
    """Recebe e salva credenciais do gateway."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    gw_nome = data.get('gw_nome', '')
    texto = message.text.strip()

    config = {}
    if gw_nome == 'mercadopago':
        # VALIDAR TOKEN ANTES DE SALVAR
        from bot.services.mercadopago import validar_token_mp
        
        validacao = await validar_token_mp(texto)
        
        if not validacao.get('valido'):
            erro_msg = validacao.get('erro', 'Token rejeitado')
            await message.answer(
                f"❌ <b>Token do MercadoPago INVÁLIDO!</b>\n\n"
                f"<b>Erro:</b> {escape_html(erro_msg)}\n\n"
                f"Verifique suas credenciais e tente novamente.",
                parse_mode='HTML',
                reply_markup=voltar_admin()
            )
            await state.clear()
            return
        
        # Token válido - prosseguir
        config = {'access_token': texto}
    elif gw_nome == 'hoopay':
        partes = texto.split('|')
        config = {'api_key': partes[0].strip()}
        if len(partes) > 1:
            config['api_url'] = partes[1].strip()
        else:
            config['api_url'] = 'https://api.hoopay.com.br'

    await atualizar_gateway(gw_nome, config=config)
    await registrar_log('admin', f'Credenciais do gateway {gw_nome} atualizadas')

    await message.answer(
        f"✅ <b>Credenciais do {gw_nome.title()} salvas!</b>\n\n"
        f"Use 🧪 Testar Conexão para verificar.",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm:gw_taxa:"))
async def callback_gw_taxa(callback: CallbackQuery, state: FSMContext):
    """Pede novas taxas do gateway."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    gw_nome = callback.data.split(":")[2]
    await state.update_data(gw_nome=gw_nome)

    gw = await buscar_gateway(gw_nome)

    if gw_nome == 'mercadopago':
        await callback.message.edit_text(
            f"💸 <b>Editar Taxa - Mercado Pago</b>\n\n"
            f"Taxa atual: {gw['taxa_venda']}%\n\n"
            f"Envie a nova taxa de venda (%):\n"
            f"Exemplo: <code>0.99</code>",
            parse_mode='HTML',
            reply_markup=voltar_admin()
        )
    elif gw_nome == 'hoopay':
        await callback.message.edit_text(
            f"💸 <b>Editar Taxas - Hoopay</b>\n\n"
            f"Taxa venda atual: R$ {gw['taxa_venda']:.2f}\n"
            f"Taxa saque atual: R$ {gw['taxa_saque']:.2f}\n\n"
            f"Envie no formato <code>taxa_venda|taxa_saque</code>:\n"
            f"Exemplo: <code>0.40|0.30</code>",
            parse_mode='HTML',
            reply_markup=voltar_admin()
        )

    await state.set_state(AdminStates.gw_taxa_esperando)


@router.message(AdminStates.gw_taxa_esperando)
async def receber_gw_taxa(message: Message, state: FSMContext):
    """Recebe e salva taxas do gateway."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    gw_nome = data.get('gw_nome', '')
    texto = message.text.strip().replace(',', '.')

    try:
        if gw_nome == 'mercadopago':
            taxa = float(texto)
            await atualizar_gateway(gw_nome, taxa_venda=taxa)
            await message.answer(
                f"✅ Taxa do Mercado Pago atualizada para {taxa}%",
                reply_markup=voltar_admin()
            )
        elif gw_nome == 'hoopay':
            partes = texto.split('|')
            taxa_v = float(partes[0].strip())
            taxa_s = float(partes[1].strip()) if len(partes) > 1 else 0.30
            await atualizar_gateway(gw_nome, taxa_venda=taxa_v, taxa_saque=taxa_s)
            await message.answer(
                f"✅ Taxas da Hoopay atualizadas:\n"
                f"Venda: R$ {taxa_v:.2f} | Saque: R$ {taxa_s:.2f}",
                reply_markup=voltar_admin()
            )
        await registrar_log('admin', f'Taxas do gateway {gw_nome} atualizadas')
    except (ValueError, IndexError):
        await message.answer("❌ Formato inválido. Tente novamente.", reply_markup=voltar_admin())

    await state.clear()


@router.callback_query(F.data.startswith("adm:gw_toggle:"))
async def callback_gw_toggle(callback: CallbackQuery):
    """Ativa/desativa gateway."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    gw_nome = callback.data.split(":")[2]
    gw = await buscar_gateway(gw_nome)
    novo_estado = 0 if gw['ativo'] else 1
    await atualizar_gateway(gw_nome, ativo=novo_estado)
    estado_txt = "ativado" if novo_estado else "desativado"
    await callback.answer(f"✅ {gw_nome.title()} {estado_txt}!", show_alert=True)
    await registrar_log('admin', f'Gateway {gw_nome} {estado_txt}')

    # Recarregar opções
    gw = await buscar_gateway(gw_nome)
    status = "✅ Ativo" if gw['ativo'] else "❌ Inativo"
    await callback.message.edit_text(
        f"💳 <b>{gw_nome.upper()}</b>\n\n📊 Status: {status}",
        parse_mode='HTML',
        reply_markup=admin_gateway_opcoes(gw_nome)
    )


@router.callback_query(F.data.startswith("adm:gw_padrao:"))
async def callback_gw_padrao(callback: CallbackQuery):
    """Define gateway como padrão."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    gw_nome = callback.data.split(":")[2]

    # Remover padrão de todos
    from bot.database.connection import get_db
    db = await get_db()
    try:
        await db.execute("UPDATE gateways SET padrao = 0")
        await db.execute("UPDATE gateways SET padrao = 1 WHERE nome = ?", (gw_nome,))
        await db.commit()
    finally:
        await db.close()

    await callback.answer(f"⭐ {gw_nome.title()} definido como padrão!", show_alert=True)
    await registrar_log('admin', f'Gateway padrão alterado para {gw_nome}')


@router.callback_query(F.data.startswith("adm:gw_test:"))
async def callback_gw_testar(callback: CallbackQuery):
    """Testa conexão com gateway."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer("🧪 Testando...")
    gw_nome = callback.data.split(":")[2]

    if gw_nome == 'mercadopago':
        resultado = await mp_testar()
    elif gw_nome == 'hoopay':
        resultado = await hp_testar()
    else:
        resultado = {'sucesso': False, 'erro': 'Gateway desconhecido'}

    if resultado['sucesso']:
        await callback.message.edit_text(
            f"✅ <b>{gw_nome.title()} - Conexão OK!</b>\n\n"
            f"{resultado.get('mensagem', 'Tudo funcionando!')}",
            parse_mode='HTML',
            reply_markup=admin_gateway_opcoes(gw_nome)
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>{gw_nome.title()} - Erro na conexão</b>\n\n"
            f"Motivo: {resultado.get('erro', 'Erro desconhecido')}\n\n"
            f"Verifique as credenciais.",
            parse_mode='HTML',
            reply_markup=admin_gateway_opcoes(gw_nome)
        )


# ==========================================
# CONFIGURAÇÕES
# ==========================================

@router.callback_query(F.data == "adm:config")
async def callback_config_menu(callback: CallbackQuery):
    """Menu de configurações."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()

    margem = await get_config('margem_lucro', '75')
    api_url = await get_config('api_url', '')
    api_key = await get_config('api_key', '')
    admin_id = await get_config('admin_id', '')
    comissao = await get_config('comissao_indicacao', '5')
    sync_int = await get_config('sync_intervalo_minutos', '60')
    status_int = await get_config('status_check_minutos', '5')

    api_key_masked = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else ("Configurada" if api_key else "❌ Não configurada")

    texto = (
        f"⚙️ <b>CONFIGURAÇÕES</b>\n\n"
        f"📈 Margem: <b>{margem}%</b>\n"
        f"🔑 API Key: {api_key_masked}\n"
        f"🌐 API URL: <code>{api_url}</code>\n"
        f"👤 Admin ID: <code>{admin_id}</code>\n"
        f"🎁 Comissão indicação: {comissao}%\n"
        f"🔄 Sync serviços: a cada {sync_int} min\n"
        f"📊 Check status: a cada {status_int} min"
    )

    await callback.message.edit_text(
        texto, parse_mode='HTML', reply_markup=admin_config()
    )


@router.callback_query(F.data.startswith("adm:cfg:"))
async def callback_config_editar(callback: CallbackQuery, state: FSMContext):
    """Edita uma configuração."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()

    cfg_key = callback.data.split(":")[2]
    await state.update_data(cfg_key=cfg_key)

    nomes = {
        'margem': ('📈 Margem de Lucro', 'Envie a nova margem (%).\nExemplo: <code>75</code>'),
        'bot_token': ('🤖 Token do Bot', 'Envie o novo token do Bot Telegram.\n⚠️ Será necessário reiniciar o bot.'),
        'api_key': ('🔑 API Key SMM', 'Envie a nova API Key do painel SMM.'),
        'api_url': ('🌐 URL da API', 'Envie a nova URL da API.\nExemplo: <code>https://baratosociais.com/api/v2</code>'),
        'admin_id': ('👤 Admin ID', 'Envie o novo ID de admin do Telegram.\n⚠️ CUIDADO: Isso transferirá o controle.'),
        'msg_inicio': ('💬 Mensagem Inicial', 'Envie a nova mensagem de boas-vindas.\nUse \\n para quebra de linha.'),
        'comissao': ('🎁 Comissão Indicação', 'Envie a nova % de comissão.\nExemplo: <code>5</code>'),
        'sync_int': ('⏰ Intervalo Sync', 'Envie intervalo em minutos.\nExemplo: <code>60</code>'),
        'status_int': ('⏰ Check Status', 'Envie intervalo em minutos.\nExemplo: <code>5</code>'),
    }

    nome, instrucao = nomes.get(cfg_key, ('Configuração', 'Envie o novo valor:'))

    valor_atual = await get_config({
        'margem': 'margem_lucro', 'bot_token': 'bot_token',
        'api_key': 'api_key', 'api_url': 'api_url',
        'admin_id': 'admin_id', 'msg_inicio': 'mensagem_inicio',
        'comissao': 'comissao_indicacao', 'sync_int': 'sync_intervalo_minutos',
        'status_int': 'status_check_minutos'
    }.get(cfg_key, cfg_key), '')

    await callback.message.edit_text(
        f"{nome}\n\n"
        f"Valor atual: <code>{valor_atual[:50]}</code>\n\n"
        f"{instrucao}",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.set_state(AdminStates.cfg_esperando)


@router.message(AdminStates.cfg_esperando)
async def receber_config(message: Message, state: FSMContext):
    """Recebe e salva nova configuração."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    cfg_key = data.get('cfg_key', '')
    valor = message.text.strip()

    # Mapear chave para nome real no banco
    chave_mapa = {
        'margem': 'margem_lucro',
        'bot_token': 'bot_token',
        'api_key': 'api_key',
        'api_url': 'api_url',
        'admin_id': 'admin_id',
        'msg_inicio': 'mensagem_inicio',
        'comissao': 'comissao_indicacao',
        'sync_int': 'sync_intervalo_minutos',
        'status_int': 'status_check_minutos',
    }

    chave_real = chave_mapa.get(cfg_key, cfg_key)
    await set_config(chave_real, valor)
    await registrar_log('admin', f'Configuração {chave_real} atualizada')

    # Limpar cache se necessário
    if cfg_key == 'api_key':
        limpar_cache()

    await message.answer(
        f"✅ <b>Configuração atualizada!</b>\n\n"
        f"🔑 {chave_real}: <code>{valor[:30]}...</code>" if len(valor) > 30 else f"✅ <b>Configuração atualizada!</b>\n\n🔑 {chave_real}: <code>{valor}</code>",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.clear()


# ==========================================
# SERVIÇOS
# ==========================================

@router.callback_query(F.data == "adm:servicos")
async def callback_servicos_menu(callback: CallbackQuery):
    """Menu de serviços."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    total = await contar_servicos_ativos()
    cats = await listar_categorias()

    await callback.message.edit_text(
        f"📦 <b>SERVIÇOS</b>\n\n"
        f"📊 Ativos: {total}\n"
        f"📂 Categorias: {len(cats)}\n\n"
        f"🔄 Sincronize para atualizar do painel SMM.",
        parse_mode='HTML',
        reply_markup=admin_servicos()
    )


@router.callback_query(F.data == "adm:srv_sync")
async def callback_sincronizar_servicos(callback: CallbackQuery):
    """Sincroniza serviços da API."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer("🔄 Sincronizando...")

    try:
        servicos = await api_listar_servicos(forcar=True)
        if servicos:
            await sincronizar_servicos(servicos)
            await callback.message.edit_text(
                f"✅ <b>Serviços sincronizados!</b>\n\n"
                f"📊 Total: {len(servicos)} serviços\n\n"
                f"Os serviços foram atualizados no banco local.",
                parse_mode='HTML',
                reply_markup=admin_servicos()
            )
            await registrar_log('admin', f'{len(servicos)} serviços sincronizados')
        else:
            await callback.message.edit_text(
                "❌ <b>Falha na sincronização</b>\n\n"
                "Nenhum serviço retornado pela API.\n"
                "Verifique a API Key nas configurações.",
                parse_mode='HTML',
                reply_markup=admin_servicos()
            )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ <b>Erro:</b> {str(e)[:200]}",
            parse_mode='HTML',
            reply_markup=admin_servicos()
        )


@router.callback_query(F.data == "adm:srv_list")
async def callback_listar_servicos(callback: CallbackQuery, state: FSMContext):
    """Lista serviços com busca."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.edit_text(
        "📦 <b>Buscar Serviço</b>\n\n"
        "Envie o ID do serviço (ID interno ou da API)\n"
        "para editar nome, markup ou bloquear:",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.set_state(AdminStates.srv_busca)


@router.message(AdminStates.srv_busca)
async def receber_busca_servico(message: Message, state: FSMContext):
    """Busca serviço para edição."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return

    try:
        sid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID inválido.")
        return

    servico = await buscar_servico(sid)
    if not servico:
        from bot.database.queries import buscar_servico_por_api_id
        servico = await buscar_servico_por_api_id(sid)

    if not servico:
        await message.answer("❌ Serviço não encontrado.", reply_markup=voltar_admin())
        await state.clear()
        return

    await state.update_data(srv_edit_id=servico['id'])

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Editar Nome", callback_data=f"adm:srv_nome:{servico['id']}")],
        [InlineKeyboardButton(text="💰 Editar Markup", callback_data=f"adm:srv_markup:{servico['id']}")],
        [InlineKeyboardButton(
            text=f"{'🔓 Desbloquear' if not servico['ativo'] else '🔒 Bloquear'}",
            callback_data=f"adm:srv_toggle:{servico['id']}"
        )],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])

    markup_txt = f"{servico['markup_custom']}%" if servico['markup_custom'] is not None else "Global"
    status = "✅ Ativo" if servico['ativo'] else "❌ Bloqueado"

    await message.answer(
        f"📦 <b>Serviço #{servico['id']}</b>\n\n"
        f"📋 API ID: {servico['service_id_api']}\n"
        f"📝 Nome: {servico['nome']}\n"
        f"📝 Nome custom: {servico['nome_custom'] or 'Nenhum'}\n"
        f"📂 Categoria: {servico['categoria']}\n"
        f"💰 Rate: {servico['rate']}\n"
        f"📊 Min: {servico['min_quantidade']} | Max: {servico['max_quantidade']}\n"
        f"📈 Markup: {markup_txt}\n"
        f"📊 Status: {status}",
        parse_mode='HTML',
        reply_markup=kb
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm:srv_nome:"))
async def callback_editar_nome_servico(callback: CallbackQuery, state: FSMContext):
    """Editar nome de serviço."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    sid = int(callback.data.split(":")[2])
    await state.update_data(srv_edit_id=sid)
    await callback.message.edit_text(
        "📝 Envie o novo nome personalizado para este serviço:",
        reply_markup=voltar_admin()
    )
    await state.set_state(AdminStates.srv_editar_nome)


@router.message(AdminStates.srv_editar_nome)
async def receber_nome_servico(message: Message, state: FSMContext):
    """Salva novo nome do serviço."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    sid = data.get('srv_edit_id')
    await atualizar_servico(sid, nome_custom=message.text.strip())
    await message.answer("✅ Nome atualizado!", reply_markup=voltar_admin())
    await state.clear()


@router.callback_query(F.data.startswith("adm:srv_markup:"))
async def callback_editar_markup(callback: CallbackQuery, state: FSMContext):
    """Editar markup do serviço."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    sid = int(callback.data.split(":")[2])
    await state.update_data(srv_edit_id=sid)
    await callback.message.edit_text(
        "💰 Envie o markup personalizado (%).\n"
        "Envie <code>0</code> para usar a margem global.\n"
        "Exemplo: <code>100</code> para 100% de margem.",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.set_state(AdminStates.srv_editar_markup)


@router.message(AdminStates.srv_editar_markup)
async def receber_markup_servico(message: Message, state: FSMContext):
    """Salva markup do serviço."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    sid = data.get('srv_edit_id')

    try:
        markup = float(message.text.strip().replace(',', '.'))
        if markup == 0:
            await atualizar_servico(sid, markup_custom=None)
            await message.answer("✅ Markup resetado para margem global.", reply_markup=voltar_admin())
        else:
            await atualizar_servico(sid, markup_custom=markup)
            await message.answer(f"✅ Markup atualizado para {markup}%", reply_markup=voltar_admin())
    except ValueError:
        await message.answer("❌ Valor inválido.", reply_markup=voltar_admin())

    await state.clear()


@router.callback_query(F.data.startswith("adm:srv_toggle:"))
async def callback_toggle_servico(callback: CallbackQuery):
    """Bloqueia/desbloqueia serviço."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    sid = int(callback.data.split(":")[2])
    servico = await buscar_servico(sid)
    novo = 0 if servico['ativo'] else 1
    await atualizar_servico(sid, ativo=novo)
    estado = "ativado" if novo else "bloqueado"
    await callback.answer(f"✅ Serviço {estado}!", show_alert=True)


# ==========================================
# USUÁRIOS
# ==========================================

@router.callback_query(F.data == "adm:usuarios")
async def callback_usuarios_menu(callback: CallbackQuery, state: FSMContext):
    """Menu de usuários."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.edit_text(
        "👥 <b>GERENCIAR USUÁRIOS</b>\n\n"
        "Envie o <b>Telegram ID</b> do usuário para gerenciar:",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.set_state(AdminStates.usr_busca)


@router.message(AdminStates.usr_busca)
async def receber_busca_usuario(message: Message, state: FSMContext):
    """Busca usuário por Telegram ID."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return

    try:
        tid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID inválido.")
        return

    user = await buscar_usuario(tid)
    if not user:
        await message.answer("❌ Usuário não encontrado.", reply_markup=voltar_admin())
        await state.clear()
        return

    ban_status = "🚫 Banido" if user['banido'] else "✅ Ativo"

    await message.answer(
        f"👤 <b>Usuário</b>\n\n"
        f"🆔 ID: <code>{user['telegram_id']}</code>\n"
        f"📛 Nome: {user['nome']}\n"
        f"👤 Username: @{user['username'] or 'N/A'}\n"
        f"💰 Saldo: {formatar_moeda(user['saldo'])}\n"
        f"💸 Total gasto: {formatar_moeda(user['total_gasto'])}\n"
        f"📦 Pedidos: {user['total_pedidos']}\n"
        f"📊 Status: {ban_status}\n"
        f"📅 Registro: {user['criado_em']}",
        parse_mode='HTML',
        reply_markup=admin_usuarios_opcoes(tid)
    )
    await state.clear()


@router.callback_query(F.data.startswith("adm:usr_saldo:"))
async def callback_ajustar_saldo(callback: CallbackQuery, state: FSMContext):
    """Ajustar saldo de usuário."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    tid = int(callback.data.split(":")[2])
    await state.update_data(usr_tid=tid)

    user = await buscar_usuario(tid)
    await callback.message.edit_text(
        f"💰 <b>Ajustar Saldo</b>\n\n"
        f"Usuário: {user['nome']}\n"
        f"Saldo atual: {formatar_moeda(user['saldo'])}\n\n"
        f"Envie o valor:\n"
        f"• Positivo para ADICIONAR (ex: <code>50</code>)\n"
        f"• Negativo para SUBTRAIR (ex: <code>-20</code>)\n"
        f"• Com = para DEFINIR (ex: <code>=100</code>)",
        parse_mode='HTML',
        reply_markup=voltar_admin()
    )
    await state.set_state(AdminStates.usr_saldo)


@router.message(AdminStates.usr_saldo)
async def receber_ajuste_saldo(message: Message, state: FSMContext):
    """Processa ajuste de saldo."""
    if not await is_owner_or_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    tid = data.get('usr_tid')
    texto = message.text.strip().replace(',', '.')

    try:
        if texto.startswith('='):
            valor = float(texto[1:])
            novo = await atualizar_saldo(tid, valor, 'definir')
            await message.answer(f"✅ Saldo definido para {formatar_moeda(novo)}", reply_markup=voltar_admin())
        else:
            valor = float(texto)
            if valor >= 0:
                novo = await atualizar_saldo(tid, valor, 'adicionar')
                await message.answer(f"✅ {formatar_moeda(valor)} adicionados.\nNovo saldo: {formatar_moeda(novo)}", reply_markup=voltar_admin())
            else:
                novo = await atualizar_saldo(tid, abs(valor), 'subtrair')
                await message.answer(f"✅ {formatar_moeda(abs(valor))} removidos.\nNovo saldo: {formatar_moeda(novo)}", reply_markup=voltar_admin())

        await registrar_log('admin', f'Saldo ajustado para user {tid}: {texto}')
    except ValueError:
        await message.answer("❌ Valor inválido.", reply_markup=voltar_admin())

    await state.clear()


@router.callback_query(F.data.startswith("adm:usr_ban:"))
async def callback_banir_usuario(callback: CallbackQuery):
    """Bane/desbane usuário."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    tid = int(callback.data.split(":")[2])
    user = await buscar_usuario(tid)

    if user['banido']:
        await banir_usuario(tid, False)
        await callback.answer("✅ Usuário desbanido!", show_alert=True)
        await registrar_log('admin', f'Usuário {tid} desbanido')
    else:
        await banir_usuario(tid, True)
        await callback.answer("🚫 Usuário banido!", show_alert=True)
        await registrar_log('admin', f'Usuário {tid} banido')


@router.callback_query(F.data.startswith("adm:usr_pedidos:"))
async def callback_ver_pedidos_usuario(callback: CallbackQuery):
    """Ver pedidos de um usuário."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    tid = int(callback.data.split(":")[2])
    user = await buscar_usuario(tid)
    if not user:
        return

    from bot.database.queries import buscar_pedidos_usuario
    pedidos = await buscar_pedidos_usuario(user['id'], 10)

    if not pedidos:
        await callback.message.edit_text(
            f"📦 Nenhum pedido para este usuário.",
            reply_markup=voltar_admin()
        )
        return

    texto = f"📦 <b>Pedidos de {user['nome']}</b>\n\n"
    for p in pedidos:
        from bot.utils.helpers import status_emoji
        emoji = status_emoji(p.get('status', ''))
        texto += f"{emoji} #{p['id']} - {formatar_moeda(p['preco_final'])} - {p['status']}\n"

    await callback.message.edit_text(
        texto, parse_mode='HTML', reply_markup=voltar_admin()
    )


# ==========================================
# FINANCEIRO
# ==========================================

@router.callback_query(F.data == "adm:financeiro")
async def callback_financeiro(callback: CallbackQuery):
    """Menu financeiro."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.edit_text(
        "💰 <b>RELATÓRIO FINANCEIRO</b>\n\nEscolha o período:",
        parse_mode='HTML',
        reply_markup=admin_financeiro()
    )


@router.callback_query(F.data.startswith("adm:fin:"))
async def callback_financeiro_periodo(callback: CallbackQuery):
    """Relatório financeiro por período."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    dias = int(callback.data.split(":")[2])

    stats = await obter_estatisticas_periodo(dias)
    periodo_txt = "Total" if dias >= 9999 else f"Últimos {dias} dias" if dias > 1 else "Hoje"

    await callback.message.edit_text(
        f"💰 <b>Financeiro - {periodo_txt}</b>\n\n"
        f"📦 Pedidos: {formatar_numero(stats['pedidos'])}\n"
        f"💵 Receita: {formatar_moeda(stats['receita'])}\n"
        f"💸 Custo: {formatar_moeda(stats['custo'])}\n"
        f"💰 Lucro: {formatar_moeda(stats['lucro'])}",
        parse_mode='HTML',
        reply_markup=admin_financeiro()
    )


# ==========================================
# UPSELL
# ==========================================

@router.callback_query(F.data == "adm:upsell")
async def callback_upsell_menu(callback: CallbackQuery):
    """Menu de upsell."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()

    from bot.services.upsell import listar_regras_upsell
    regras = await listar_regras_upsell()
    upsell_ativo = await get_config('upsell_ativo', '1')

    texto = f"🎁 <b>SISTEMA DE UPSELL</b>\n\n"
    texto += f"📊 Status: {'✅ Ativo' if upsell_ativo == '1' else '❌ Inativo'}\n"
    texto += f"📋 Regras: {len(regras)}\n\n"

    for r in regras[:10]:
        status = "✅" if r['ativo'] else "❌"
        texto += f"{status} #{r['id']} → Serviço #{r['servico_destino_id']} ({r['desconto_pct']}% desc)\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'❌ Desativar' if upsell_ativo == '1' else '✅ Ativar'} Upsell",
            callback_data="adm:upsell_toggle"
        )],
        [InlineKeyboardButton(text="🔙 Admin", callback_data="adm:menu")],
    ])

    await callback.message.edit_text(texto, parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data == "adm:upsell_toggle")
async def callback_upsell_toggle(callback: CallbackQuery):
    """Ativa/desativa sistema de upsell."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    atual = await get_config('upsell_ativo', '1')
    novo = '0' if atual == '1' else '1'
    await set_config('upsell_ativo', novo)
    estado = "ativado" if novo == '1' else "desativado"
    await callback.answer(f"✅ Upsell {estado}!", show_alert=True)


# ==========================================
# CUPONS (Admin)
# ==========================================

@router.callback_query(F.data == "adm:cupons")
async def callback_cupons_menu(callback: CallbackQuery):
    """Menu de cupons."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()

    from bot.database.connection import get_db
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM cupons ORDER BY id DESC LIMIT 20")
        cupons = [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()

    texto = "🎟️ <b>CUPONS</b>\n\n"
    if cupons:
        for c in cupons:
            status = "✅" if c['ativo'] else "❌"
            usos = f"{c['usos_atuais']}/{c['usos_max']}"
            if c['desconto_pct'] > 0:
                desc = f"{c['desconto_pct']}%"
            else:
                desc = formatar_moeda(c['desconto_fixo'])
            texto += f"{status} <code>{c['codigo']}</code> - {desc} ({usos} usos)\n"
    else:
        texto += "Nenhum cupom criado.\n"

    texto += "\nPara criar: envie no chat\n<code>/cupom CODIGO TIPO VALOR USOS</code>\nEx: <code>/cupom PROMO10 pct 10 100</code>"

    await callback.message.edit_text(texto, parse_mode='HTML', reply_markup=voltar_admin())


# ==========================================
# SISTEMA
# ==========================================

@router.callback_query(F.data == "adm:sistema")
async def callback_sistema(callback: CallbackQuery):
    """Menu de sistema."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()
    await callback.message.edit_text(
        "🛠 <b>SISTEMA</b>\n\nEscolha uma opção:",
        parse_mode='HTML',
        reply_markup=admin_sistema()
    )


@router.callback_query(F.data == "adm:backup")
async def callback_backup(callback: CallbackQuery):
    """Faz backup do banco."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer("💾 Criando backup...")

    try:
        caminho = await fazer_backup()
        await callback.message.edit_text(
            f"✅ <b>Backup criado!</b>\n\n"
            f"📁 Arquivo: <code>{caminho}</code>",
            parse_mode='HTML',
            reply_markup=admin_sistema()
        )
        await registrar_log('admin', f'Backup criado: {caminho}')
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Erro ao criar backup: {e}",
            reply_markup=admin_sistema()
        )


@router.callback_query(F.data == "adm:logs")
async def callback_logs(callback: CallbackQuery):
    """Mostra logs recentes."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer()

    logs = await buscar_logs(limite=15)
    texto = "📋 <b>LOGS RECENTES</b>\n\n"

    if logs:
        for log in logs:
            texto += f"<code>[{log['criado_em']}]</code> [{log['tipo']}] {log['mensagem'][:60]}\n"
    else:
        texto += "Nenhum log registrado."

    await callback.message.edit_text(
        texto[:4000], parse_mode='HTML', reply_markup=admin_sistema()
    )


@router.callback_query(F.data == "adm:saldo_api")
async def callback_saldo_api(callback: CallbackQuery):
    """Mostra saldo da API SMM."""
    if not await is_owner_or_admin(callback.from_user.id):
        return
    await callback.answer("🔄 Consultando...")

    resultado = await api_ver_saldo()

    if 'error' in resultado:
        await callback.message.edit_text(
            f"❌ Erro ao consultar saldo: {resultado['error']}",
            reply_markup=admin_sistema()
        )
    else:
        saldo = resultado.get('balance', resultado.get('Balance', '0'))
        moeda = resultado.get('currency', 'BRL')
        await callback.message.edit_text(
            f"💰 <b>Saldo da API SMM</b>\n\n"
            f"📊 Saldo: <b>{saldo} {moeda}</b>",
            parse_mode='HTML',
            reply_markup=admin_sistema()
        )


# ==========================================
# COMANDOS ADMIN EXTRAS
# ==========================================

@router.message(Command("cupom"))
async def cmd_cupom(message: Message):
    """Criar cupom: /cupom CODIGO TIPO VALOR USOS"""
    if not await is_owner_or_admin(message.from_user.id):
        return

    partes = message.text.split()
    if len(partes) < 5:
        await message.answer(
            "📋 Uso: <code>/cupom CODIGO TIPO VALOR USOS</code>\n\n"
            "TIPO: <code>pct</code> (percentual) ou <code>fixo</code> (valor fixo)\n"
            "Exemplos:\n"
            "• <code>/cupom PROMO10 pct 10 100</code>\n"
            "• <code>/cupom BONUS5 fixo 5 50</code>",
            parse_mode='HTML'
        )
        return

    codigo = partes[1].upper()
    tipo = partes[2].lower()
    valor = float(partes[3])
    usos = int(partes[4])

    from bot.database.queries import criar_cupom
    try:
        if tipo == 'pct':
            cupom = await criar_cupom(codigo, desconto_pct=valor, usos_max=usos)
        else:
            cupom = await criar_cupom(codigo, desconto_fixo=valor, usos_max=usos)

        await message.answer(
            f"✅ <b>Cupom criado!</b>\n\n"
            f"🎟️ Código: <code>{codigo}</code>\n"
            f"💰 Desconto: {valor}{'%' if tipo == 'pct' else ' R$'}\n"
            f"📊 Usos: {usos}",
            parse_mode='HTML'
        )
        await registrar_log('admin', f'Cupom {codigo} criado')
    except Exception as e:
        await message.answer(f"❌ Erro: {e}")
