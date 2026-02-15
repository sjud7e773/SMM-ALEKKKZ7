"""
Gateway Mercado Pago.
======================
Integração com PIX via Mercado Pago.
"""

import aiohttp
import json
from bot.utils.logger import logger
from bot.database.queries import buscar_gateway


async def _get_credentials() -> dict:
    """Obtém credenciais do Mercado Pago."""
    gw = await buscar_gateway('mercadopago')
    if not gw:
        return {}
    return gw.get('config', {})


async def criar_pagamento_pix(valor: float, descricao: str,
                                referencia: str, email_pagador: str = '') -> dict:
    """
    Cria um pagamento PIX no Mercado Pago.
    Retorna: {sucesso, qr_code, link_pagamento, referencia_externa, erro}
    """
    creds = await _get_credentials()
    access_token = creds.get('access_token', '')

    if not access_token:
        return {'sucesso': False, 'erro': 'Token do Mercado Pago não configurado.'}

    url = "https://api.mercadopago.com/v1/payments"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": referencia
    }

    payload = {
        "transaction_amount": round(valor, 2),
        "description": descricao,
        "payment_method_id": "pix",
        "payer": {
            "email": email_pagador or "cliente@bot.com"
        },
        "external_reference": referencia
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()

                if resp.status in (200, 201):
                    pix_data = data.get('point_of_interaction', {}).get('transaction_data', {})
                    return {
                        'sucesso': True,
                        'id_pagamento': str(data.get('id', '')),
                        'qr_code': pix_data.get('qr_code', ''),
                        'qr_code_base64': pix_data.get('qr_code_base64', ''),
                        'link_pagamento': pix_data.get('ticket_url', ''),
                        'referencia_externa': referencia,
                    }
                else:
                    erro = data.get('message', str(data))
                    logger.error(f"❌ Erro Mercado Pago: {erro}")
                    return {'sucesso': False, 'erro': erro}

    except Exception as e:
        logger.error(f"❌ Erro ao criar pagamento MP: {e}")
        return {'sucesso': False, 'erro': str(e)}


async def verificar_pagamento(payment_id: str) -> dict:
    """
    Verifica status de um pagamento no Mercado Pago.
    Retorna: {status, aprovado, valor}
    """
    creds = await _get_credentials()
    access_token = creds.get('access_token', '')

    if not access_token:
        return {'status': 'erro', 'aprovado': False}

    url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                status = data.get('status', 'unknown')
                return {
                    'status': status,
                    'aprovado': status == 'approved',
                    'valor': data.get('transaction_amount', 0),
                    'referencia': data.get('external_reference', ''),
                }
    except Exception as e:
        logger.error(f"❌ Erro ao verificar pagamento MP: {e}")
        return {'status': 'erro', 'aprovado': False}


async def testar_conexao() -> dict:
    """Testa se as credenciais do Mercado Pago estão funcionando."""
    creds = await _get_credentials()
    access_token = creds.get('access_token', '')

    if not access_token:
        return {'sucesso': False, 'erro': 'Token não configurado.'}

    url = "https://api.mercadopago.com/v1/payment_methods"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return {'sucesso': True, 'mensagem': 'Conexão OK!'}
                else:
                    data = await resp.json()
                    return {'sucesso': False, 'erro': data.get('message', 'Erro desconhecido')}
    except Exception as e:
        return {'sucesso': False, 'erro': str(e)}


async def validar_token_mp(access_token: str) -> dict:
    """
    Valida token do Mercado Pago fazendo requisição REAL à API.
    Retorna: {valido: bool, erro: str ou None}
    
    CRÍTICO: Deve ser chamado ANTES de salvar o token no banco.
    """
    if not access_token or not access_token.strip():
        return {'valido': False, 'erro': 'Token vazio'}
    
    # Tentar buscar dados do usuário da conta MP
    url = "https://api.mercadopago.com/v1/users/me"
    headers = {"Authorization": f"Bearer {access_token.strip()}"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        'valido': True,
                        'conta_id': data.get('id'),
                        'email': data.get('email'),
                        'nickname': data.get('nickname')
                    }
                else:
                    data = await resp.json()
                    erro_msg = data.get('message', 'Token inválido')
                    return {'valido': False, 'erro': erro_msg}
    except Exception as e:
        return {'valido': False, 'erro': f'Erro ao validar: {str(e)}'}

