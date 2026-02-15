"""
Painel Owner (Proprietário) - Bot SMM
======================================
Funções EXCLUSIVAS do dono do sistema.
Separação clara entre owner e admin.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.keyboards.inline import voltar_menu
from bot.utils.helpers import safe_edit_message
from bot.utils.logger import logger

router = Router()


# ==========================================
# MENU PRINCIPAL OWNER
# ==========================================

def owner_menu_principal() -> InlineKeyboardMarkup:
    """Menu principal do owner."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 PAINEL DO PROPRIETÁRIO", callback_data="noop")],
        [InlineKeyboardButton(text="🔐 Gerenciar Admins", callback_data="owner:admins")],
        [InlineKeyboardButton(text="💎 Planos SaaS", callback_data="owner:saas_plans")],
        [InlineKeyboardButton(text="⚙️ Configurações Globais", callback_data="owner:global_config")],
        [InlineKeyboardButton(text="📋 Logs do Sistema", callback_data="owner:system_logs")],
        [InlineKeyboardButton(text="💾 Backup/Restore", callback_data="owner:backup")],
        [InlineKeyboardButton(text="🛠️ Modo Manutenção", callback_data="owner:maintenance")],
        [InlineKeyboardButton(text="🔄 Voltar ao Admin", callback_data="adm:menu")],
    ])


@router.callback_query(F.data == "owner:menu")
async def callback_owner_menu(callback: CallbackQuery):
    """Menu owner principal - TELA DEDICADA."""
    await callback.answer()
    
    await callback.message.answer(
        "👑 <b>PAINEL DO PROPRIETÁRIO</b>\n\n"
        "Acesso às funções exclusivas do dono:\n\n"
        "🔐 <b>Gerenciar Admins</b>\n"
        "Criar, editar planos e permissões de administradores\n\n"
        "💎 <b>Planos SaaS</b>\n"
        "Configure planos de revenda para admins\n\n"
        "⚙️ <b>Configurações Globais</b>\n"
        "Defina parâmetros que afetam todo o sistema\n\n"
        "📋 <b>Logs</b>\n"
        "Visualize erros e atividades do sistema\n\n"
        "💾 <b>Backup</b>\n"
        "Faça backup ou restaure o banco de dados\n\n"
        "🛠️ <b>Modo Manutenção</b>\n"
        "Desative temporariamente o bot",
        reply_markup=owner_menu_principal()
    )


# ==========================================
# GERENCIAR ADMINS
# ==========================================

def menu_gerenciar_admins() -> InlineKeyboardMarkup:
    """Menu gerenciar admins."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 GERENCIAR ADMINS", callback_data="noop")],
        [InlineKeyboardButton(text="➕ Criar Novo Admin", callback_data="owner:admin_criar")],
        [InlineKeyboardButton(text="📋 Listar Todos Admins", callback_data="owner:admin_listar")],
        [InlineKeyboardButton(text="✏️ Editar Permissões", callback_data="owner:admin_editar")],
        [InlineKeyboardButton(text="💎 Definir Plano SaaS", callback_data="owner:admin_plano")],
        [InlineKeyboardButton(text="🚫 Bloquear Admin", callback_data="owner:admin_bloquear")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="owner:menu")],
    ])


@router.callback_query(F.data == "owner:admins")
async def callback_owner_admins(callback: CallbackQuery):
    """Gerenciar admins - TELA DEDICADA."""
    await callback.answer()
    
    # Busca quantidade de admins
    from bot.database.queries_owner import contar_admins
    total = await contar_admins()
    
    await callback.message.answer(
        "🔐 <b>GERENCIAMENTO DE ADMINISTRADORES</b>\n\n"
        f"Total de admins: <b>{total}</b>\n\n"
        "<b>O que são Admins?</b>\n"
        "Administradores têm acesso ao painel admin\n"
        "do bot, mas NÃO podem acessar funções de owner.\n\n"
        "<b>Funcionalidades:</b>\n"
        "• Criar novos administradores\n"
        "• Definir permissões específicas\n"
        "• Vincular planos SaaS\n"
        "• Bloquear/desbloquear acesso\n\n"
        "<i>💡 Perfeito para sistema de revenda!</i>",
        reply_markup=menu_gerenciar_admins()
    )


# ==========================================
# PLANOS SAAS
# ==========================================

def menu_saas_plans() -> InlineKeyboardMarkup:
    """Menu planos SaaS."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 PLANOS SAAS", callback_data="noop")],
        [InlineKeyboardButton(text="➕ Criar Novo Plano", callback_data="owner:saas_criar")],
        [InlineKeyboardButton(text="📋 Listar Todos Planos", callback_data="owner:saas_listar")],
        [InlineKeyboardButton(text="✏️ Editar Plano", callback_data="owner:saas_editar")],
        [InlineKeyboardButton(text="❌ Desativar Plano", callback_data="owner:saas_desativar")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="owner:menu")],
    ])


