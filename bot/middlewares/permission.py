"""
Middleware de Permissões.
==========================
Verifica hierarquia Owner/Admin/User em cada request.
Bloqueia acesso de admins com plano vencido/bloqueado.

Performance: cache do owner_id por 5 minutos para evitar
queries desnecessárias no banco a cada mensagem.
"""

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta

from bot.utils.logger import logger

# Cache do owner_id para evitar query a cada mensagem
_owner_cache = {'owner_id': None, 'expires': None}
_CACHE_TTL = timedelta(minutes=5)


def invalidar_owner_cache():
    """Invalida cache do owner. Chamar após /definir_dono."""
    global _owner_cache
    _owner_cache = {'owner_id': None, 'expires': None}


class PermissionMiddleware(BaseMiddleware):
    """
    Middleware que injeta informações de permissão no handler data.
    Adiciona 'user_role' e 'admin_data' ao dict de dados do handler.
    
    Performance otimizada:
    - Cache do owner_id (5 min) → evita SELECT * FROM owners a cada msg
    - Só faz query de admin se não for owner e não for user normal
    - Não bloqueia fluxo do user final (apenas admin panel)
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id if event.from_user else None

        if not user_id:
            return await handler(event, data)

        # 1. PRIORIDADE MÁXIMA: Verificar se é owner (com cache)
        #    Owner TEM ACESSO TOTAL IRRESTRITO — bypassa TUDO
        if await self._is_owner_cached(user_id):
            data['user_role'] = 'owner'
            data['admin_data'] = None
            # Owner NUNCA é bloqueado, SEMPRE passa
            return await handler(event, data)

        # 2. Verificar se é admin (só consulta DB se não for owner)
        from bot.database.queries_owner import buscar_admin_por_telegram_id
        admin = await buscar_admin_por_telegram_id(user_id)

        if admin:
            data['user_role'] = 'admin'
            data['admin_data'] = admin

            # Bloquear acesso ao admin panel se inativo (APENAS para admins, NUNCA para owner)
            if admin['status'] in ('bloqueado', 'vencido', 'suspenso'):
                callback_data = getattr(event, 'data', '') or ''
                text = getattr(event, 'text', '') or ''

                # Só bloqueia acesso ao painel admin, NÃO bloqueia o uso normal
                if callback_data.startswith('adm:') or text.startswith('/admin'):
                    if isinstance(event, CallbackQuery):
                        await event.answer(
                            "🔒 Seu acesso está temporariamente suspenso.\n"
                            "Entre em contato com o suporte.",
                            show_alert=True
                        )
                        return
                    elif isinstance(event, Message):
                        status_msg = {
                            'bloqueado': '🔴 Sua conta está bloqueada.',
                            'vencido': '🟡 Seu plano venceu. Renove para continuar.',
                            'suspenso': '🟠 Sua conta está suspensa temporariamente.'
                        }
                        await event.answer(
                            status_msg.get(admin['status'],
                                          '⚠️ Acesso temporariamente indisponível.'),
                            parse_mode='HTML'
                        )
                        return
        else:
            # Usuário final — ZERO overhead no DB, passa direto
            data['user_role'] = 'user'
            data['admin_data'] = None

        return await handler(event, data)

    async def _is_owner_cached(self, user_id: int) -> bool:
        """Verifica owner com cache TTL de 5 min."""
        global _owner_cache

        now = datetime.now()

        # Cache válido?
        if (_owner_cache['owner_id'] is not None and
                _owner_cache['expires'] and now < _owner_cache['expires']):
            return int(_owner_cache['owner_id']) == int(user_id)

        # Cache expirado/vazio — buscar do DB
        try:
            from bot.database.queries_owner import buscar_owner
            owner = await buscar_owner()
            if owner:
                _owner_cache['owner_id'] = owner['telegram_id']
                _owner_cache['expires'] = now + _CACHE_TTL
                return int(owner['telegram_id']) == int(user_id)
            else:
                # Nenhum owner configurado — cache negativo curto (1 min)
                _owner_cache['owner_id'] = -1
                _owner_cache['expires'] = now + timedelta(minutes=1)
                return False
        except Exception:
            return False
