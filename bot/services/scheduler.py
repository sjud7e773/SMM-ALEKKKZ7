"""
Tarefas agendadas.
===================
Atualização automática de status, sincronização de serviços,
verificação de pagamentos e notificações.
"""

import asyncio
from bot.utils.logger import logger


async def atualizar_status_pedidos(bot):
    """Atualiza status de todos os pedidos pendentes via API.
    Usa batch multi-status (até 100 por requisição) conforme API."""
    from bot.database.queries import buscar_pedidos_pendentes, atualizar_status_pedido, buscar_usuario_por_id
    from bot.services.smm_api import ver_multi_status
    from bot.utils.helpers import status_emoji

    try:
        pedidos = await buscar_pedidos_pendentes()
        if not pedidos:
            return

        logger.info(f"🔄 Atualizando status de {len(pedidos)} pedidos...")

        # Agrupar em lotes de até 100 (limite da API)
        pedidos_com_api = [p for p in pedidos if p.get('order_id_api')]
        for i in range(0, len(pedidos_com_api), 100):
            lote = pedidos_com_api[i:i+100]
            order_ids = [p['order_id_api'] for p in lote]

            # Consulta multi-status em uma só requisição
            resultado = await ver_multi_status(order_ids)

            if not isinstance(resultado, dict) or 'error' in resultado:
                logger.warning(f"⚠️ Falha no batch status: {resultado}")
                continue

            for pedido in lote:
                try:
                    oid = str(pedido['order_id_api'])
                    dados = resultado.get(oid, {})

                    if not dados or 'error' in dados:
                        continue

                    status_api = dados.get('status', '')
                    start_count = int(dados.get('start_count', 0))
                    remains = int(dados.get('remains', 0))

                    # Mapear status
                    status_local = status_api
                    if status_api in ('Completed',):
                        status_local = 'concluido'
                    elif status_api in ('Canceled', 'Refunded'):
                        status_local = 'cancelado'
                    elif status_api in ('In progress', 'Processing'):
                        status_local = 'em_andamento'
                    elif status_api in ('Partial',):
                        status_local = 'parcial'

                    # Só atualiza se mudou
                    if status_local != pedido.get('status') or status_api != pedido.get('status_api'):
                        await atualizar_status_pedido(
                            pedido['id'], status_local, status_api, start_count, remains
                        )

                        # Notificar usuário se concluído/parcial/cancelado
                        if status_local in ('concluido', 'parcial', 'cancelado'):
                            try:
                                usuario = await buscar_usuario_por_id(pedido['usuario_id'])
                                if usuario:
                                    emoji = status_emoji(status_api)
                                    msg = (
                                        f"📦 <b>Pedido #{pedido['id']} atualizado!</b>\n\n"
                                        f"📋 Status: {status_api}\n"
                                        f"🔗 Link: {pedido['link']}\n"
                                        f"📊 Quantidade: {pedido['quantidade']}"
                                    )
                                    if remains > 0:
                                        msg += f"\n⚠️ Restantes: {remains}"
                                    await bot.send_message(
                                        usuario['telegram_id'], msg,
                                        parse_mode='HTML'
                                    )
                            except Exception as e:
                                logger.warning(f"⚠️ Não foi possível notificar usuário: {e}")

                except Exception as e:
                    logger.error(f"❌ Erro ao processar pedido #{pedido.get('id')}: {e}")

            # Delay entre lotes
            await asyncio.sleep(1)

        logger.info("✅ Atualização de status concluída.")

    except Exception as e:
        logger.error(f"❌ Erro na atualização de status: {e}")


async def sincronizar_servicos_periodico():
    """Sincroniza serviços do painel SMM periodicamente."""
    from bot.services.smm_api import listar_servicos
    from bot.database.queries import sincronizar_servicos
    from bot.config import get_config

    try:
        api_key = await get_config('api_key', '')
        if not api_key:
            return

        servicos = await listar_servicos(forcar=True)
        if servicos:
            await sincronizar_servicos(servicos)
            logger.info(f"🔄 Sincronização periódica: {len(servicos)} serviços.")
    except Exception as e:
        logger.error(f"❌ Erro na sincronização periódica: {e}")


