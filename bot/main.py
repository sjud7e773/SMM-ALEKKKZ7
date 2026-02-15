"""
Inicialização do Bot SMM Telegram.
=====================================
Registra handlers, middlewares, comandos e inicia o polling.
Os comandos de barra (/) são registrados automaticamente no BotFather.
Suporta hierarquia Owner/Admin/User.
Aceita shutdown_event para encerramento gracioso.
"""

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, ErrorEvent
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_env, carregar_configs, get_config
from bot.database.connection import inicializar_banco
from bot.utils.logger import logger

# Importar handlers
from bot.handlers import (
    setup, start, comprar, saldo, pedidos, admin, suporte, broadcast,
    configuracoes, owner_panel, notificacoes
)

# Importar middlewares
from bot.middlewares.antiflood import AntiFloodMiddleware
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.permission import PermissionMiddleware


def _mascarar_token(token: str) -> str:
    """Mascara token para logs — mostra apenas últimos 4 caracteres."""
    if not token or len(token) < 8:
        return '***'
    return f"***{token[-4:]}"


async def registrar_comandos(bot: Bot):
    """Registra os comandos de barra automaticamente no Telegram.
    Nota: /dono e /definir_dono são OCULTOS (não aparecem na lista)."""
    comandos = [
        BotCommand(command="start", description="🏠 Iniciar / Menu principal"),
        BotCommand(command="menu", description="📋 Abrir menu"),
        BotCommand(command="comprar", description="🛒 Comprar serviço"),
        BotCommand(command="saldo", description="💰 Ver meu saldo"),
        BotCommand(command="pedidos", description="📦 Meus pedidos"),
        BotCommand(command="status", description="📈 Status de um pedido"),
        BotCommand(command="suporte", description="📞 Suporte / Ajuda"),
        BotCommand(command="admin", description="🛠 Painel Admin"),
    ]
    await bot.set_my_commands(comandos)
    logger.info("✅ Comandos de barra registrados no Telegram.")


