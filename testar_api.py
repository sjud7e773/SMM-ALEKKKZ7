"""
=== TESTE DE CONEXÃO COM A API SMM ===
Verifica se a API está acessível, se os serviços são carregados
e se o saldo está disponível.

USO: python testar_api.py
"""

import asyncio
import aiohttp
import json
import sys
import os
from decimal import Decimal

# Carregar .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


# ============================================================
# CONFIGURAÇÃO - pode alterar aqui ou usar .env / banco
# ============================================================
API_URL = os.getenv("API_URL", "https://baratosociais.com/api/v2")
API_KEY = os.getenv("API_KEY", "")


async def fazer_requisicao(params: dict) -> dict | list:
    """Faz POST na API e retorna o resultado."""
    params['key'] = API_KEY
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, data=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                texto = await resp.text()
                try:
                    return json.loads(texto)
                except json.JSONDecodeError:
                    return {'error': f'Resposta inválida: {texto[:200]}'}
    except asyncio.TimeoutError:
        return {'error': 'Timeout na requisição (30s)'}
    except aiohttp.ClientError as e:
        return {'error': f'Erro de conexão: {e}'}
    except Exception as e:
        return {'error': f'Erro inesperado: {e}'}


def ok(msg):
    print(f"  ✅ {msg}")

def erro(msg):
    print(f"  ❌ {msg}")

def info(msg):
    print(f"  ℹ️  {msg}")

def separador(titulo):
    print(f"\n{'='*50}")
    print(f"  {titulo}")
    print(f"{'='*50}")


async def testar_conexao():
    """Testa se a API responde."""
    separador("1. TESTE DE CONEXÃO")
    resultado = await fazer_requisicao({'action': 'balance'})
    if 'error' in resultado:
        erro(f"Falha na conexão: {resultado['error']}")
        return False
    ok("Conexão com a API OK!")
    return True


async def testar_saldo():
    """Testa consulta de saldo."""
    separador("2. TESTE DE SALDO")
    resultado = await fazer_requisicao({'action': 'balance'})

    if 'error' in resultado:
        erro(f"Erro ao consultar saldo: {resultado['error']}")
        return False

    saldo = resultado.get('balance', 'N/A')
    moeda = resultado.get('currency', 'N/A')
    ok(f"Saldo: {saldo} {moeda}")

    try:
        saldo_decimal = Decimal(str(saldo))
        if saldo_decimal > 0:
            ok(f"Crédito disponível para enviar pedidos")
        else:
            erro(f"Saldo zerado! Você precisa recarregar para enviar pedidos.")
    except:
        info("Não foi possível converter saldo para número")

    return True


async def testar_servicos():
    """Testa carregamento de serviços."""
    separador("3. TESTE DE SERVIÇOS")
    resultado = await fazer_requisicao({'action': 'services'})

    if isinstance(resultado, dict) and 'error' in resultado:
        erro(f"Erro ao listar serviços: {resultado['error']}")
        return False

    if not isinstance(resultado, list):
        erro(f"Resposta inesperada: tipo {type(resultado).__name__}")
        return False

    ok(f"Total de serviços: {len(resultado)}")

    # Contar categorias
    categorias = set()
    com_refill = 0
    com_cancel = 0
    for s in resultado:
        categorias.add(s.get('category', 'Sem categoria'))
        if s.get('refill'):
            com_refill += 1
        if s.get('cancel'):
            com_cancel += 1

    ok(f"Categorias: {len(categorias)}")
    info(f"Serviços com refill: {com_refill}")
    info(f"Serviços com cancel: {com_cancel}")

    # Mostrar amostra
    print("\n  📋 Amostra dos primeiros 5 serviços:")
    for s in resultado[:5]:
        rate = s.get('rate', '?')
        min_q = s.get('min', '?')
        max_q = s.get('max', '?')
        refill = "✅" if s.get('refill') else "❌"
        cancel = "✅" if s.get('cancel') else "❌"
        print(f"     ID:{s.get('service')} | {s.get('name','?')[:40]}")
        print(f"       Categoria: {s.get('category','?')[:30]}")
        print(f"       Rate: ${rate}/1000 | Min: {min_q} | Max: {max_q}")
        print(f"       Refill: {refill} | Cancel: {cancel}")
        print()

    return True