@router.callback_query(F.data == "owner:saas_plans")
async def callback_owner_saas(callback: CallbackQuery):
    """Planos SaaS - TELA DEDICADA."""
    await callback.answer()
    
    await callback.message.answer(
        "💎 <b>PLANOS SAAS (REVENDA)</b>\n\n"
        "<b>O que são Planos SaaS?</b>\n"
        "São pacotes de funcionalidades que você\n"
        "vende para admins/revendedores.\n\n"
        "<b>Exemplos de planos:</b>\n\n"
        "🥉 <b>Básico</b> - R$ 50/mês\n"
        "Até 100 usuários, serviços limitados\n\n"
        "🥈 <b>Profissional</b> - R$ 150/mês\n"
        "Até 1000 usuários, todos os serviços\n\n"
        "🥇 <b>Enterprise</b> - R$ 500/mês\n"
        "Usuários ilimitados, marca branca\n\n"
        "<i>💡 Monetize seu bot vendendo acesso!</i>",
        reply_markup=menu_saas_plans()
    )


# ==========================================
# BACKUP/RESTORE
# ==========================================

def menu_backup() -> InlineKeyboardMarkup:
    """Menu backup."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 BACKUP/RESTORE", callback_data="noop")],
        [InlineKeyboardButton(text="📥 Fazer Backup Agora", callback_data="owner:backup_fazer")],
        [InlineKeyboardButton(text="📤 Restaurar Backup", callback_data="owner:backup_restaurar")],
        [InlineKeyboardButton(text="⏰ Backup Automático", callback_data="owner:backup_auto")],
        [InlineKeyboardButton(text="📋 Histórico de Backups", callback_data="owner:backup_historico")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="owner:menu")],
    ])


@router.callback_query(F.data == "owner:backup")
async def callback_owner_backup(callback: CallbackQuery):
    """Backup/Restore - TELA DEDICADA."""
    await callback.answer()
    
    await callback.message.answer(
        "💾 <b>SISTEMA DE BACKUP</b>\n\n"
        "<b>Por que fazer backup?</b>\n"
        "Proteja seus dados contra perda acidental:\n"
        "• Erros de configuração\n"
        "• Falhas de servidor\n"
        "• Atualizações problemáticas\n\n"
        "<b>O que é salvo no backup?</b>\n"
        "• Todos os usuários\n"
        "• Histórico de pedidos\n"
        "• Configurações do sistema\n"
        "• Cupons e promoções\n"
        "• Tudo exceto arquivos de mídia\n\n"
        "<i>⚠️ Recomendamos backup diário!</i>",
        reply_markup=menu_backup()
    )


@router.callback_query(F.data == "owner:backup_fazer")
async def callback_fazer_backup(callback: CallbackQuery):
    """Faz backup do banco."""
    await callback.answer("Gerando backup...")
    
    import os
    import shutil
    from datetime import datetime
    
    try:
        # Copia o banco de dados
        db_path = "config.db"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/backup_{timestamp}.db"
        
        os.makedirs("backups", exist_ok=True)
        shutil.copy2(db_path, backup_path)
        
        # Envia o arquivo para o owner
        from aiogram.types import FSInputFile
        await callback.message.answer_document(
            document=FSInputFile(backup_path),
            caption=(
                f"💾 <b>Backup Realizado!</b>\n\n"
                f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
                f"Arquivo: <code>{os.path.basename(backup_path)}</code>\n\n"
                f"<i>Guarde este arquivo em local seguro!</i>"
            )
        )
        
        logger.info(f"Backup criado: {backup_path}")
        
    except Exception as e:
        logger.error(f"Erro ao criar backup: {e}")
        await callback.message.answer(
            f"❌ <b>Erro ao criar backup!</b>\n\n{str(e)}",
            reply_markup=voltar_menu()
        )


# ==========================================
# MODO MANUTENÇÃO
# ==========================================

def menu_manutencao() -> InlineKeyboardMarkup:
    """Menu modo manutenção."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ MODO MANUTENÇÃO", callback_data="noop")],
        [InlineKeyboardButton(text="🔴 Ativar Manutenção", callback_data="owner:manut_ativar")],
        [InlineKeyboardButton(text="🟢 Desativar Manutenção", callback_data="owner:manut_desativar")],
        [InlineKeyboardButton(text="📝 Personalizar Mensagem", callback_data="owner:manut_msg")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="owner:menu")],
    ])


