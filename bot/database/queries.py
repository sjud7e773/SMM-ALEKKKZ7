"""
Queries do banco de dados.
===========================
Todas as operações CRUD organizadas por entidade.
"""

from bot.database.connection import get_db
from bot.utils.logger import logger
import json


# ==========================================
# USUÁRIOS
# ==========================================

async def criar_usuario(telegram_id: int, nome: str, username: str = '', indicado_por: int = None) -> dict:
    """Cria ou retorna usuário existente.
    Usa INSERT OR IGNORE para evitar UNIQUE constraint errors."""
    db = await get_db()
    try:
        # INSERT OR IGNORE: se já existe, não faz nada (sem erro)
        await db.execute(
            """INSERT OR IGNORE INTO usuarios (telegram_id, nome, username, indicado_por)
               VALUES (?, ?, ?, ?)""",
            (telegram_id, nome, username, indicado_por)
        )
        # Sempre atualiza nome/username (independente se é novo ou existente)
        await db.execute(
            "UPDATE usuarios SET nome = ?, username = ?, atualizado_em = datetime('now','localtime') WHERE telegram_id = ?",
            (nome, username, telegram_id)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        return dict(user) if user else {}
    finally:
        await db.close()


async def buscar_usuario(telegram_id: int) -> dict | None:
    """Busca usuário por telegram_id."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        return dict(user) if user else None
    finally:
        await db.close()


async def buscar_usuario_por_id(user_id: int) -> dict | None:
    """Busca usuário por ID interno."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM usuarios WHERE id = ?", (user_id,))
        user = await cursor.fetchone()
        return dict(user) if user else None
    finally:
        await db.close()


async def atualizar_saldo(telegram_id: int, valor: float, operacao: str = 'adicionar') -> float:
    """Atualiza saldo do usuário. operacao: 'adicionar' ou 'subtrair'."""
    db = await get_db()
    try:
        if operacao == 'adicionar':
            await db.execute(
                "UPDATE usuarios SET saldo = saldo + ?, atualizado_em = datetime('now','localtime') WHERE telegram_id = ?",
                (valor, telegram_id)
            )
        elif operacao == 'subtrair':
            await db.execute(
                "UPDATE usuarios SET saldo = saldo - ?, atualizado_em = datetime('now','localtime') WHERE telegram_id = ?",
                (valor, telegram_id)
            )
        elif operacao == 'definir':
            await db.execute(
                "UPDATE usuarios SET saldo = ?, atualizado_em = datetime('now','localtime') WHERE telegram_id = ?",
                (valor, telegram_id)
            )
        await db.commit()
        cursor = await db.execute("SELECT saldo FROM usuarios WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row['saldo'] if row else 0.0
    finally:
        await db.close()


async def banir_usuario(telegram_id: int, banir: bool = True):
    """Bane ou desbane um usuário."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE usuarios SET banido = ?, atualizado_em = datetime('now','localtime') WHERE telegram_id = ?",
            (1 if banir else 0, telegram_id)
        )
        await db.commit()
    finally:
        await db.close()


async def listar_usuarios(pagina: int = 1, por_pagina: int = 20) -> tuple:
    """Lista usuários com paginação. Retorna (lista, total)."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as total FROM usuarios")
        total = (await cursor.fetchone())['total']
        offset = (pagina - 1) * por_pagina
        cursor = await db.execute(
            "SELECT * FROM usuarios ORDER BY criado_em DESC LIMIT ? OFFSET ?",
            (por_pagina, offset)
        )
        users = [dict(row) for row in await cursor.fetchall()]
        return users, total
    finally:
        await db.close()


async def contar_usuarios_ativos() -> int:
    """Conta usuários que fizeram pelo menos 1 pedido."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as total FROM usuarios WHERE total_pedidos > 0")
        return (await cursor.fetchone())['total']
    finally:
        await db.close()


async def buscar_todos_telegram_ids() -> list:
    """Retorna todos os telegram_ids para broadcast."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT telegram_id FROM usuarios WHERE banido = 0")
        rows = await cursor.fetchall()
        return [row['telegram_id'] for row in rows]
    finally:
        await db.close()


# ==========================================
# PEDIDOS
# ==========================================