async def verificar_pagamentos_pendentes(bot):
    """Verifica e atualiza pagamentos pendentes."""
    from bot.database.queries import (buscar_pagamentos_pendentes, atualizar_pagamento,
                                       atualizar_saldo, buscar_usuario_por_id)
    from bot.services.mercadopago import verificar_pagamento as mp_verificar
    from bot.services.hoopay import verificar_pagamento as hp_verificar

    try:
        pagamentos = await buscar_pagamentos_pendentes()
        if not pagamentos:
            return

        for pag in pagamentos:
            try:
                ref = pag.get('referencia_externa', '')
                if not ref:
                    continue

                # Verificar baseado no gateway
                if pag['gateway'] == 'mercadopago':
                    resultado = await mp_verificar(ref)
                elif pag['gateway'] == 'hoopay':
                    resultado = await hp_verificar(ref)
                else:
                    continue

                if resultado.get('aprovado'):
                    # Aprovar pagamento
                    await atualizar_pagamento(pag['id'], 'aprovado')

                    # Creditar saldo
                    usuario = await buscar_usuario_por_id(pag['usuario_id'])
                    if usuario:
                        await atualizar_saldo(usuario['telegram_id'], pag['valor'])

                        # Notificar
                        try:
                            await bot.send_message(
                                usuario['telegram_id'],
                                f"✅ <b>Pagamento confirmado!</b>\n\n"
                                f"💰 Valor: R$ {pag['valor']:.2f}\n"
                                f"📊 Novo saldo disponível!\n\n"
                                f"Use /saldo para ver seu saldo.",
                                parse_mode='HTML'
                            )
                        except Exception:
                            pass

                        logger.info(f"✅ Pagamento #{pag['id']} aprovado - R$ {pag['valor']:.2f}")

                elif resultado.get('status') in ('cancelled', 'rejected', 'expired'):
                    await atualizar_pagamento(pag['id'], 'cancelado')

                await asyncio.sleep(0.3)

            except Exception as e:
                logger.error(f"❌ Erro ao verificar pagamento #{pag.get('id')}: {e}")

    except Exception as e:
        logger.error(f"❌ Erro na verificação de pagamentos: {e}")


async def iniciar_scheduler(bot):
    """Inicia todas as tarefas agendadas."""
    from bot.config import get_config

    logger.info("⏰ Iniciando scheduler de tarefas...")

    ciclo = 0
    ultimo_backup = 0

    while True:
        try:
            # Intervalo de verificação de status
            status_min = int(await get_config('status_check_minutos', '5'))
            sync_min = int(await get_config('sync_intervalo_minutos', '60'))

            # Executar tarefas principais
            await atualizar_status_pedidos(bot)
            await verificar_pagamentos_pendentes(bot)

            # Verificar se é hora de sincronizar (a cada sync_min)
            import time
            minuto_atual = int(time.time() / 60)
            if minuto_atual % sync_min == 0:
                await sincronizar_servicos_periodico()

            # === TAREFAS SAAS ===
            # Verificar vencimento de planos (a cada 12 ciclos = ~1h com 5min/ciclo)
            ciclo += 1
            if ciclo % 12 == 0:
                try:
                    from bot.services.plan_manager import verificar_vencimentos
                    await verificar_vencimentos(bot)
                except Exception as e:
                    logger.error(f"❌ Erro na verificação de vencimentos: {e}")

            # Backup automático diário (a cada 288 ciclos = ~24h com 5min/ciclo)
            if ciclo % 288 == 0:
                try:
                    from bot.database.connection import fazer_backup
                    from bot.database.queries import registrar_log
                    caminho = await fazer_backup()
                    await registrar_log('sistema', f'Backup automático: {caminho}')
                    logger.info(f"💾 Backup automático criado: {caminho}")
                except Exception as e:
                    logger.error(f"❌ Erro no backup automático: {e}")

            # Resetar contadores mensais (1º dia do mês)
            from datetime import datetime
            agora = datetime.now()
            if agora.day == 1 and agora.hour == 0 and ciclo % 12 == 0:
                try:
                    from bot.services.plan_manager import resetar_contadores_mensais
                    await resetar_contadores_mensais()
                except Exception as e:
                    logger.error(f"❌ Erro ao resetar contadores mensais: {e}")

            # Esperar até próximo ciclo
            await asyncio.sleep(status_min * 60)

        except asyncio.CancelledError:
            logger.info("⏰ Scheduler encerrado.")
            break
        except Exception as e:
            logger.error(f"❌ Erro no scheduler: {e}")
            await asyncio.sleep(60)