@router.callback_query(F.data == "owner:maintenance")
async def callback_owner_manutencao(callback: CallbackQuery):
    """Modo manutenção - TELA DEDICADA."""
    await callback.answer()
    
    from bot.config import get_config
    ativo = await get_config('maintenance_mode', '0')
    status = "🔴 ATIVADO" if ativo == '1' else "🟢 DESATIVADO"
    
    await callback.message.answer(
        "🛠️ <b>MODO MANUTENÇÃO</b>\n\n"
        f"Status atual: <b>{status}</b>\n\n"
        "<b>O que é o Modo Manutenção?</b>\n"
        "Quando ativado, o bot para de aceitar\n"
        "comandos de usuários normais.\n\n"
        "<b>Quem ainda tem acesso?</b>\n"
        "• Owner (você)\n"
        "• Admins (se configurado)\n\n"
        "<b>Quando usar?</b>\n"
        "• Atualizações importantes\n"
        "• Manutenção no servidor\n"
        "• Correção de bugs críticos\n\n"
        "<i>💡 Evita problemas durante mudanças</i>",
        reply_markup=menu_manutencao()
    )


@router.callback_query(F.data.startswith("owner:manut_"))
async def callback_toggle_manutencao(callback: CallbackQuery):
    """Ativa/desativa modo manutenção."""
    await callback.answer()
    acao = callback.data.split("_")[1]
    
    from bot.config import set_config
    
    if acao == "ativar":
        await set_config('maintenance_mode', '1')
        await callback.message.answer(
            "🔴 <b>MODO MANUTENÇÃO ATIVADO!</b>\n\n"
            "O bot está agora em manutenção.\n"
            "Usuários normais não conseguem usar comandos.\n\n"
            "<i>Apenas owner e admins têm acesso.</i>",
            reply_markup=voltar_menu()
        )
        logger.warn("⚠️ MODO MANUTENÇÃO ATIVADO")
        
    elif acao == "desativar":
        await set_config('maintenance_mode', '0')
        await callback.message.answer(
            "🟢 <b>MODO MANUTENÇÃO DESATIVADO!</b>\n\n"
            "O bot voltou ao normal.\n"
            "Todos os usuários podem usá-lo novamente.",
            reply_markup=voltar_menu()
        )
        logger.info("✅ Modo manutenção desativado")


# ==========================================
# LOGS DO SISTEMA
# ==========================================

@router.callback_query(F.data == "owner:system_logs")
async def callback_owner_logs(callback: CallbackQuery):
    """Visualizar logs - TELA DEDICADA."""
    await callback.answer()
    
    try:
        # Lê as últimas 50 linhas do log
        with open("bot.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            ultimas_linhas = "".join(lines[-50:])
        
        await callback.message.answer(
            "📋 <b>LOGS DO SISTEMA</b>\n\n"
            "<i>Últimas 50 entradas:</i>\n\n"
            f"<code>{ultimas_linhas}</code>",
            reply_markup=voltar_menu()
        )
    except FileNotFoundError:
        await callback.message.answer(
            "📋 <b>LOGS DO SISTEMA</b>\n\n"
            "Nenhum log encontrado ainda.",
            reply_markup=voltar_menu()
        )
