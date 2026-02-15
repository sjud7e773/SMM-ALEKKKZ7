"""
Middleware Anti-Flood / Rate Limiting.
=======================================
Proteção contra spam e uso abusivo.
"""

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from typing import Callable, Dict, Any, Awaitable
from collections import defaultdict
import time

from bot.utils.logger import logger


class AntiFloodMiddleware(BaseMiddleware):
    """Limita a taxa de mensagens por usuário."""

    def __init__(self, limite: int = 3, periodo: float = 1.0):
        """
        Args:
            limite: Máximo de mensagens por período.
            periodo: Período em segundos.
        """
        super().__init__()
        self.limite = limite
        self.periodo = periodo
        self.usuarios: Dict[int, list] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Extrair user_id do evento
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        agora = time.time()

        # Limpar timestamps antigos
        self.usuarios[user_id] = [
            t for t in self.usuarios[user_id]
            if agora - t < self.periodo
        ]

        # Verificar limite
        if len(self.usuarios[user_id]) >= self.limite:
            if isinstance(event, Message):
                try:
                    await event.answer("⚠️ Muitas mensagens! Aguarde um momento...")
                except Exception:
                    pass
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer("⚠️ Calma! Aguarde um momento...", show_alert=True)
                except Exception:
                    pass
            logger.warning(f"🛑 Rate limit atingido para user {user_id}")
            return None

        # Registrar timestamp
        self.usuarios[user_id].append(agora)

        return await handler(event, data)