async def criar_pedido(usuario_id: int, servico_id: int, service_id_api: int,
                       link: str, quantidade: int, preco_custo: float,
                       preco_com_lucro: float, preco_final: float,
                       gateway: str = '') -> dict:
    """Cria um novo pedido."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO pedidos (usuario_id, servico_id, service_id_api, link,
               quantidade, preco_custo, preco_com_lucro, preco_final, gateway, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente')""",
            (usuario_id, servico_id, service_id_api, link, quantidade,
             preco_custo, preco_com_lucro, preco_final, gateway)
        )
        pedido_id = cursor.lastrowid

        # Atualiza estatísticas do usuário
        await db.execute(
            """UPDATE usuarios SET total_gasto = total_gasto + ?, total_pedidos = total_pedidos + 1,
               atualizado_em = datetime('now','localtime') WHERE id = ?""",
            (preco_final, usuario_id)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def atualizar_pedido_api(pedido_id: int, order_id_api: str, status: str = 'enviado'):
    """Atualiza pedido com ID da API e status."""
    db = await get_db()
    try:
        await db.execute(
            """UPDATE pedidos SET order_id_api = ?, status = ?, status_api = ?,
               atualizado_em = datetime('now','localtime') WHERE id = ?""",
            (order_id_api, status, status, pedido_id)
        )
        await db.commit()
    finally:
        await db.close()


async def atualizar_status_pedido(pedido_id: int, status: str, status_api: str = '',
                                   start_count: int = 0, remains: int = 0):
    """Atualiza status do pedido."""
    db = await get_db()
    try:
        await db.execute(
            """UPDATE pedidos SET status = ?, status_api = ?, start_count = ?, remains = ?,
               atualizado_em = datetime('now','localtime') WHERE id = ?""",
            (status, status_api, start_count, remains, pedido_id)
        )
        await db.commit()
    finally:
        await db.close()


async def buscar_pedidos_usuario(usuario_id: int, limite: int = 20) -> list:
    """Busca pedidos de um usuário."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT p.*, s.nome as servico_nome FROM pedidos p
               LEFT JOIN servicos s ON p.servico_id = s.id
               WHERE p.usuario_id = ? ORDER BY p.criado_em DESC LIMIT ?""",
            (usuario_id, limite)
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def buscar_pedido(pedido_id: int) -> dict | None:
    """Busca pedido por ID."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT p.*, s.nome as servico_nome FROM pedidos p
               LEFT JOIN servicos s ON p.servico_id = s.id
               WHERE p.id = ?""",
            (pedido_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def buscar_pedidos_pendentes() -> list:
    """Busca pedidos que precisam de atualização de status."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM pedidos WHERE status NOT IN ('concluido', 'cancelado', 'erro', 'Completed', 'Canceled')
               AND order_id_api IS NOT NULL AND order_id_api != '' ORDER BY criado_em ASC"""
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


# ==========================================
# PAGAMENTOS
# ==========================================

async def criar_pagamento(usuario_id: int, gateway: str, valor: float, taxa: float = 0.0,
                          referencia_externa: str = '', qr_code: str = '',
                          link_pagamento: str = '') -> dict:
    """Cria um novo pagamento."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO pagamentos (usuario_id, gateway, valor, taxa, referencia_externa, qr_code, link_pagamento)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (usuario_id, gateway, valor, taxa, referencia_externa, qr_code, link_pagamento)
        )
        pagamento_id = cursor.lastrowid
        await db.commit()
        cursor = await db.execute("SELECT * FROM pagamentos WHERE id = ?", (pagamento_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def atualizar_pagamento(pagamento_id: int, status: str):
    """Atualiza status do pagamento."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE pagamentos SET status = ?, atualizado_em = datetime('now','localtime') WHERE id = ?",
            (status, pagamento_id)
        )
        await db.commit()
    finally:
        await db.close()


async def buscar_pagamento_por_referencia(referencia: str) -> dict | None:
    """Busca pagamento pela referência externa."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM pagamentos WHERE referencia_externa = ?", (referencia,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def buscar_pagamentos_pendentes() -> list:
    """Busca pagamentos pendentes."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM pagamentos WHERE status = 'pendente' ORDER BY criado_em ASC"
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


# ==========================================
# SERVIÇOS
# ==========================================

async def sincronizar_servicos(servicos_api: list):
    """Sincroniza serviços do painel SMM com o banco local."""
    db = await get_db()
    try:
        for s in servicos_api:
            service_id = int(s.get('service', 0))
            nome = s.get('name', '')
            categoria = s.get('category', '')
            tipo = s.get('type', '')
            rate = float(s.get('rate', 0))
            min_q = int(s.get('min', 1))
            max_q = int(s.get('max', 1000000))
            permite_refill = 1 if s.get('refill', False) else 0
            permite_cancel = 1 if s.get('cancel', False) else 0

            cursor = await db.execute(
                "SELECT id FROM servicos WHERE service_id_api = ?", (service_id,)
            )
            existe = await cursor.fetchone()

            if existe:
                await db.execute(
                    """UPDATE servicos SET nome = ?, categoria = ?, tipo = ?,
                       rate = ?, min_quantidade = ?, max_quantidade = ?,
                       permite_refill = ?, permite_cancel = ?,
                       atualizado_em = datetime('now','localtime')
                       WHERE service_id_api = ?""",
                    (nome, categoria, tipo, rate, min_q, max_q,
                     permite_refill, permite_cancel, service_id)
                )
            else:
                await db.execute(
                    """INSERT INTO servicos (service_id_api, nome, categoria, tipo, rate,
                       min_quantidade, max_quantidade, permite_refill, permite_cancel)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (service_id, nome, categoria, tipo, rate, min_q, max_q,
                     permite_refill, permite_cancel)
                )

        await db.commit()
        logger.info(f"✅ {len(servicos_api)} serviços sincronizados.")
    finally:
        await db.close()


async def listar_categorias() -> list:
    """Lista categorias únicas de serviços ativos."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT DISTINCT categoria FROM servicos WHERE ativo = 1 ORDER BY categoria"
        )
        return [row['categoria'] for row in await cursor.fetchall()]
    finally:
        await db.close()


async def listar_servicos_ativos() -> list:
    """Lista todos os serviços ativos (para agrupamento por plataforma)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, service_id_api, nome, categoria, tipo, rate,
               min_quantidade, max_quantidade, permite_refill, permite_cancel,
               descricao, nome_custom, markup_custom, ativo
               FROM servicos WHERE ativo = 1 ORDER BY nome"""
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()



async def listar_servicos_por_categoria(categoria: str) -> list:
    """Lista serviços ativos de uma categoria."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM servicos WHERE categoria = ? AND ativo = 1 ORDER BY nome",
            (categoria,)
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def buscar_servico(servico_id: int) -> dict | None:
    """Busca serviço por ID interno."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM servicos WHERE id = ?", (servico_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def buscar_servico_por_api_id(service_id_api: int) -> dict | None:
    """Busca serviço pelo ID da API."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM servicos WHERE service_id_api = ?", (service_id_api,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def atualizar_servico(servico_id: int, **kwargs):
    """Atualiza campos de um serviço."""
    db = await get_db()
    try:
        campos = []
        valores = []
        for chave, valor in kwargs.items():
            campos.append(f"{chave} = ?")
            valores.append(valor)
        campos.append("atualizado_em = datetime('now','localtime')")
        valores.append(servico_id)

        query = f"UPDATE servicos SET {', '.join(campos)} WHERE id = ?"
        await db.execute(query, valores)
        await db.commit()
    finally:
        await db.close()


async def contar_servicos_ativos() -> int:
    """Conta serviços ativos."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as total FROM servicos WHERE ativo = 1")
        return (await cursor.fetchone())['total']
    finally:
        await db.close()


# ==========================================
# CONFIGURAÇÕES
# ==========================================

async def get_config(chave: str, padrao: str = '') -> str:
    """Obtém valor de configuração."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,))
        row = await cursor.fetchone()
        return row['valor'] if row else padrao
    finally:
        await db.close()


async def set_config(chave: str, valor: str):
    """Define valor de configuração."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO configuracoes (chave, valor, atualizado_em)
               VALUES (?, ?, datetime('now','localtime'))
               ON CONFLICT(chave) DO UPDATE SET valor = ?, atualizado_em = datetime('now','localtime')""",
            (chave, valor, valor)
        )
        await db.commit()
    finally:
        await db.close()


async def get_todas_configs() -> dict:
    """Retorna todas as configurações como dicionário."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT chave, valor FROM configuracoes")
        rows = await cursor.fetchall()
        return {row['chave']: row['valor'] for row in rows}
    finally:
        await db.close()


