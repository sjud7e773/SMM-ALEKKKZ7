"""
Serviço de Licenciamento.
==========================
Gerencia licenças do sistema (PROTEGIDA / WHITE_LABEL).
Validação de hash SHA256, integridade do owner e proteção contra tampering.
"""

import hashlib
from datetime import datetime
from bot.config import gerar_hash_seguranca, verificar_hash
from bot.database.queries_owner import buscar_owner, atualizar_owner
from bot.utils.logger import logger


class LicenseError(Exception):
    """Erro de licença."""
    pass


async def validar_licenca() -> dict:
    """
    Valida a licença na inicialização do sistema.
    Retorna dict com dados da licença ou levanta LicenseError.
    """
    owner = await buscar_owner()
    if not owner:
        return {
            'valida': False,
            'tipo': 'NENHUMA',
            'motivo': 'Nenhum dono configurado. Use /definir_dono.'
        }

    # Verificar hash de integridade do owner
    hash_esperado = gerar_hash_seguranca(str(owner['telegram_id']))
    if owner['hash_verificacao'] != hash_esperado:
        logger.error("❌ VIOLAÇÃO DE INTEGRIDADE: Hash do owner não corresponde!")
        logger.error(f"   Esperado: {hash_esperado[:16]}... | Atual: {owner['hash_verificacao'][:16]}...")
        return {
            'valida': False,
            'tipo': owner['license_type'],
            'motivo': 'Hash de integridade corrompido. Possível tampering.',
            'owner_id': owner['telegram_id']
        }

    # Verificar signature hash
    sig_esperada = gerar_hash_seguranca(f"{owner['telegram_id']}:owner:master")
    if owner['signature_hash'] != sig_esperada:
        logger.error("❌ VIOLAÇÃO DE ASSINATURA: Signature hash não corresponde!")
        return {
            'valida': False,
            'tipo': owner['license_type'],
            'motivo': 'Assinatura digital inválida.',
            'owner_id': owner['telegram_id']
        }

    logger.info(f"✅ Licença válida — Tipo: {owner['license_type']}")
    return {
        'valida': True,
        'tipo': owner['license_type'],
        'owner_id': owner['telegram_id'],
        'installation_id': owner['installation_id'],
        'white_label': bool(owner['white_label_enabled']),
        'criado_em': owner['criado_em']
    }


async def verificar_integridade_completa() -> dict:
    """Verificação completa de integridade do sistema."""
    resultados = {
        'owner_ok': False,
        'hash_ok': False,
        'signature_ok': False,
        'installation_ok': False,
        'erros': []
    }

    owner = await buscar_owner()
    if not owner:
        resultados['erros'].append("Nenhum owner encontrado")
        return resultados

    resultados['owner_ok'] = True

    # Hash
    hash_esperado = gerar_hash_seguranca(str(owner['telegram_id']))
    resultados['hash_ok'] = (owner['hash_verificacao'] == hash_esperado)
    if not resultados['hash_ok']:
        resultados['erros'].append("Hash de verificação inválido")

    # Signature
    sig_esperada = gerar_hash_seguranca(f"{owner['telegram_id']}:owner:master")
    resultados['signature_ok'] = (owner['signature_hash'] == sig_esperada)
    if not resultados['signature_ok']:
        resultados['erros'].append("Assinatura digital inválida")

    # Installation ID
    resultados['installation_ok'] = bool(owner.get('installation_id'))
    if not resultados['installation_ok']:
        resultados['erros'].append("Installation ID ausente")

    return resultados


def gerar_chave_licenca(owner_id: int, tipo: str) -> str:
    """Gera chave de licença baseada no owner e tipo."""
    dados = f"{owner_id}:{tipo}:{datetime.now().strftime('%Y%m')}"
    return gerar_hash_seguranca(dados)[:32].upper()