async def iniciar_bot(shutdown_event: asyncio.Event = None):
    """Função principal que inicializa e executa o bot.
    Aceita shutdown_event para encerramento gracioso via SIGTERM."""
    logger.info("=" * 50)
    logger.info("🤖 BOT SMM TELEGRAM SaaS - INICIANDO...")
    logger.info("=" * 50)

    # 1. Inicializar banco de dados
    logger.info("📦 Inicializando banco de dados...")
    await inicializar_banco()

    # 2. Carregar configurações
    logger.info("⚙️ Carregando configurações...")
    await carregar_configs()

    # 3. Obter token do bot
    bot_token = await get_config('bot_token', '')
    if not bot_token:
        bot_token = get_env('BOT_TOKEN', '')

    if not bot_token or bot_token == 'SEU_TOKEN_AQUI':
        logger.error("❌ BOT_TOKEN não configurado!")
        logger.error("   Configure o token no arquivo .env ou via painel admin.")
        print("\n" + "=" * 50)
        print("❌ ERRO: Token do bot não configurado!")
        print("=" * 50)
        print("\n1. Copie o arquivo .env.example para .env")
        print("2. Coloque seu token do BotFather em BOT_TOKEN=")
        print("3. Execute novamente\n")
        return

    # Log do token mascarado (segurança: nunca expor token completo)
    logger.info(f"🔑 Token: {_mascarar_token(bot_token)}")

    # 4. Criar bot e dispatcher — PADRONIZADO PARA HTML
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 5. Registrar middlewares
    logger.info("🔒 Registrando middlewares...")
    dp.message.middleware(AntiFloodMiddleware(limite=3, periodo=1.0))
    dp.message.middleware(AuthMiddleware())
    dp.message.middleware(PermissionMiddleware())
    dp.callback_query.middleware(AntiFloodMiddleware(limite=5, periodo=1.0))
    dp.callback_query.middleware(AuthMiddleware())
    dp.callback_query.middleware(PermissionMiddleware())

    # 5.1 — Registrar handler global de erros (anti-crash)
    @dp.error()
    async def global_error_handler(event: ErrorEvent):
        """Captura QUALQUER erro não tratado nos handlers."""
        exception = event.exception
        update = event.update
        
        logger.error(f"💥 ERRO NÃO TRATADO: {type(exception).__name__}: {exception}")
        logger.exception(exception)
        try:
            user_msg = None
            if update.message:
                user_msg = update.message
            elif update.callback_query:
                user_msg = update.callback_query.message
                try:
                    await update.callback_query.answer(
                        "❌ Ocorreu um erro. Tente novamente.",
                        show_alert=True
                    )
                except Exception:
                    pass
  
            if user_msg:
                try:
                    await user_msg.answer(
                        "⚠️ Ocorreu um erro inesperado.\n"
                        "Por favor, tente novamente ou entre em contato com o suporte.",
                        parse_mode=None
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Erro ao processar error handler: {e}")
        return True  # Marca como tratado, não propaga

    # 5.2 Validar licença na inicialização
    try:
        from bot.services.license import validar_licenca
        licenca = await validar_licenca()
        if licenca.get('valida'):
            logger.info(f"✅ Licença válida — {licenca.get('tipo', 'N/A')}")
        else:
            logger.warning(f"⚠️ Licença inválida: {licenca.get('motivo', 'desconhecido')}")
    except Exception as e:
        logger.warning(f"⚠️ Verificação de licença ignorada: {e}")

    # 6. Registrar routers (handlers) — ordem importa
    logger.info("📋 Registrando handlers...")

    # Handlers do dono (ocultos, prioridade máxima)
    try:
        from bot.handlers import definir_dono, dono
        dp.include_router(definir_dono.router)
        dp.include_router(dono.router)
        logger.info("  👑 Handlers de dono registrados.")
    except ImportError:
        logger.info("  ℹ️ Handlers de dono não disponíveis ainda.")

    dp.include_router(setup.router)         # Setup legado
    dp.include_router(admin.router)         # Admin antes dos gerais

    # Handlers opcionais (tutorial, revenda, termos)
    for modulo_nome in ('tutorial', 'revenda', 'termos'):
        try:
            modulo = __import__(f'bot.handlers.{modulo_nome}', fromlist=['router'])
            dp.include_router(modulo.router)
            logger.info(f"  📦 Handler {modulo_nome} registrado.")
        except ImportError:
            pass

    # Novos handlers reorganizados (prioridade alta)
    dp.include_router(configuracoes.router)        # Sistema de configurações
    dp.include_router(owner_panel.router)          # Painel owner exclusivo
    dp.include_router(notificacoes.router)         # Sistema de notificações

    dp.include_router(broadcast.router)
    dp.include_router(start.router)
    dp.include_router(comprar.router)
    dp.include_router(saldo.router)
    dp.include_router(pedidos.router)
    dp.include_router(suporte.router)       # Suporte por último (catch-all)

    # 7. Registrar comandos no BotFather
    logger.info("📝 Registrando comandos...")
    await registrar_comandos(bot)

    # 8. Iniciar scheduler em background
    logger.info("⏰ Iniciando scheduler...")
    from bot.services.scheduler import iniciar_scheduler
    scheduler_task = asyncio.create_task(iniciar_scheduler(bot))

    # 9. Startup diagnostics
    import sys
    bot_info = await bot.me()
    logger.info("=" * 50)
    logger.info("📊 DIAGNÓSTICO DE STARTUP")
    logger.info(f"  🐍 Python: {sys.version.split()[0]}")
    logger.info(f"  📦 aiogram: {__import__('aiogram').__version__}")
    logger.info(f"  🗄️ DB: SQLite (aiosqlite)")
    logger.info(f"  ⏰ Scheduler: ativo")

    # API status check
    try:
        from bot.services.smm_api import ver_saldo as _check_api
        api_result = await _check_api()
        if 'error' not in api_result:
            logger.info(f"  🌐 API SMM: ✅ conectada (saldo: {api_result.get('balance', 'N/A')})")
        else:
            logger.info(f"  🌐 API SMM: ⚠️ {api_result.get('error', 'sem resposta')}")
    except Exception:
        logger.info("  🌐 API SMM: ⚠️ não configurada")

    # Owner check
    try:
        from bot.database.queries_owner import buscar_owner
        owner = await buscar_owner()
        if owner:
            logger.info(f"  👑 Owner: {owner.get('nome', 'N/A')} (ID: {owner['telegram_id']})")
        else:
            logger.info("  👑 Owner: ⚠️ não configurado (use /definir_dono)")
    except Exception:
        logger.info("  👑 Owner: ⚠️ tabela não encontrada")

    logger.info("=" * 50)
    logger.info(f"✅ Bot @{bot_info.username} iniciado com sucesso!")
    logger.info(f"🆔 Bot ID: {bot_info.id}")
    logger.info("=" * 50)
    print(f"\n✅ Bot @{bot_info.username} está rodando!")
    print(f"🔗 https://t.me/{bot_info.username}")
    print("Pressione Ctrl+C para parar.\n")

    # 10. Iniciar polling com suporte a shutdown gracioso
    try:
        if shutdown_event:
            # Monitorar shutdown_event em paralelo com polling
            polling_task = asyncio.create_task(
                dp.start_polling(
                    bot,
                    allowed_updates=dp.resolve_used_update_types(),
                    close_bot_session=False
                )
            )
            shutdown_task = asyncio.create_task(shutdown_event.wait())

            # Esperar o que terminar primeiro
            done, pending = await asyncio.wait(
                [polling_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Se shutdown solicitado, parar polling
            if shutdown_task in done:
                logger.info("📡 Shutdown gracioso — parando polling...")
                await dp.stop_polling()
                polling_task.cancel()
                try:
                    await polling_task
                except asyncio.CancelledError:
                    pass
            else:
                # Polling saiu sozinho
                shutdown_task.cancel()
        else:
            # Modo simples sem shutdown_event
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                close_bot_session=False
            )
    finally:
        # Cleanup
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        logger.info("🔴 Bot encerrado.")
