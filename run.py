"""
Ponto de entrada do Bot SMM Telegram.
=======================================
Execute com: python run.py

Deploy Universal:
- Se PORT definido (PaaS): sobe health server HTTP + polling
- Se PORT não definido (VPS/local): apenas polling
- Shutdown gracioso com SIGTERM/SIGINT
- Auto-criação de diretórios
- Watchdog com auto-restart
"""

import asyncio
import os
import sys
import signal
import logging

# ============================================
# CONFIGURAÇÃO INICIAL
# ============================================

# Configurar logging antes de tudo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger('startup')

# Constantes
MAX_RETRIES = 10
BASE_RETRY_DELAY = 5


# ============================================
# AUTO-CRIAÇÃO DE DIRETÓRIOS
# ============================================

def garantir_diretorios():
    """Cria todos os diretórios necessários antes de qualquer import."""
    base = os.path.dirname(os.path.abspath(__file__))
    dirs = [
        os.path.join(base, 'data'),
        os.path.join(base, 'data', 'backups'),
        os.path.join(base, 'data', 'logs'),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


# ============================================
# DETECÇÃO DE AMBIENTE
# ============================================

def detectar_ambiente() -> dict:
    """Detecta automaticamente o ambiente de hospedagem."""
    port = os.environ.get('PORT')
    env = {
        'port': int(port) if port else None,
        'modo': 'web' if port else 'worker',
        'render': bool(os.environ.get('RENDER')),
        'railway': bool(os.environ.get('RAILWAY_ENVIRONMENT')),
        'koyeb': bool(os.environ.get('KOYEB_SERVICE_NAME')),
        'flyio': bool(os.environ.get('FLY_APP_NAME')),
        'docker': os.path.exists('/.dockerenv'),
    }

    # Detectar provedor
    if env['render']:
        env['provedor'] = 'Render'
    elif env['railway']:
        env['provedor'] = 'Railway'
    elif env['koyeb']:
        env['provedor'] = 'Koyeb'
    elif env['flyio']:
        env['provedor'] = 'Fly.io'
    elif env['docker']:
        env['provedor'] = 'Docker'
    else:
        env['provedor'] = 'Local/VPS'

    return env


# ============================================
# HEALTH SERVER (SOMENTE SE PORT DEFINIDO)
# ============================================

async def iniciar_health_server(port: int) -> None:
    """
    Servidor HTTP leve para health checks do PaaS.
    Não interfere no bot. Roda em paralelo.
    Endpoints:
    - GET / → 200 OK
    - GET /health → 200 OK com status
    """
    from aiohttp import web

    async def health_handler(request):
        return web.json_response({
            'status': 'ok',
            'bot': 'running',
            'service': 'smm-bot-telegram'
        })

    app = web.Application()
    app.router.add_get('/', health_handler)
    app.router.add_get('/health', health_handler)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"🌐 Health server rodando na porta {port}")
    return runner


# ============================================
# SHUTDOWN GRACIOSO
# ============================================

_shutdown_event = asyncio.Event()


def _sinal_shutdown(sig, frame):
    """Handler para SIGTERM/SIGINT — sinaliza shutdown gracioso."""
    nome = signal.Signals(sig).name
    log.info(f"📡 Sinal {nome} recebido — iniciando shutdown gracioso...")
    _shutdown_event.set()


# ============================================
# MAIN
# ============================================

async def main():
    """Loop principal com watchdog, health server e shutdown gracioso."""

    # 1. Auto-criar diretórios
    garantir_diretorios()

    # 2. Detectar ambiente
    env = detectar_ambiente()
    log.info(f"🌍 Ambiente detectado: {env['provedor']} (modo: {env['modo']})")

    # 3. Registrar handlers de sinal (SIGTERM/SIGINT)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _shutdown_event.set())
        except NotImplementedError:
            # Windows não suporta add_signal_handler — usar fallback
            signal.signal(sig, _sinal_shutdown)

    # 4. Health server (se PORT definido)
    health_runner = None
    if env['port']:
        try:
            health_runner = await iniciar_health_server(env['port'])
        except Exception as e:
            log.warning(f"⚠️ Health server falhou (não crítico): {e}")

    # 5. Watchdog com auto-restart
    tentativa = 0
    while tentativa < MAX_RETRIES:
        tentativa += 1

        if _shutdown_event.is_set():
            log.info("🔴 Shutdown solicitado antes do início.")
            break

        try:
            from bot.main import iniciar_bot
            log.info(f"🚀 Iniciando bot (tentativa {tentativa}/{MAX_RETRIES})...")
            await iniciar_bot(shutdown_event=_shutdown_event)
            break  # Saiu normalmente

        except KeyboardInterrupt:
            log.info("🔴 Bot encerrado pelo usuário (Ctrl+C).")
            break

        except SystemExit:
            log.info("🔴 Bot encerrado via SystemExit.")
            break

        except Exception as e:
            log.error(f"❌ Erro fatal na tentativa {tentativa}: {e}")

            if _shutdown_event.is_set():
                break

            if tentativa < MAX_RETRIES:
                delay = min(BASE_RETRY_DELAY * tentativa, 60)
                log.info(f"🔄 Reiniciando em {delay}s...")
                try:
                    await asyncio.wait_for(
                        _shutdown_event.wait(),
                        timeout=delay
                    )
                    break  # Shutdown durante espera
                except asyncio.TimeoutError:
                    pass  # Timeout normal — re-tentar
            else:
                log.error(f"❌ Máximo de {MAX_RETRIES} tentativas atingido.")

    # 6. Cleanup
    log.info("🧹 Limpando recursos...")
    if health_runner:
        await health_runner.cleanup()
        log.info("🌐 Health server encerrado.")

    log.info("🔴 Processo encerrado.")


# ============================================
# ENTRY POINT
# ============================================

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔴 Encerrado.")
    except SystemExit:
        pass