# ==========================================
# GATEWAYS
# ==========================================

async def buscar_gateway(nome: str) -> dict | None:
    """Busca gateway por nome."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM gateways WHERE nome = ?", (nome,))
        row = await cursor.fetchone()
        if row:
            gw = dict(row)
            gw['config'] = json.loads(gw.get('config_json', '{}'))
            return gw
        return None
    finally:
        await db.close()


async def atualizar_gateway(nome: str, **kwargs):
    """Atualiza campos de um gateway."""
    db = await get_db()
    try:
        campos = []
        valores = []
        for chave, valor in kwargs.items():
            if chave == 'config':
                campos.append("config_json = ?")
                valores.append(json.dumps(valor))
            else:
                campos.append(f"{chave} = ?")
                valores.append(valor)
        campos.append("atualizado_em = datetime('now','localtime')")
        valores.append(nome)

        query = f"UPDATE gateways SET {', '.join(campos)} WHERE nome = ?"
        await db.execute(query, valores)
        await db.commit()
    finally:
        await db.close()


async def listar_gateways() -> list:
    """Lista todos os gateways."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM gateways ORDER BY nome")
        gws = []
        for row in await cursor.fetchall():
            gw = dict(row)
            gw['config'] = json.loads(gw.get('config_json', '{}'))
            gws.append(gw)
        return gws
    finally:
        await db.close()


