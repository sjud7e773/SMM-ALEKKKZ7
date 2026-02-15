"""
Integração com API SMM.
========================
Todas as operações com o painel SMM via API.
Inclui retry automático e cache de serviços.
"""

import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
from bot.utils.logger import logger

# Cache de serviços
_cache_servicos: list = []
_cache_timestamp: datetime = None
CACHE_TTL_MINUTOS = 30


async def _get_api_params():
    """Obtém parâmetros de conexão da API."""
    from bot.config import get_config
    api_url = await get_config('api_url', 'https://baratosociais.com/api/v2')
    api_key = await get_config('api_key', '')
    return api_url, api_key


async def _fazer_requisicao(params: dict, tentativas: int = 3) -> dict:
    """Faz requisição à API com retry automático."""
    api_url, api_key = await _get_api_params()

    if not api_key:
        logger.error("❌ API key não configurada!")
        return {'error': 'API key não configurada. Configure via /admin.'}

    params['key'] = api_key

    for tentativa in range(1, tentativas + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, data=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    texto = await resp.text()
                    try:
                        resultado = json.loads(texto)
                    except json.JSONDecodeError:
                        logger.error(f"❌ Resposta inválida da API: {texto[:200]}")
                        resultado = {'error': f'Resposta inválida da API: {texto[:100]}'}

                    if 'error' in resultado:
                        logger.warning(f"⚠️ API retornou erro: {resultado['error']}")

                    return resultado

        except asyncio.TimeoutError:
            logger.warning(f"⏰ Timeout na tentativa {tentativa}/{tentativas}")
            if tentativa < tentativas:
                await asyncio.sleep(2 ** tentativa)  # Backoff exponencial
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro de conexão tentativa {tentativa}/{tentativas}: {e}")
            if tentativa < tentativas:
                await asyncio.sleep(2 ** tentativa)
        except Exception as e:
            logger.error(f"❌ Erro inesperado na API: {e}")
            return {'error': str(e)}

    return {'error': 'Falha após múltiplas tentativas. Verifique sua conexão.'}


async def listar_servicos(forcar: bool = False) -> list:
    """Lista todos os serviços do painel SMM. Usa cache."""
    global _cache_servicos, _cache_timestamp

    # Verificar cache
    if not forcar and _cache_servicos and _cache_timestamp:
        if datetime.now() - _cache_timestamp < timedelta(minutes=CACHE_TTL_MINUTOS):
            return _cache_servicos

    resultado = await _fazer_requisicao({'action': 'services'})

    if isinstance(resultado, list):
        _cache_servicos = resultado
        _cache_timestamp = datetime.now()
        logger.info(f"✅ {len(resultado)} serviços carregados da API.")
        return resultado
    elif isinstance(resultado, dict) and 'error' in resultado:
        logger.error(f"❌ Erro ao listar serviços: {resultado['error']}")
        # Retorna cache antigo se existir
        if _cache_servicos:
            return _cache_servicos
        return []
    return []


async def criar_pedido(service_id: int, link: str, quantity: int) -> dict:
    """Cria um pedido no painel SMM."""
    params = {
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    resultado = await _fazer_requisicao(params)
    if 'order' in resultado:
        logger.info(f"✅ Pedido criado na API: #{resultado['order']}")
    else:
        logger.error(f"❌ Falha ao criar pedido: {resultado}")
    return resultado


async def ver_status(order_id: str) -> dict:
    """Consulta status de um pedido."""
    params = {
        'action': 'status',
        'order': order_id
    }
    return await _fazer_requisicao(params)


async def ver_multi_status(order_ids: list) -> dict:
    """Consulta status de múltiplos pedidos."""
    params = {
        'action': 'status',
        'orders': ','.join(str(oid) for oid in order_ids)
    }
    return await _fazer_requisicao(params)


async def refill(order_id: str) -> dict:
    """Solicita refill de um pedido."""
    params = {
        'action': 'refill',
        'order': order_id
    }
    resultado = await _fazer_requisicao(params)
    logger.info(f"🔄 Refill solicitado para pedido #{order_id}: {resultado}")
    return resultado


async def ver_status_refill(refill_id: str) -> dict:
    """Consulta status de um refill."""
    params = {
        'action': 'refill_status',
        'refill': refill_id
    }
    return await _fazer_requisicao(params)


async def cancelar(order_id: str) -> dict:
    """Solicita cancelamento de um pedido. API usa 'orders' (plural)."""
    params = {
        'action': 'cancel',
        'orders': str(order_id)  # API exige 'orders' mesmo para 1
    }
    resultado = await _fazer_requisicao(params)
    logger.info(f"❌ Cancelamento solicitado para pedido #{order_id}: {resultado}")

    # API retorna lista [{order: N, cancel: 1}] — extrair resultado
    if isinstance(resultado, list) and len(resultado) > 0:
        item = resultado[0]
        cancel_result = item.get('cancel', {})
        if isinstance(cancel_result, dict) and 'error' in cancel_result:
            return {'error': cancel_result['error']}
        return {'cancel': cancel_result}
    return resultado


async def ver_saldo() -> dict:
    """Consulta saldo disponível na API."""
    params = {'action': 'balance'}
    resultado = await _fazer_requisicao(params)
    return resultado


def limpar_cache():
    """Limpa o cache de serviços."""
    global _cache_servicos, _cache_timestamp
    _cache_servicos = []
    _cache_timestamp = None
