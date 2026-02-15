"""
Detector Inteligente de Plataformas.
=====================================
Analisa service.name e service.category para determinar plataforma.
Evita mistura de serviços e organiza hierarquicamente.
"""

import re
from typing import Optional


# Mapeamento de palavr as-chave para plataformas
PLATFORM_KEYWORDS = {
    'instagram': ['instagram', 'insta', 'ig ', ' ig'],
    'tiktok': ['tiktok', 'tik tok', 'tt '],
    'youtube': ['youtube', 'yt ', ' yt', 'views', 'subscribers'],
    'telegram': ['telegram', 'tg ', ' tg', 'members'],
    'facebook': ['facebook', 'fb ', ' fb', 'like', 'page'],
    'twitter': ['twitter', 'x.com', 'tweet', 'followers'],
    'kwai': ['kwai'],
    'spotify': ['spotify', 'streams', 'plays'],
    'twitch': ['twitch'],
    'discord': ['discord'],
    'whatsapp': ['whatsapp', 'wpp'],
    'linkedin': ['linkedin'],
    'pinterest': ['pinterest'],
    'snapchat': ['snapchat', 'snap'],
    'reddit': ['reddit'],
    'vimeo': ['vimeo'],
    'soundcloud': ['soundcloud'],
}


def detectar_plataforma(service_name: str, service_category: str = '') -> str:
    """
    Detecta a plataforma do serviço usando nome e categoria.
    
    Args:
        service_name: Nome do serviço da API
        service_category: Categoria do serviço da API
        
    Returns:
        Nome da plataforma ou 'Outros' se não detectado
        
    Exemplos:
        >>> detectar_plataforma("Instagram Followers - Real")
        'Instagram'
        >>> detectar_plataforma("TikTok Views", "Views")
        'TikTok'
        >>> detectar_plataforma("YouTube Subscribers")
        'YouTube'
    """
    # Normalizar para busca
    texto_busca = f"{service_name} {service_category}".lower()
    
    # Buscar por palavras-chave
    for plataforma, keywords in PLATFORM_KEYWORDS.items():
        for keyword in keywords:
            if keyword in texto_busca:
                return plataforma.capitalize()
    
    # Fallback: "Outros"
    return 'Outros'


def agrupar_por_plataforma(servicos: list) -> dict:
    """
    Agrupa serviços por plataforma detectada.
    
    Args:
        servicos: Lista de dicts com 'nome', 'category', etc
        
    Returns:
        Dict {plataforma: [servicos]}
        
    Example:
        >>> servicos = [
        ...     {'nome': 'Instagram Followers', 'category': 'Followers'},
        ...     {'nome': 'TikTok Views', 'category': 'Views'},
        ...     {'nome': 'Instagram Likes', 'category': 'Likes'}
        ... ]
        >>> grupos = agrupar_por_plataforma(servicos)
        >>> list(grupos.keys())
        ['Instagram', 'Tiktok']
        >>> len(grupos['Instagram'])
        2
    """
    grupos = {}
    
    for servico in servicos:
        nome = servico.get('nome') or servico.get('nome_custom', '')
        categoria = servico.get('category', '')
        
        plataforma = detectar_plataforma(nome, categoria)
        
        if plataforma not in grupos:
            grupos[plataforma] = []
        
        grupos[plataforma].append(servico)
    
    # Ordenar: plataformas principais primeiro, "Outros" por último
    plataformas_ordenadas = sorted(
        grupos.keys(),
        key=lambda x: (x == 'Outros', x)
    )
    
    return {p: grupos[p] for p in plataformas_ordenadas}


def obter_emoji_plataforma(plataforma: str) -> str:
    """Retorna emoji representativo da plataforma."""
    emojis = {
        'Instagram': '📸',
        'Tiktok': '🎵',
        'Youtube': '▶️',
        'Telegram': '✈️',
        'Facebook': '📘',
        'Twitter': '🐦',
        'Kwai': '🎬',
        'Spotify': '🎧',
        'Twitch': '🎮',
        'Discord': '💬',
        'Whatsapp': '💚',
        'Linkedin': '💼',
        'Pinterest': '📌',
        'Snapchat': '👻',
        'Reddit': '🤖',
        'Outros': '🌐'
    }
    return emojis.get(plataforma, '🌐')
