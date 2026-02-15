"""
Middleware de Autenticação.
============================
Registra usuários automaticamente e verifica bans.
"""

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from typing import Callable, Dict, Any, Awaitable

from bot.database.queries import criar_usuario, buscar_usuario
from bot.utils.logger import logger


class AuthMiddleware(BaseMiddleware):
    """Registra novos usuários e bloqueia banidos."""

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        user = None
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.from_user:
            user = event.from_user

        if user is None:
            return await handler(event, data)

        # Registrar/atualizar usuário
        try:
            nome = user.full_name or "Sem Nome"
            username = user.username or ""
            db_user = await criar_usuario(user.id, nome, username)
            
            # CRÍTICO: Notificar novo usuário (se configurado)
            if db_user:
                # Verificar se é primeiro registro (não atualização)
                from bot.database.queries import buscar_usuario
                usuario_existente = await buscar_usuario(user.id)
                if usuario_existente and usuario_existente.get('criado_em') == usuario_existente.get('atualizado_em'):
                    # Primeiro registro — disparar notificação
                    try:
                        from bot.services.notifications import enviar_notificacao_novo_usuario
                        bot = data.get('bot') or event.bot
                        await enviar_notificacao_novo_usuario(bot, user.id, username, nome)
                    except Exception:
                        pass  # Não quebrar fluxo se notificação falhar

            # Verificar ban
            if db_user and db_user.get('banido', 0) == 1:
                if isinstance(event, Message):
                    try:
                        await event.answer("🚫 Sua conta foi bloqueada. Entre em contato com o suporte.")
                    except Exception:
                        pass
                elif isinstance(event, CallbackQuery):
                    try:
                        await event.answer("🚫 Conta bloqueada.", show_alert=True)
                    except Exception:
                        pass
                return None

            # Adicionar dados do usuário ao contexto
            data['db_user'] = db_user

        except Exception as e:
            logger.error(f"❌ Erro no middleware de auth: {e}")

        return await handler(event, data)
