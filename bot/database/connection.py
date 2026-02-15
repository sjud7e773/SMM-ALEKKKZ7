"""
Conexão com banco de dados SQLite.
====================================
Gerencia conexão, inicialização de tabelas e backup.
"""

import aiosqlite
import os
import shutil
from datetime import datetime

from bot.utils.logger import logger

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "bot.db")
BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), "backups")


async def get_db() -> aiosqlite.Connection:
    """Retorna conexão com o banco de dados."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def inicializar_banco():
    """Cria todas as tabelas se não existirem."""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                nome TEXT NOT NULL DEFAULT '',
                username TEXT DEFAULT '',
                saldo REAL NOT NULL DEFAULT 0.0,
                banido INTEGER NOT NULL DEFAULT 0,
                indicado_por INTEGER DEFAULT NULL,
                total_gasto REAL NOT NULL DEFAULT 0.0,
                total_pedidos INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                servico_id INTEGER NOT NULL,
                service_id_api INTEGER NOT NULL,
                order_id_api TEXT DEFAULT NULL,
                link TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_custo REAL NOT NULL,
                preco_com_lucro REAL NOT NULL,
                preco_final REAL NOT NULL,
                gateway TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pendente',
                status_api TEXT DEFAULT '',
                start_count INTEGER DEFAULT 0,
                remains INTEGER DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            );

            CREATE TABLE IF NOT EXISTS pagamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                gateway TEXT NOT NULL,
                valor REAL NOT NULL,
                taxa REAL NOT NULL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'pendente',
                referencia_externa TEXT DEFAULT '',
                qr_code TEXT DEFAULT '',
                link_pagamento TEXT DEFAULT '',
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            );

            CREATE TABLE IF NOT EXISTS servicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id_api INTEGER UNIQUE NOT NULL,
                nome TEXT NOT NULL,
                nome_custom TEXT DEFAULT '',
                categoria TEXT NOT NULL DEFAULT '',
                tipo TEXT DEFAULT '',
                rate REAL NOT NULL,
                min_quantidade INTEGER NOT NULL DEFAULT 1,
                max_quantidade INTEGER NOT NULL DEFAULT 1000000,
                ativo INTEGER NOT NULL DEFAULT 1,
                permite_refill INTEGER NOT NULL DEFAULT 0,
                permite_cancel INTEGER NOT NULL DEFAULT 0,
                markup_custom REAL DEFAULT NULL,
                descricao TEXT DEFAULT '',
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS gateways (
                nome TEXT PRIMARY KEY,
                ativo INTEGER NOT NULL DEFAULT 0,
                config_json TEXT NOT NULL DEFAULT '{}',
                taxa_venda REAL NOT NULL DEFAULT 0.0,
                taxa_saque REAL NOT NULL DEFAULT 0.0,
                taxa_tipo TEXT NOT NULL DEFAULT 'percentual',
                padrao INTEGER NOT NULL DEFAULT 0,
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL DEFAULT 'info',
                mensagem TEXT NOT NULL,
                dados TEXT DEFAULT '',
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS upsell_regras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                servico_origem_id INTEGER DEFAULT NULL,
                categoria_origem TEXT DEFAULT '',
                servico_destino_id INTEGER NOT NULL,
                desconto_pct REAL NOT NULL DEFAULT 5.0,
                mensagem TEXT DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS cupons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                desconto_pct REAL NOT NULL DEFAULT 0.0,
                desconto_fixo REAL NOT NULL DEFAULT 0.0,
                usos_max INTEGER NOT NULL DEFAULT 1,
                usos_atuais INTEGER NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                validade TEXT DEFAULT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS indicacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                indicado_id INTEGER NOT NULL,
                comissao REAL NOT NULL DEFAULT 0.0,
                paga INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
                FOREIGN KEY (indicado_id) REFERENCES usuarios(id)
            );

            -- === TABELAS SAAS (Hierarquia Owner/Admin/User) ===

            CREATE TABLE IF NOT EXISTS owners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT DEFAULT '',
                nome TEXT DEFAULT '',
                hash_verificacao TEXT NOT NULL DEFAULT '',
                arroba_contato TEXT DEFAULT '',
                license_type TEXT NOT NULL DEFAULT 'PROTEGIDA',
                white_label_enabled INTEGER NOT NULL DEFAULT 0,
                allow_owner_change INTEGER NOT NULL DEFAULT 0,
                signature_hash TEXT NOT NULL DEFAULT '',
                installation_id TEXT NOT NULL DEFAULT '',
                msg_revenda TEXT DEFAULT '',
                link_revenda TEXT DEFAULT '',
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT DEFAULT '',
                nome TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ativo',
                plano TEXT NOT NULL DEFAULT 'basico',
                dias_plano INTEGER NOT NULL DEFAULT 30,
                data_inicio TEXT DEFAULT NULL,
                data_vencimento TEXT DEFAULT NULL,
                limite_pedidos_mes INTEGER NOT NULL DEFAULT 500,
                pedidos_mes_atual INTEGER NOT NULL DEFAULT 0,
                margem_min REAL NOT NULL DEFAULT 30,
                margem_max REAL NOT NULL DEFAULT 500,
                api_key TEXT DEFAULT '',
                api_url TEXT DEFAULT 'https://baratosociais.com/api/v2',
                mensagem_inicio TEXT DEFAULT '',
                mensagem_pix TEXT DEFAULT '',
                media_inicio_id TEXT DEFAULT '',
                media_pix_id TEXT DEFAULT '',
                termos_texto TEXT DEFAULT '',
                termos_imagem_id TEXT DEFAULT '',
                termos_modo TEXT NOT NULL DEFAULT 'mensagem',
                modo_manutencao INTEGER NOT NULL DEFAULT 0,
                adicionado_por INTEGER DEFAULT NULL,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                preco REAL NOT NULL DEFAULT 0,
                dias INTEGER NOT NULL DEFAULT 30,
                limite_pedidos INTEGER NOT NULL DEFAULT 500,
                limite_bots INTEGER NOT NULL DEFAULT 1,
                margem_min REAL NOT NULL DEFAULT 30,
                margem_max REAL NOT NULL DEFAULT 500,
                permite_whitelabel INTEGER NOT NULL DEFAULT 0,
                descricao TEXT DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE NOT NULL,
                telegram_id INTEGER NOT NULL,
                pedido_id INTEGER DEFAULT NULL,
                tipo TEXT NOT NULL DEFAULT 'suporte',
                mensagem TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'aberto',
                resposta TEXT DEFAULT '',
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS saas_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT DEFAULT '',
                preco REAL NOT NULL DEFAULT 0,
                duracao_dias INTEGER NOT NULL DEFAULT 30,
                features TEXT DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 0,
                destino TEXT DEFAULT '',
                valor TEXT DEFAULT '',
                criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_pedidos_usuario ON pedidos(usuario_id);
            CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
            CREATE INDEX IF NOT EXISTS idx_pagamentos_usuario ON pagamentos(usuario_id);
            CREATE INDEX IF NOT EXISTS idx_pagamentos_status ON pagamentos(status);
            CREATE INDEX IF NOT EXISTS idx_servicos_categoria ON servicos(categoria);
            CREATE INDEX IF NOT EXISTS idx_servicos_ativo ON servicos(ativo);
            CREATE INDEX IF NOT EXISTS idx_usuarios_telegram ON usuarios(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_admins_telegram ON admins(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_admins_status ON admins(status);
            CREATE INDEX IF NOT EXISTS idx_tickets_telegram ON tickets(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
        """)

        # Inserir gateways padrão se não existirem
        await db.execute("""
            INSERT OR IGNORE INTO gateways (nome, ativo, config_json, taxa_venda, taxa_saque, taxa_tipo, padrao)
            VALUES ('mercadopago', 0, '{}', 0.99, 0.0, 'percentual', 1)
        """)
        await db.execute("""
            INSERT OR IGNORE INTO gateways (nome, ativo, config_json, taxa_venda, taxa_saque, taxa_tipo, padrao)
            VALUES ('hoopay', 0, '{}', 0.40, 0.30, 'fixo', 0)
        """)

        # Configurações padrão
        configs_padrao = [
            ('margem_lucro', '75'),
            ('mensagem_inicio', '🤖 Bem-vindo ao Bot de Serviços SMM!\\n\\nEscolha uma opção no menu abaixo:'),
            ('mensagem_suporte', '📞 Entre em contato com o suporte.'),
            ('api_url', 'https://baratosociais.com/api/v2'),
            ('api_key', ''),
            ('admin_id', ''),
            ('bot_token', ''),
            ('comissao_indicacao', '5'),
            ('upsell_ativo', '1'),
            ('sync_intervalo_minutos', '60'),
            ('status_check_minutos', '5'),
            ('sistema_configurado', '0'),
        ]
        for chave, valor in configs_padrao:
            await db.execute(
                "INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES (?, ?)",
                (chave, valor)
            )

        # Planos padrão
        planos_padrao = [
            ('Básico', 'basico', 49.90, 30, 500, 1, 30, 500, 0,
             'Plano inicial com até 500 pedidos/mês'),
            ('Profissional', 'profissional', 99.90, 30, 2000, 3, 20, 1000, 0,
             'Plano avançado com até 2000 pedidos/mês'),
            ('White Label', 'whitelabel', 199.90, 30, 10000, 5, 10, 2000, 1,
             'Plano completo com white label e pedidos ilimitados'),
        ]
        for p in planos_padrao:
            await db.execute("""
                INSERT OR IGNORE INTO plans (nome, slug, preco, dias, limite_pedidos,
                limite_bots, margem_min, margem_max, permite_whitelabel, descricao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, p)

        await db.commit()

        # Migração: adicionar colunas novas se não existirem (bancos antigos)
        try:
            await db.execute("ALTER TABLE servicos ADD COLUMN permite_refill INTEGER NOT NULL DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # Coluna já existe
        try:
            await db.execute("ALTER TABLE servicos ADD COLUMN permite_cancel INTEGER NOT NULL DEFAULT 0")
            await db.commit()
        except Exception:
            pass  # Coluna já existe

        logger.info("✅ Banco de dados inicializado com sucesso.")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco: {e}")
        raise
    finally:
        await db.close()


async def fazer_backup() -> str:
    """Cria backup do banco de dados. Retorna o caminho do backup."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"bot_backup_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    logger.info(f"✅ Backup criado: {backup_path}")
    return backup_path


async def restaurar_backup(backup_path: str) -> bool:
    """Restaura banco de dados a partir de backup."""
    if not os.path.exists(backup_path):
        return False
    shutil.copy2(backup_path, DB_PATH)
    logger.info(f"✅ Backup restaurado de: {backup_path}")
    return True


async def listar_backups() -> list:
    """Lista todos os backups disponíveis."""
    if not os.path.exists(BACKUP_DIR):
        return []
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith('.db'):
            path = os.path.join(BACKUP_DIR, f)
            size = os.path.getsize(path) / 1024  # KB
            backups.append({'nome': f, 'caminho': path, 'tamanho_kb': round(size, 1)})
    return backups
