"""
Queries do banco de dados — Owner/Admin/Plans.
================================================
CRUD para tabelas do sistema SaaS:
- owners: dono do sistema (apenas 1)
- admins: clientes pagantes
- plans: planos disponíveis
"""

from datetime import datetime, timedelta
from bot.database.connection import get_db
from bot.utils.logger import logger


# ==========================================
# OWNERS
# ==========================================

async def buscar_owner():
    """Busca o dono do sistema (deve haver apenas 1)."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM owners LIMIT 1")
        row = await cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"❌ Erro ao buscar owner: {e}")
        return None
    finally:
        await db.close()


async def criar_owner(telegram_id: int, nome: str, username: str,
                      hash_verificacao: str, signature_hash: str,
                      installation_id: str) -> dict:
    """Cria o dono do sistema (apenas 1 permitido)."""
    db = await get_db()
    try:
        # Verificar se já existe um owner
        existing = await db.execute("SELECT id FROM owners LIMIT 1")
        if await existing.fetchone():
            raise ValueError("Já existe um dono cadastrado no sistema.")

        await db.execute("""
            INSERT INTO owners (telegram_id, nome, username, hash_verificacao,
                               signature_hash, installation_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (telegram_id, nome, username, hash_verificacao,
              signature_hash, installation_id))
        await db.commit()

        cursor = await db.execute("SELECT * FROM owners WHERE telegram_id = ?",
                                  (telegram_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def atualizar_owner(**kwargs) -> bool:
    """Atualiza campos do owner."""
    db = await get_db()
    try:
        campos = []
        valores = []
        for chave, valor in kwargs.items():
            campos.append(f"{chave} = ?")
            valores.append(valor)

        if not campos:
            return False

        query = f"UPDATE owners SET {', '.join(campos)} WHERE id = 1"
        await db.execute(query, valores)
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar owner: {e}")
        return False
    finally:
        await db.close()


# ==========================================
# ADMINS
# ==========================================

async def criar_admin(telegram_id: int, nome: str, username: str = '',
                      plano: str = 'basico', dias: int = 30,
                      adicionado_por: int = None) -> dict:
    """Cria um novo admin (cliente pagante)."""
    db = await get_db()
    try:
        # Buscar limites do plano
        plan = await _buscar_plano_por_slug(db, plano)

        agora = datetime.now()
        vencimento = agora + timedelta(days=dias)

        await db.execute("""
            INSERT INTO admins (telegram_id, nome, username, plano, dias_plano,
                               data_inicio, data_vencimento, limite_pedidos_mes,
                               margem_min, margem_max, adicionado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (telegram_id, nome, username, plano, dias,
              agora.isoformat(), vencimento.isoformat(),
              plan['limite_pedidos'] if plan else 500,
              plan['margem_min'] if plan else 30,
              plan['margem_max'] if plan else 500,
              adicionado_por))
        await db.commit()

        cursor = await db.execute("SELECT * FROM admins WHERE telegram_id = ?",
                                  (telegram_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def buscar_admin_por_telegram_id(telegram_id: int):
    """Busca admin pelo telegram_id."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM admins WHERE telegram_id = ?",
                                  (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def buscar_admin_por_id(admin_id: int):
    """Busca admin pelo ID interno."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM admins WHERE id = ?",
                                  (admin_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def listar_admins(status_filtro: str = None) -> list:
    """Lista todos os admins, opcionalmente filtrando por status."""
    db = await get_db()
    try:
        if status_filtro:
            cursor = await db.execute(
                "SELECT * FROM admins WHERE status = ? ORDER BY id DESC",
                (status_filtro,))
        else:
            cursor = await db.execute("SELECT * FROM admins ORDER BY id DESC")
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def atualizar_admin(telegram_id: int, **kwargs) -> bool:
    """Atualiza campos de um admin."""
    db = await get_db()
    try:
        campos = []
        valores = []
        for chave, valor in kwargs.items():
            campos.append(f"{chave} = ?")
            valores.append(valor)

        if not campos:
            return False

        campos.append("atualizado_em = ?")
        valores.append(datetime.now().isoformat())
        valores.append(telegram_id)

        query = f"UPDATE admins SET {', '.join(campos)} WHERE telegram_id = ?"
        result = await db.execute(query, valores)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar admin {telegram_id}: {e}")
        return False
    finally:
        await db.close()


async def remover_admin(telegram_id: int) -> bool:
    """Remove um admin."""
    db = await get_db()
    try:
        result = await db.execute("DELETE FROM admins WHERE telegram_id = ?",
                                  (telegram_id,))
        await db.commit()
        return result.rowcount > 0
    finally:
        await db.close()


async def bloquear_admin(telegram_id: int) -> bool:
    """Bloqueia um admin."""
    return await atualizar_admin(telegram_id, status='bloqueado')


async def desbloquear_admin(telegram_id: int) -> bool:
    """Desbloqueia um admin (reativa)."""
    return await atualizar_admin(telegram_id, status='ativo')


async def definir_plano_admin(telegram_id: int, slug_plano: str,
                              dias: int = None) -> bool:
    """Define o plano de um admin. Renova data de início/vencimento."""
    db = await get_db()
    try:
        plan = await _buscar_plano_por_slug(db, slug_plano)
        if not plan:
            return False

        dias_val = dias if dias else plan['dias']
        agora = datetime.now()
        vencimento = agora + timedelta(days=dias_val)

        await db.execute("""
            UPDATE admins SET plano = ?, dias_plano = ?, data_inicio = ?,
                data_vencimento = ?, limite_pedidos_mes = ?,
                margem_min = ?, margem_max = ?,
                pedidos_mes_atual = 0, status = 'ativo',
                atualizado_em = ?
            WHERE telegram_id = ?
        """, (slug_plano, dias_val, agora.isoformat(),
              vencimento.isoformat(), plan['limite_pedidos'],
              plan['margem_min'], plan['margem_max'],
              agora.isoformat(), telegram_id))
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao definir plano do admin {telegram_id}: {e}")
        return False
    finally:
        await db.close()


async def contar_admins() -> dict:
    """Conta admins por status."""
    db = await get_db()
    try:
        result = {'total': 0, 'ativos': 0, 'bloqueados': 0, 'vencidos': 0}
        cursor = await db.execute("SELECT COUNT(*) FROM admins")
        result['total'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COUNT(*) FROM admins WHERE status = 'ativo'")
        result['ativos'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COUNT(*) FROM admins WHERE status = 'bloqueado'")
        result['bloqueados'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COUNT(*) FROM admins WHERE status = 'vencido'")
        result['vencidos'] = (await cursor.fetchone())[0]
        return result
    finally:
        await db.close()


async def buscar_admins_vencidos() -> list:
    """Busca admins com plano vencido que ainda estão ativos."""
    db = await get_db()
    try:
        agora = datetime.now().isoformat()
        cursor = await db.execute("""
            SELECT * FROM admins
            WHERE status = 'ativo' AND data_vencimento IS NOT NULL
                AND data_vencimento < ?
        """, (agora,))
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def buscar_admins_prestes_a_vencer(dias: int = 3) -> list:
    """Busca admins cujo plano vence nos próximos X dias."""
    db = await get_db()
    try:
        agora = datetime.now()
        limite = (agora + timedelta(days=dias)).isoformat()
        cursor = await db.execute("""
            SELECT * FROM admins
            WHERE status = 'ativo' AND data_vencimento IS NOT NULL
                AND data_vencimento > ? AND data_vencimento <= ?
        """, (agora.isoformat(), limite))
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def incrementar_pedidos_admin(telegram_id: int) -> bool:
    """Incrementa contador de pedidos do mês para um admin."""
    db = await get_db()
    try:
        await db.execute("""
            UPDATE admins SET pedidos_mes_atual = pedidos_mes_atual + 1,
                atualizado_em = ?
            WHERE telegram_id = ?
        """, (datetime.now().isoformat(), telegram_id))
        await db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao incrementar pedidos do admin {telegram_id}: {e}")
        return False
    finally:
        await db.close()


async def resetar_pedidos_mensais():
    """Reseta contadores de pedidos mensais de todos os admins."""
    db = await get_db()
    try:
        await db.execute("""
            UPDATE admins SET pedidos_mes_atual = 0, atualizado_em = ?
        """, (datetime.now().isoformat(),))
        await db.commit()
        logger.info("✅ Contadores de pedidos mensais resetados.")
    finally:
        await db.close()


# ==========================================
# PLANS
# ==========================================

async def listar_planos(apenas_ativos: bool = True) -> list:
    """Lista todos os planos disponíveis."""
    db = await get_db()
    try:
        if apenas_ativos:
            cursor = await db.execute(
                "SELECT * FROM plans WHERE ativo = 1 ORDER BY preco ASC")
        else:
            cursor = await db.execute("SELECT * FROM plans ORDER BY preco ASC")
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def buscar_plano(slug: str):
    """Busca plano pelo slug."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM plans WHERE slug = ?",
                                  (slug,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def atualizar_plano(slug: str, **kwargs) -> bool:
    """Atualiza campos de um plano."""
    db = await get_db()
    try:
        campos = []
        valores = []
        for chave, valor in kwargs.items():
            campos.append(f"{chave} = ?")
            valores.append(valor)
        if not campos:
            return False
        valores.append(slug)
        query = f"UPDATE plans SET {', '.join(campos)} WHERE slug = ?"
        result = await db.execute(query, valores)
        await db.commit()
        return result.rowcount > 0
    finally:
        await db.close()


# ==========================================
# ESTATÍSTICAS GLOBAIS (Owner)
# ==========================================

async def obter_estatisticas_globais() -> dict:
    """Retorna estatísticas globais para o dono."""
    db = await get_db()
    try:
        stats = {}

        # Admins
        cursor = await db.execute("SELECT COUNT(*) FROM admins")
        stats['total_admins'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COUNT(*) FROM admins WHERE status = 'ativo'")
        stats['admins_ativos'] = (await cursor.fetchone())[0]

        # Usuários globais
        cursor = await db.execute("SELECT COUNT(*) FROM usuarios")
        stats['total_usuarios'] = (await cursor.fetchone())[0]

        # Pedidos globais
        cursor = await db.execute("SELECT COUNT(*) FROM pedidos")
        stats['total_pedidos'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COALESCE(SUM(preco_final), 0) FROM pedidos")
        stats['receita_total'] = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "SELECT COALESCE(SUM(preco_custo), 0) FROM pedidos")
        stats['custo_total'] = (await cursor.fetchone())[0]
        stats['lucro_total'] = stats['receita_total'] - stats['custo_total']

        # Pedidos hoje
        cursor = await db.execute("""
            SELECT COUNT(*) FROM pedidos
            WHERE date(criado_em) = date('now', 'localtime')
        """)
        stats['pedidos_hoje'] = (await cursor.fetchone())[0]

        return stats
    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas globais: {e}")
        return {}
    finally:
        await db.close()


# ==========================================
# HELPERS INTERNOS
# ==========================================

async def _buscar_plano_por_slug(db, slug: str):
    """Helper interno para buscar plano sem abrir nova conexão."""
    try:
        cursor = await db.execute("SELECT * FROM plans WHERE slug = ?",
                                  (slug,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
