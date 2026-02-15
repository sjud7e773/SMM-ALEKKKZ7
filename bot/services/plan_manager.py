"""
Gerenciador de Planos.
========================
Controla vencimento, renovação e limites de planos dos admins.
Executado pelo scheduler periodicamente.
"""

from datetime import datetime, timedelta
from bot.database.queries_owner import (
    buscar_admins_vencidos, buscar_admins_prestes_a_vencer,
    atualizar_admin, resetar_pedidos_mensais
)
from bot.database.queries import registrar_log
from bot.utils.logger import logger


async def verificar_vencimentos(bot=None):
    """
    Verifica e processa planos vencidos.
    - Bloqueia admins com plano vencido
    - Envia aviso 3 dias antes do vencimento
    Executado diariamente pelo scheduler.
    """
    # 1. Bloquear admins vencidos
    vencidos = await buscar_admins_vencidos()
    for admin in vencidos:
        try:
            await atualizar_admin(admin['telegram_id'], status='vencido')
            await registrar_log(
                'plano',
                f"Plano do admin {admin['telegram_id']} venceu. Status: vencido."
            )
            logger.info(f"🟡 Admin {admin['telegram_id']} — plano vencido, bloqueado.")

            # Notificar o admin via bot (se disponível)
            if bot:
                try:
                    await bot.send_message(
                        admin['telegram_id'],
                        "⚠️ <b>Seu plano venceu!</b>\n\n"
                        "Seu bot foi desativado temporariamente.\n"
                        "Entre em contato com o suporte para renovar.\n\n"
                        f"📦 Plano: <b>{admin['plano'].title()}</b>\n"
                        f"⏰ Vencimento: {admin.get('data_vencimento', 'N/A')}",
                        parse_mode='HTML'
                    )
                except Exception:
                    pass  # Admin pode ter bloqueado o bot

        except Exception as e:
            logger.error(f"❌ Erro ao bloquear admin vencido {admin['telegram_id']}: {e}")

    # 2. Avisar admins prestes a vencer (3 dias)
    prestes = await buscar_admins_prestes_a_vencer(dias=3)
    for admin in prestes:
        if bot:
            try:
                venc = admin.get('data_vencimento', 'N/A')
                await bot.send_message(
                    admin['telegram_id'],
                    "⏰ <b>Aviso de Vencimento</b>\n\n"
                    f"Seu plano <b>{admin['plano'].title()}</b> "
                    f"vence em breve!\n\n"
                    f"📅 Data: {venc[:10] if venc != 'N/A' else 'N/A'}\n\n"
                    "Entre em contato para renovar e evitar interrupções.",
                    parse_mode='HTML'
                )
                await registrar_log(
                    'plano',
                    f"Aviso de vencimento enviado para admin {admin['telegram_id']}"
                )
            except Exception:
                pass

    if vencidos:
        logger.info(f"🟡 {len(vencidos)} admin(s) bloqueado(s) por vencimento.")
    if prestes:
        logger.info(f"⏰ {len(prestes)} admin(s) avisado(s) sobre vencimento.")


async def resetar_contadores_mensais():
    """
    Reseta contadores de pedidos mensais de todos os admins.
    Executado no 1º dia de cada mês pelo scheduler.
    """
    await resetar_pedidos_mensais()
    await registrar_log('sistema', 'Contadores de pedidos mensais resetados')
    logger.info("✅ Contadores de pedidos mensais resetados.")


async def verificar_limite_pedidos(admin_telegram_id: int) -> dict:
    """
    Verifica se admin pode fazer mais pedidos.
    Retorna {'pode': bool, 'usados': int, 'limite': int, 'restantes': int}
    """
    from bot.database.queries_owner import buscar_admin_por_telegram_id
    admin = await buscar_admin_por_telegram_id(admin_telegram_id)

    if not admin:
        return {'pode': False, 'usados': 0, 'limite': 0, 'restantes': 0}

    usados = admin.get('pedidos_mes_atual', 0)
    limite = admin.get('limite_pedidos_mes', 500)
    restantes = max(0, limite - usados)

    return {
        'pode': restantes > 0,
        'usados': usados,
        'limite': limite,
        'restantes': restantes
    }