async def buscar_gateway_padrao() -> dict | None:
    """Retorna o gateway padrão ativo."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM gateways WHERE padrao = 1 AND ativo = 1"
        )
        row = await cursor.fetchone()
        if row:
            gw = dict(row)
            gw['config'] = json.loads(gw.get('config_json', '{}'))
            return gw
        # Se não há padrão, retorna primeiro ativo
        cursor = await db.execute("SELECT * FROM gateways WHERE ativo = 1 LIMIT 1")
        row = await cursor.fetchone()
        if row:
            gw = dict(row)
            gw['config'] = json.loads(gw.get('config_json', '{}'))
            return gw
        return None
    finally:
        await db.close()


# ==========================================
# LOGS
# ==========================================

async def registrar_log(tipo: str, mensagem: str, dados: str = ''):
    """Registra log no banco."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO logs (tipo, mensagem, dados) VALUES (?, ?, ?)",
            (tipo, mensagem, dados)
        )
        await db.commit()
    finally:
        await db.close()


async def buscar_logs(tipo: str = None, limite: int = 50) -> list:
    """Busca logs recentes."""
    db = await get_db()
    try:
        if tipo:
            cursor = await db.execute(
                "SELECT * FROM logs WHERE tipo = ? ORDER BY criado_em DESC LIMIT ?",
                (tipo, limite)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM logs ORDER BY criado_em DESC LIMIT ?", (limite,)
            )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


# ==========================================
# ESTATÍSTICAS
# ==========================================

