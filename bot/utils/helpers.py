"""
Funções auxiliares.
===================
Utilitários gerais para o bot.
"""

import html
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from datetime import datetime
from aiogram.exceptions import TelegramBadRequest
from bot.utils.logger import logger


def formatar_moeda(valor) -> str:
    """Formata valor para moeda brasileira (R$)."""
    if isinstance(valor, Decimal):
        valor = float(valor)
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


def formatar_numero(numero) -> str:
    """Formata número com separador de milhar."""
    try:
        return f"{int(numero):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def formatar_data(data_str: str) -> str:
    """Formata string de data para formato brasileiro."""
    try:
        if isinstance(data_str, str):
            dt = datetime.fromisoformat(data_str)
        else:
            dt = data_str
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(data_str) if data_str else "N/A"


def truncar_texto(texto: str, max_len: int = 64) -> str:
    """Trunca texto com reticências se exceder o limite.
    Default 64 = limite seguro para botões do Telegram."""
    if not texto:
        return ""
    if len(texto) <= max_len:
        return texto
    return texto[:max_len - 1] + "…"


def decimal_seguro(valor) -> Decimal:
    """Converte valor para Decimal de forma segura."""
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor))
    except Exception:
        return Decimal('0')


def arredondar_preco(valor: Decimal) -> Decimal:
    """Arredonda preço para 2 casas decimais (para cima)."""
    return valor.quantize(Decimal('0.01'), rounding=ROUND_CEILING)


def arredondar_normal(valor: Decimal) -> Decimal:
    """Arredonda para 2 casas decimais (normal)."""
    return valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def validar_link(link: str) -> bool:
    """Valida se o link é uma URL válida básica."""
    if not link:
        return False
    link = link.strip()
    return link.startswith("http://") or link.startswith("https://")


def escape_html(texto: str) -> str:
    """
    Escapa caracteres especiais para parse_mode=HTML.
    Converte <, >, & em entidades HTML seguras.
    """
    if not texto:
        return ""
    return html.escape(str(texto))


def status_emoji(status: str) -> str:
    """Retorna emoji para status do pedido."""
    mapa = {
        'pendente': '⏳',
        'Pending': '⏳',
        'In progress': '🔄',
        'em_andamento': '🔄',
        'Processing': '🔄',
        'Completed': '✅',
        'concluido': '✅',
        'Partial': '⚠️',
        'parcial': '⚠️',
        'Canceled': '❌',
        'cancelado': '❌',
        'Refunded': '💰',
        'erro': '🚫',
        'Error': '🚫',
    }
    return mapa.get(status, '❓')


def paginar_lista(lista: list, pagina: int, itens_por_pagina: int = 8) -> tuple:
    """Pagina uma lista. Retorna (itens_pagina, total_paginas, pagina_atual)."""
    total = len(lista)
    total_paginas = max(1, (total + itens_por_pagina - 1) // itens_por_pagina)
    pagina = max(1, min(pagina, total_paginas))
    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    return lista[inicio:fim], total_paginas, pagina


async def safe_edit_message(message, texto: str, reply_markup=None,
                            parse_mode: str = 'HTML'):
    """
    Edita mensagem de forma segura.
    Trata TODOS os erros comuns do Telegram:
    - "message is not modified" → ignora
    - "can't parse entities" → reenvia sem formatação
    - "message to edit not found" → ignora
    - "message to delete not found" → ignora
    - "query is too old" → ignora
    - Qualquer outro TelegramBadRequest → loga e ignora
    """
    try:
        await message.edit_text(
            texto,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except TelegramBadRequest as e:
        erro = str(e).lower()
        if "message is not modified" in erro:
            pass
        elif "can't parse entities" in erro:
            try:
                # Strip HTML tags e reenvia sem formatação
                import re
                texto_limpo = re.sub(r'<[^>]+>', '', texto)
                await message.edit_text(
                    texto_limpo,
                    parse_mode=None,
                    reply_markup=reply_markup
                )
            except Exception:
                pass
        elif "message to edit not found" in erro:
            pass
        elif "message to delete not found" in erro:
            pass
        elif "query is too old" in erro:
            pass
        elif "bot was blocked" in erro:
            pass
        elif "chat not found" in erro:
            pass
        else:
            logger.warning(f"⚠️ Erro ao editar mensagem: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Erro inesperado ao editar mensagem: {e}")


async def safe_send_message(target, texto: str, reply_markup=None,
                            parse_mode: str = 'HTML', **kwargs):
    """
    Envia mensagem de forma segura.
    Trata erros de bot blocked, chat not found, parse entities.
    """
    try:
        return await target.answer(
            texto, parse_mode=parse_mode,
            reply_markup=reply_markup, **kwargs
        )
    except TelegramBadRequest as e:
        erro = str(e).lower()
        if "can't parse entities" in erro:
            try:
                import re
                texto_limpo = re.sub(r'<[^>]+>', '', texto)
                return await target.answer(
                    texto_limpo, parse_mode=None,
                    reply_markup=reply_markup, **kwargs
                )
            except Exception:
                pass
        elif "bot was blocked" in erro or "chat not found" in erro:
            pass
        else:
            logger.warning(f"⚠️ Erro ao enviar mensagem: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Erro inesperado ao enviar: {e}")
    return None


async def safe_answer_callback(callback, texto: str = "", show_alert: bool = False):
    """
    Responde callback de forma segura.
    Ignora erros de callback já respondido.
    """
    try:
        await callback.answer(texto, show_alert=show_alert)
    except Exception:
        pass


def emoji_numero(n: int) -> str:
    """Converte número (1-99) em emoji numérico."""
    digitos = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣',
        '4': '4️⃣', '5': '5️⃣', '6': '6️⃣', '7': '7️⃣',
        '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(digitos.get(d, d) for d in str(n))
