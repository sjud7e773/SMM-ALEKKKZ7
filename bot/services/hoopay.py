"""
Gateway Hoopay.
================
Integração com Hoopay para pagamentos PIX.
"""

import aiohttp
import json
from bot.utils.logger import logger
from bot.database.queries import buscar_gateway


async def _get_credentials() -> dict:
    """Obtém credenciais da Hoopay."""
    gw = await buscar_gateway('hoopay')
    if not gw:
        return {}
    return gw.get('config', {})


async def criar_pagamento_pix(valor: float, descricao: str,
                                referencia: str) -> dict:
    """
    Cria um pagamento PIX na Hoopay.
    Retorna: {sucesso, qr_code, link_pagamento, referencia_externa, erro}
    """
    creds = await _get_credentials()
    api_key = creds.get('api_key', '')
    api_url = creds.get('api_url', 'https://api.hoopay.com.br')

    if not api_key:
        return {'sucesso': False, 'erro': 'API Key da Hoopay não configurada.'}

    url = f"{api_url}/v1/payments"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "amount": round(valor * 100),  # Hoopay usa centavos
        "description": descricao,
        "external_reference": referencia,
        "payment_method": "pix"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()

                if resp.status in (200, 201) and data.get('id'):
                    return {
                        'sucesso': True,
                        'id_pagamento': str(data.get('id', '')),
                        'qr_code': data.get('pix_qr_code', data.get('qr_code', '')),
                        'link_pagamento': data.get('payment_url', ''),
                        'referencia_externa': referencia,
                    }
                else:
                    erro = data.get('message', data.get('error', str(data)))
                    logger.error(f"❌ Erro Hoopay: {erro}")
                    return {'sucesso': False, 'erro': erro}

    except Exception as e:
        logger.error(f"❌ Erro ao criar pagamento Hoopay: {e}")
        return {'sucesso': False, 'erro': str(e)}


async def verificar_pagamento(payment_id: str) -> dict:
    """Verifica status de pagamento na Hoopay."""
    creds = await _get_credentials()
    api_key = creds.get('api_key', '')
    api_url = creds.get('api_url', 'https://api.hoopay.com.br')

    if not api_key:
        return {'status': 'erro', 'aprovado': False}

    url = f"{api_url}/v1/payments/{payment_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                status = data.get('status', 'unknown')
                aprovado = status in ('paid', 'approved', 'completed')
                return {
                    'status': status,
                    'aprovado': aprovado,
                    'valor': data.get('amount', 0) / 100,
                    'referencia': data.get('external_reference', ''),
                }
    except Exception as e:
        logger.error(f"❌ Erro ao verificar pagamento Hoopay: {e}")
        return {'status': 'erro', 'aprovado': False}


async def testar_conexao() -> dict:
    """Testa conexão com Hoopay."""
    creds = await _get_credentials()
    api_key = creds.get('api_key', '')
    api_url = creds.get('api_url', 'https://api.hoopay.com.br')

    if not api_key:
        return {'sucesso': False, 'erro': 'API Key não configurada.'}

    url = f"{api_url}/v1/account"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return {'sucesso': True, 'mensagem': 'Conexão OK!'}
                else:
                    data = await resp.json()
                    return {'sucesso': False, 'erro': data.get('message', 'Erro')}
    except Exception as e:
        return {'sucesso': False, 'erro': str(e)}
