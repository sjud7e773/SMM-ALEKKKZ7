"""
Sistema de Upsell.
===================
Ofertas inteligentes após compras.
"""

from bot.database.queries import buscar_servico
from bot.utils.logger import logger
from bot.database.connection import get_db


async def buscar_upsell(servico_id: int, categoria: str = '') -> dict | None:
    """
    Busca oferta de upsell para um serviço/categoria.
    Retorna: {servico_destino, desconto_pct, mensagem} ou None.
    """
    db = await get_db()
    try:
        # Primeiro tenta por serviço específico
        cursor = await db.execute(
            """SELECT * FROM upsell_regras WHERE servico_origem_id = ? AND ativo = 1
               ORDER BY desconto_pct DESC LIMIT 1""",
            (servico_id,)
        )
        regra = await cursor.fetchone()

        # Se não encontrou, tenta por categoria
        if not regra and categoria:
            cursor = await db.execute(
                """SELECT * FROM upsell_regras WHERE categoria_origem = ? AND ativo = 1
                   AND servico_origem_id IS NULL
                   ORDER BY desconto_pct DESC LIMIT 1""",
                (categoria,)
            )
            regra = await cursor.fetchone()

        # Se não encontrou nenhuma, tenta regra genérica
        if not regra:
            cursor = await db.execute(
                """SELECT * FROM upsell_regras WHERE servico_origem_id IS NULL
                   AND (categoria_origem IS NULL OR categoria_origem = '') AND ativo = 1
                   ORDER BY desconto_pct DESC LIMIT 1"""
            )
            regra = await cursor.fetchone()

        if regra:
            regra = dict(regra)
            servico_dest = await buscar_servico(regra['servico_destino_id'])
            if servico_dest and servico_dest['ativo']:
                return {
                    'regra_id': regra['id'],
                    'servico_destino': servico_dest,
                    'desconto_pct': regra['desconto_pct'],
                    'mensagem': regra['mensagem'] or '🎁 Oferta especial!',
                }
        return None
    finally:
        await db.close()


async def criar_regra_upsell(servico_origem_id: int | None, categoria_origem: str,
                               servico_destino_id: int, desconto_pct: float,
                               mensagem: str = '') -> dict:
    """Cria uma nova regra de upsell."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO upsell_regras (servico_origem_id, categoria_origem,
               servico_destino_id, desconto_pct, mensagem)
               VALUES (?, ?, ?, ?, ?)""",
            (servico_origem_id, categoria_origem, servico_destino_id,
             desconto_pct, mensagem)
        )
        await db.commit()
        return {'id': cursor.lastrowid, 'sucesso': True}
    finally:
        await db.close()


async def listar_regras_upsell() -> list:
    """Lista todas as regras de upsell."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM upsell_regras ORDER BY id")
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def toggle_regra_upsell(regra_id: int, ativo: bool):
    """Ativa/desativa uma regra de upsell."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE upsell_regras SET ativo = ? WHERE id = ?",
            (1 if ativo else 0, regra_id)
        )
        await db.commit()
    finally:
        await db.close()


async def deletar_regra_upsell(regra_id: int):
    """Deleta uma regra de upsell."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM upsell_regras WHERE id = ?", (regra_id,))
        await db.commit()
    finally:
        await db.close()