async def obter_estatisticas() -> dict:
    """Retorna estatísticas gerais do sistema."""
    db = await get_db()
    try:
        stats = {}

        # Total usuários
        cursor = await db.execute("SELECT COUNT(*) as total FROM usuarios")
        stats['total_usuarios'] = (await cursor.fetchone())['total']

        # Usuários ativos (com pedidos)
        cursor = await db.execute("SELECT COUNT(*) as total FROM usuarios WHERE total_pedidos > 0")
        stats['usuarios_ativos'] = (await cursor.fetchone())['total']

        # Total pedidos
        cursor = await db.execute("SELECT COUNT(*) as total FROM pedidos")
        stats['total_pedidos'] = (await cursor.fetchone())['total']

        # Pedidos concluídos
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM pedidos WHERE status IN ('concluido', 'Completed')"
        )
        stats['pedidos_concluidos'] = (await cursor.fetchone())['total']

        # Total pagamentos gerados
        cursor = await db.execute("SELECT COUNT(*) as total FROM pagamentos")
        stats['total_pagamentos'] = (await cursor.fetchone())['total']

        # Pagamentos aprovados
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM pagamentos WHERE status = 'aprovado'"
        )
        stats['pagamentos_aprovados'] = (await cursor.fetchone())['total']

        # Pagamentos pendentes
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM pagamentos WHERE status = 'pendente'"
        )
        stats['pagamentos_pendentes'] = (await cursor.fetchone())['total']

        # Receita bruta (soma de preco_final dos pedidos)
        cursor = await db.execute(
            "SELECT COALESCE(SUM(preco_final), 0) as total FROM pedidos WHERE status NOT IN ('cancelado', 'erro')"
        )
        stats['receita_bruta'] = (await cursor.fetchone())['total']

        # Custo total (soma de preco_custo)
        cursor = await db.execute(
            "SELECT COALESCE(SUM(preco_custo), 0) as total FROM pedidos WHERE status NOT IN ('cancelado', 'erro')"
        )
        stats['custo_total'] = (await cursor.fetchone())['total']

        # Lucro líquido
        stats['lucro_liquido'] = stats['receita_bruta'] - stats['custo_total']

        # Conversão
        if stats['total_usuarios'] > 0:
            stats['conversao'] = round(
                (stats['usuarios_ativos'] / stats['total_usuarios']) * 100, 1
            )
        else:
            stats['conversao'] = 0

        # Taxas pagas por gateway
        cursor = await db.execute(
            "SELECT gateway, COALESCE(SUM(taxa), 0) as total_taxa FROM pagamentos WHERE status = 'aprovado' GROUP BY gateway"
        )
        stats['taxas_por_gateway'] = {row['gateway']: row['total_taxa'] for row in await cursor.fetchall()}

        return stats
    finally:
        await db.close()


async def obter_estatisticas_periodo(dias: int = 30) -> dict:
    """Retorna estatísticas de um período específico."""
    db = await get_db()
    try:
        stats = {}
        cursor = await db.execute(
            f"""SELECT COUNT(*) as total, COALESCE(SUM(preco_final), 0) as receita,
                COALESCE(SUM(preco_custo), 0) as custo
                FROM pedidos WHERE criado_em >= datetime('now', '-{dias} days', 'localtime')
                AND status NOT IN ('cancelado', 'erro')"""
        )
        row = await cursor.fetchone()
        stats['pedidos'] = row['total']
        stats['receita'] = row['receita']
        stats['custo'] = row['custo']
        stats['lucro'] = row['receita'] - row['custo']
        return stats
    finally:
        await db.close()


# ==========================================
# CUPONS
# ==========================================

async def criar_cupom(codigo: str, desconto_pct: float = 0, desconto_fixo: float = 0,
                      usos_max: int = 1, validade: str = None) -> dict:
    """Cria um novo cupom."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO cupons (codigo, desconto_pct, desconto_fixo, usos_max, validade)
               VALUES (?, ?, ?, ?, ?)""",
            (codigo.upper(), desconto_pct, desconto_fixo, usos_max, validade)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM cupons WHERE codigo = ?", (codigo.upper(),))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def buscar_cupom(codigo: str) -> dict | None:
    """Busca cupom por código."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM cupons WHERE codigo = ? AND ativo = 1", (codigo.upper(),)
        )
        row = await cursor.fetchone()
        if row:
            cupom = dict(row)
            # Verifica usos e validade
            if cupom['usos_atuais'] >= cupom['usos_max']:
                return None
            if cupom['validade']:
                from datetime import datetime
                try:
                    val = datetime.fromisoformat(cupom['validade'])
                    if datetime.now() > val:
                        return None
                except ValueError:
                    pass
            return cupom
        return None
    finally:
        await db.close()


async def usar_cupom(codigo: str):
    """Incrementa uso do cupom."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE cupons SET usos_atuais = usos_atuais + 1 WHERE codigo = ?",
            (codigo.upper(),)
        )
        await db.commit()
    finally:
        await db.close()


# ==========================================
# INDICAÇÕES
# ==========================================

async def registrar_indicacao(usuario_id: int, indicado_id: int, comissao: float):
    """Registra uma indicação."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO indicacoes (usuario_id, indicado_id, comissao) VALUES (?, ?, ?)",
            (usuario_id, indicado_id, comissao)
        )
        await db.commit()
    finally:
        await db.close()
