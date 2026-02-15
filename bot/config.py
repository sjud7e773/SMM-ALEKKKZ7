"""
Gerenciamento de configuração.
===============================
Carrega config do .env e do banco de dados.
Config do banco sobrepõe .env.
Suporta hierarquia: Owner > Admin > Usuário.
"""

import os
import hashlib
from dotenv import load_dotenv
from bot.utils.logger import logger

# Carrega .env
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_PATH)

# Timezone fixo
TIMEZONE = 'America/Sao_Paulo'

# Cache de configurações
_config_cache: dict = {}


def invalidar_cache():
    """Limpa cache de configurações. Chamar após mudanças críticas."""
    global _config_cache
    _config_cache = {}


def get_env(chave: str, padrao: str = '') -> str:
    """Obtém variável de ambiente."""
    return os.getenv(chave, padrao)


async def carregar_configs():
    """Carrega todas as configurações do banco para cache."""
    global _config_cache
    from bot.database.queries import get_todas_configs
    try:
        _config_cache = await get_todas_configs()
        logger.info(f"✅ {len(_config_cache)} configurações carregadas do banco.")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar configs do banco: {e}")
        _config_cache = {}


async def get_config(chave: str, padrao: str = '') -> str:
    """Obtém configuração (banco > env > padrão)."""
    # Primeiro verifica cache do banco
    if chave in _config_cache and _config_cache[chave]:
        return _config_cache[chave]

    # Depois verifica banco diretamente
    from bot.database.queries import get_config as db_get_config
    try:
        valor = await db_get_config(chave)
        if valor:
            _config_cache[chave] = valor
            return valor
    except Exception:
        pass

    # Finalmente verifica .env
    env_valor = get_env(chave.upper(), padrao)
    return env_valor


async def set_config(chave: str, valor: str):
    """Define configuração no banco e atualiza cache."""
    from bot.database.queries import set_config as db_set_config
    await db_set_config(chave, valor)
    _config_cache[chave] = valor


def get_bot_token() -> str:
    """Retorna token do bot (prioridade: cache > env)."""
    if 'bot_token' in _config_cache and _config_cache['bot_token']:
        return _config_cache['bot_token']
    return get_env('BOT_TOKEN', '')


async def is_owner(telegram_id: int) -> bool:
    """Verifica se o usuário é o dono (owner) do sistema."""
    from bot.database.queries_owner import buscar_owner
    try:
        owner = await buscar_owner()
        if not owner:
            return False
        return int(owner['telegram_id']) == int(telegram_id)
    except Exception:
        return False


async def is_admin(telegram_id: int) -> bool:
    """
    Verifica se o usuário é admin (cliente pagante) OU owner.
    
    CRÍTICO: Owner SEMPRE tem acesso admin total e irrestrito.
    Owner NUNCA depende da tabela admins.
    Owner NUNCA é bloqueado por status de plano.
    """
    # PRIORIDADE MÁXIMA: Owner sempre é admin, sem exceções
    if await is_owner(telegram_id):
        return True

    # Verificar na tabela admins (apenas para não-owners)
    from bot.database.queries_owner import buscar_admin_por_telegram_id
    try:
        admin = await buscar_admin_por_telegram_id(telegram_id)
        if not admin:
            return False
        return admin['status'] == 'ativo'
    except Exception:
        # Fallback para sistema legado (config admin_id)
        admin_id = await get_config('admin_id', '')
        if admin_id:
            return str(telegram_id) == str(admin_id)
        return False


async def sistema_configurado() -> bool:
    """Verifica se o sistema já foi configurado (owner definido)."""
    from bot.database.queries_owner import buscar_owner
    try:
        owner = await buscar_owner()
        if owner:
            return True
    except Exception:
        pass
    # Fallback legado
    admin_id = await get_config('admin_id', '')
    return bool(admin_id)


def invalidar_cache():
    """Limpa cache de configurações."""
    global _config_cache
    _config_cache = {}


def gerar_hash_seguranca(dados: str) -> str:
    """Gera hash SHA256 para verificação de integridade."""
    chave_interna = "SMM_SAAS_PLATFORM_2026_SECURE"
    conteudo = f"{chave_interna}:{dados}:{chave_interna}"
    return hashlib.sha256(conteudo.encode()).hexdigest()


def verificar_hash(dados: str, hash_esperado: str) -> bool:
    """Verifica se o hash corresponde aos dados."""
    return gerar_hash_seguranca(dados) == hash_esperado