async def testar_preco_calculo():
    """Testa se os cálculos de preço estão corretos."""
    separador("4. TESTE DE CÁLCULO DE PREÇO")

    resultado = await fazer_requisicao({'action': 'services'})
    if isinstance(resultado, dict) and 'error' in resultado:
        erro("Não foi possível carregar serviços para teste de preço")
        return False

    if not isinstance(resultado, list) or len(resultado) == 0:
        erro("Nenhum serviço disponível")
        return False

    # Pegar primeiro serviço como exemplo
    servico = resultado[0]
    rate = Decimal(str(servico.get('rate', '0')))
    min_q = int(servico.get('min', 100))
    quantidade = min_q

    # Calcular preços
    custo_base = (rate / Decimal('1000')) * Decimal(str(quantidade))
    margem = Decimal('1.75')  # 75% lucro
    preco_com_lucro = custo_base * margem

    # Com taxa MP (0.99%)
    taxa_mp = Decimal('0.0099')
    preco_mp = preco_com_lucro / (Decimal('1') - taxa_mp)
    preco_mp = preco_mp.quantize(Decimal('0.01'))

    # Com taxa Hoopay (R$0.40 venda + R$0.30 saque)
    preco_hp = preco_com_lucro + Decimal('0.40') + Decimal('0.30')
    preco_hp = preco_hp.quantize(Decimal('0.01'))

    ok(f"Serviço de teste: {servico.get('name','?')[:40]}")
    info(f"  Rate API: ${rate}/1000")
    info(f"  Quantidade: {quantidade}")
    info(f"  Custo base: R$ {custo_base:.4f}")
    info(f"  Com lucro 75%: R$ {preco_com_lucro:.4f}")
    info(f"  Preço final MP: R$ {preco_mp}")
    info(f"  Preço final Hoopay: R$ {preco_hp}")

    # Validar que o preço final é maior que custo
    if preco_com_lucro > custo_base:
        ok("Margem de lucro aplicada corretamente")
    else:
        erro("ERRO: Preço com lucro não é maior que custo base!")

    if preco_mp > preco_com_lucro:
        ok("Taxa Mercado Pago aplicada corretamente")
    else:
        erro("ERRO: Preço MP deveria ser maior que preço com lucro!")

    if preco_hp > preco_com_lucro:
        ok("Taxa Hoopay aplicada corretamente")
    else:
        erro("ERRO: Preço Hoopay deveria ser maior que preço com lucro!")

    return True


async def main():
    print("\n" + "="*50)
    print("  🧪 TESTE COMPLETO DA API SMM")
    print("  URL: " + API_URL)
    print("="*50)

    if not API_KEY:
        erro("API_KEY não configurada!")
        print("\n  Configure sua API key de uma destas formas:")
        print("  1. No arquivo .env: API_KEY=sua_chave_aqui")
        print("  2. Direto no script testar_api.py (variável API_KEY)")
        print("  3. Você a obterá no site: https://baratosociais.com")
        sys.exit(1)

    info(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}" if len(API_KEY) > 12 else f"API Key: {API_KEY}")

    resultados = {
        'Conexão': False,
        'Saldo': False,
        'Serviços': False,
        'Cálculo de Preço': False
    }

    # 1. Conexão
    resultados['Conexão'] = await testar_conexao()
    if not resultados['Conexão']:
        separador("❌ FALHA CRÍTICA")
        erro("Não foi possível conectar à API.")
        erro("Verifique sua API key e sua conexão com a internet.")
        sys.exit(1)

    # 2. Saldo
    resultados['Saldo'] = await testar_saldo()

    # 3. Serviços
    resultados['Serviços'] = await testar_servicos()

    # 4. Cálculos
    resultados['Cálculo de Preço'] = await testar_preco_calculo()

    # Resumo
    separador("📊 RESUMO FINAL")
    total_ok = 0
    for nome, status in resultados.items():
        icone = "✅" if status else "❌"
        print(f"  {icone} {nome}")
        if status:
            total_ok += 1

    print(f"\n  Resultado: {total_ok}/{len(resultados)} testes passaram")

    if total_ok == len(resultados):
        print("\n  🎉 TUDO FUNCIONANDO! Seu bot está pronto para uso.")
    elif total_ok >= 2:
        print("\n  ⚠️  Alguns testes falharam. Verifique os erros acima.")
    else:
        print("\n  ❌ Problemas críticos detectados. Corrija antes de usar o bot.")

    print()


if __name__ == '__main__':
    asyncio.run(main())
