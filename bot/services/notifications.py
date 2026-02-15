"""
Sistema de Notificações.
=========================
Notificações de novo usuário e vendas para grupo/canal ou chat do dono.
Suporta texto natural (sem exigir HTML/\n).
"""

from aiogram import Bot
from bot.database.connection import get_db
from bot.database.queries_owner import buscar_owner
from bot.utils.logger import logger
from datetime import datetime


async def get_notification_setting(chave: str) -> str:
    """Busca valor de uma configuração de notificação."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT valor FROM notification_settings WHERE chave = ?", (chave,)
        )
        row = await cursor.fetchone()
        return row['valor'] if row else ''
    finally:
        await db.close()


async def set_notification_setting(chave: str, valor: str):
    """Define valor de uma configuração de notificação."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO notification_settings (chave, valor, atualizado_em)
               VALUES (?, ?, datetime('now','localtime'))
               ON CONFLICT(chave) DO UPDATE SET valor = ?, atualizado_em = datetime('now','localtime')""",
            (chave, valor, valor)
        )
        await db.commit()
    finally:
        await db.close()


async def enviar_notificacao_novo_usuario(bot: Bot, user_id: int, username: str, first_name: str):
    """
    Envia notificação de novo usuário registrado.
    Respeita configuração: ativado, destino (dono/grupo), texto natural.
    """
    try:
        ativado = await get_notification_setting('notif_new_user_enabled')
        if ativado != '1':
            return  # Desativado
        
        destino = await get_notification_setting('notif_new_user_dest')  # 'owner' ou 'group'
        
        # Montar mensagem
        data_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
        username_display = f"@{username}" if username else "Sem username"
        
        mensagem = (
            f"📥 Novo usuário registrado!\n\n"
            f"👤 Nome: {first_name}\n"
            f"🔗 {username_display}\n"
            f"🆔 ID: {user_id}\n"
            f"🕒 Data: {data_hora}"
        )
        
        if destino == 'owner':
            # Enviar para chat do dono
            owner = await buscar_owner()
            if owner:
                try:
                    await bot.send_message(owner['telegram_id'], mensagem)
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar notificação de novo usuário para owner: {e}")
        
        elif destino == 'group':
            # Enviar para grupo/canal
            group_id = await get_notification_setting('notif_new_user_group_id')
            if group_id:
                try:
                    await bot.send_message(int(group_id), mensagem)
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar notificação de novo usuário para grupo: {e}")
    
    except Exception as e:
        logger.error(f"❌ Erro no sistema de notificação de novo usuário: {e}")


async def enviar_notificacao_venda(
    bot: Bot,
    user_id: int,
    username: str,
    servico_nome: str,
    valor: float
):
    """
    Envia notificação de venda confirmada.
    Mensagem profissional com botões personalizáveis.
    """
    try:
        ativado = await get_notification_setting('notif_sale_enabled')
        if ativado != '1':
            return
        
        group_id = await get_notification_setting('notif_sale_group_id')
        if not group_id:
            return
        
        data_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
        username_display = username if username else "Sem username"  # SEM @ para não marcar
        
        # Mensagem profissional
        mensagem = (
            "━━━━━━━━━━━━━━━━━━\n"
            "🛍️ <b>VENDA CONFIRMADA COM SUCESSO</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "👤 Cliente\n"
            f"• ID: <code>{user_id}</code>\n"
            f"• Usuário: {username_display}\n\n"
            "📦 Produto\n"
            f"• {servico_nome}\n\n"
            "💰 Valor Pago\n"
            f"• R$ {valor:.2f}\n\n"
            "📅 Data\n"
            f"• {data_hora}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🔥 O que te impede de adquirir nossos serviços?\n"
            "Garanta já o seu!\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        
        # Buscar configurações de botões
        button_text = await get_notification_setting('notif_sale_button_text')
        button_url = await get_notification_setting('notif_sale_button_url')
        
        # Botão automático "Comprar Agora" + botão personalizável
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        
        # Botão personalizável (se configurado)
        if button_text and button_url:
            buttons.append([InlineKeyboardButton(text=button_text, url=button_url)])
        
        # Botão fixo "Comprar Agora" (sempre aparece)
        bot_info = await bot.get_me()
        bot_link = f"https://t.me/{bot_info.username}"
        buttons.append([InlineKeyboardButton(text="🛒 Comprar Agora", url=bot_link)])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        try:
            await bot.send_message(int(group_id), mensagem, parse_mode='HTML', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"❌ Erro ao enviar notificação de venda: {e}")
    
    except Exception as e:
        logger.error(f"❌ Erro no sistema de notificação de venda: {e}")


async def validar_grupo_notificacoes(bot: Bot, group_id: int) -> dict:
    """
    Valida se o bot pode enviar mensagens em um grupo/canal.
    Retorna: {valido: bool, erro: str ou None}
    """
    try:
        # Tentar buscar info do chat
        chat = await bot.get_chat(group_id)
        
        # Verificar se bot é membro
        try:
            member = await bot.get_chat_member(group_id, bot.id)
            
            # Verificar se tem permissão para enviar mensagens
            if member.status in ('administrator', 'creator'):
                return {'valido': True}
            elif member.status == 'member':
                # Verificar se chat permite envio de membros
                if chat.type == 'channel':
                    return {'valido': False, 'erro': 'Bot precisa ser administrador do canal'}
                return {'valido': True}
            else:
                return {'valido': False, 'erro': 'Bot não é membro do grupo/canal'}
        
        except Exception:
            return {'valido': False, 'erro': 'Bot não está no grupo/canal'}
    
    except Exception as e:
        return {'valido': False, 'erro': f'Grupo/canal inválido: {str(e)}'}
