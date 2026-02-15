"""
Motor de cálculo de preços.
=============================
Usa Decimal para precisão absoluta.
NÃO há arredondamento prematuro, NÃO há conflito de taxas.
"""

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from bot.utils.logger import logger


def decimal_seguro(valor) -> Decimal:
    """Converte qualquer valor para Decimal de forma segura."""
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def calcular_custo_base(rate: float, quantidade: int) -> Decimal:
    """
    Calcula o custo base do serviço.
    FÓRMULA: (rate / 1000) * quantidade
    """
    rate_d = decimal_seguro(rate)
    qtd_d = decimal_seguro(quantidade)
    custo = (rate_d / Decimal('1000')) * qtd_d
    return custo


def calcular_preco_com_lucro(custo_base: Decimal, margem_pct: float = 75.0) -> Decimal:
    """
    Aplica margem de lucro ao custo base.
    FÓRMULA: custo_base * (1 + margem/100)
    Margem 75% = custo_base * 1.75
    """
    margem_d = decimal_seguro(margem_pct)
    multiplicador = Decimal('1') + (margem_d / Decimal('100'))
    preco = custo_base * multiplicador
    return preco


def calcular_preco_final_mercadopago(preco_com_lucro: Decimal, taxa_venda_pct: float = 0.99) -> Decimal:
    """
    Calcula preço final com taxa do Mercado Pago (percentual).
    A taxa é SOBRE o valor, então o cliente paga mais para cobrir.
    FÓRMULA: preco_com_lucro / (1 - taxa/100)
    Isso garante que após o Mercado Pago descontar a taxa,
    o vendedor recebe exatamente o preco_com_lucro.
    """
    taxa_d = decimal_seguro(taxa_venda_pct) / Decimal('100')
    divisor = Decimal('1') - taxa_d
    preco_final = preco_com_lucro / divisor
    # Arredonda para cima com 2 casas
    return preco_final.quantize(Decimal('0.01'), rounding=ROUND_CEILING)


def calcular_preco_final_hoopay(preco_com_lucro: Decimal,
                                  taxa_venda: float = 0.40,
                                  taxa_saque: float = 0.30) -> Decimal:
    """
    Calcula preço final com taxas da Hoopay (fixas).
    FÓRMULA: preco_com_lucro + taxa_venda + taxa_saque
    """
    taxa_total = decimal_seguro(taxa_venda) + decimal_seguro(taxa_saque)
    preco_final = preco_com_lucro + taxa_total
    # Arredonda para cima com 2 casas
    return preco_final.quantize(Decimal('0.01'), rounding=ROUND_CEILING)


async def calcular_preco_completo(rate: float, quantidade: int,
                                    gateway: str = 'mercadopago',
                                    margem_custom: float = None,
                                    markup_servico: float = None) -> dict:
    """
    Calcula todos os componentes de preço de uma vez.
    Retorna dict com todos os valores para transparência total.

    Prioridade de margem: markup_servico > margem_custom > margem do banco
    """
    from bot.config import get_config
    from bot.database.queries import buscar_gateway

    # Determinar margem
    if markup_servico is not None:
        margem = markup_servico
    elif margem_custom is not None:
        margem = margem_custom
    else:
        margem_str = await get_config('margem_lucro', '75')
        margem = float(margem_str)

    # Calcular custo base
    custo_base = calcular_custo_base(rate, quantidade)

    # Calcular preço com lucro
    preco_com_lucro = calcular_preco_com_lucro(custo_base, margem)

    # Buscar taxas do gateway
    gw = await buscar_gateway(gateway)

    # Calcular preço final baseado no gateway
    if gateway == 'mercadopago':
        taxa_pct = gw['taxa_venda'] if gw else 0.99
        preco_final = calcular_preco_final_mercadopago(preco_com_lucro, taxa_pct)
        taxa_valor = preco_final - preco_com_lucro
        taxa_info = f"{taxa_pct}%"
    elif gateway == 'hoopay':
        taxa_venda = gw['taxa_venda'] if gw else 0.40
        taxa_saque = gw['taxa_saque'] if gw else 0.30
        preco_final = calcular_preco_final_hoopay(preco_com_lucro, taxa_venda, taxa_saque)
        taxa_valor = decimal_seguro(taxa_venda) + decimal_seguro(taxa_saque)
        taxa_info = f"R$ {float(taxa_valor):.2f} (fixa)"
    else:
        # Gateway desconhecido - sem taxa adicional
        preco_final = preco_com_lucro.quantize(Decimal('0.01'), rounding=ROUND_CEILING)
        taxa_valor = Decimal('0')
        taxa_info = "Nenhuma"

    # Arredondar custo e lucro para exibição
    custo_base_r = custo_base.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    preco_com_lucro_r = preco_com_lucro.quantize(Decimal('0.01'), rounding=ROUND_CEILING)
    lucro = preco_com_lucro_r - custo_base_r
    taxa_valor_r = taxa_valor.quantize(Decimal('0.01'), rounding=ROUND_CEILING)

    resultado = {
        'rate': float(rate),
        'quantidade': quantidade,
        'margem_pct': margem,
        'gateway': gateway,
        'custo_base': float(custo_base_r),
        'preco_com_lucro': float(preco_com_lucro_r),
        'lucro': float(lucro),
        'taxa_gateway': float(taxa_valor_r),
        'taxa_info': taxa_info,
        'preco_final': float(preco_final),
    }

    logger.debug(f"💰 Cálculo: rate={rate}, qty={quantidade}, margem={margem}%, "
                 f"custo={resultado['custo_base']}, lucro={resultado['lucro']}, "
                 f"taxa={resultado['taxa_gateway']}, final={resultado['preco_final']}")

    return resultado


def calcular_preco_minimo(rate: float, min_quantidade: int,
                           margem: float = 75.0, gateway: str = 'mercadopago') -> float:
    """Calcula o preço mínimo (quantidade mínima) para exibição."""
    custo_base = calcular_custo_base(rate, min_quantidade)
    preco_lucro = calcular_preco_com_lucro(custo_base, margem)

    if gateway == 'mercadopago':
        preco_final = calcular_preco_final_mercadopago(preco_lucro)
    elif gateway == 'hoopay':
        preco_final = calcular_preco_final_hoopay(preco_lucro)
    else:
        preco_final = preco_lucro.quantize(Decimal('0.01'), rounding=ROUND_CEILING)

    return float(preco_final)


def calcular_preco_por_mil(rate: float, margem: float = 75.0, gateway: str = 'mercadopago') -> float:
    """Calcula preço por 1000 unidades para exibição em catálogo."""
    return calcular_preco_minimo(rate, 1000, margem, gateway)
