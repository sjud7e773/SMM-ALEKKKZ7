"""
Handler de Definir Dono.
==========================
Comando /definir_dono — permite que o primeiro usuário
se torne o dono (owner) do sistema, com proteção SHA256.
Substituição do antigo /setup para o sistema SaaS.
"""

import uuid
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from bot.config import gerar_hash_seguranca
from bot.database.queries_owner import buscar_owner, criar_owner
from bot.utils.helpers import escape_html
from bot.utils.logger import logger

router = Router()


@router.message(Command("definir_dono"))
async def cmd_definir_dono(message: Message):
    """Comando /definir_dono — configuração de dono do sistema."""
    # Verificar se já existe owner
    owner = await buscar_owner()
    if owner:
        if owner['telegram_id'] == message.from_user.id:
            await message.answer(
                "✅ Você já é o <b>dono</b> deste sistema.\n"
                "Use /dono para acessar o painel de administração global.",
                parse_mode='HTML'
            )
        else:
            await message.answer(
                "⚠️ Este sistema já possui um dono configurado.\n"
                "Se você precisa de acesso, entre em contato com o proprietário.",
                parse_mode='HTML'
            )
        return

    # Nenhum owner — oferecer setup
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Sim, confirmar como Dono",
            callback_data=f"definir_dono_confirm:{message.from_user.id}"
        )],
        [InlineKeyboardButton(
            text="❌ Cancelar",
            callback_data="definir_dono_cancel"
        )]
    ])

    nome = escape_html(message.from_user.full_name)
    await message.answer(
        "👑 <b>CONFIGURAÇÃO DE DONO DO SISTEMA</b>\n\n"
        "Este sistema ainda não possui um dono configurado.\n\n"
        f"👤 <b>Seu Nome:</b> {nome}\n"
        f"🆔 <b>Seu ID:</b> <code>{message.from_user.id}</code>\n\n"
        "⚠️ <b>ATENÇÃO:</b> Ao confirmar, você será definido como o <b>DONO</b> "
        "do sistema e terá controle total sobre todas as funcionalidades, "
        "incluindo:\n\n"
        "• 👥 Gerenciar admins (clientes pagantes)\n"
        "• 💰 Definir planos e preços\n"
        "• 🔒 Configurar licenciamento\n"
        "• 📊 Estatísticas globais\n"
        "• 🛡️ Segurança e backup\n\n"
        "⚡ Esta ação <b>não pode ser desfeita</b> sem acesso ao código.",
        parse_mode='HTML',
        reply_markup=kb
    )


@router.callback_query(lambda c: c.data and c.data.startswith("definir_dono_confirm:"))
async def callback_definir_dono_confirm(callback: CallbackQuery):
    """Confirma definição de dono."""
    tid = int(callback.data.split(":")[1])

    # Segurança: apenas o próprio pode confirmar
    if callback.from_user.id != tid:
        await callback.answer("❌ Ação não permitida.", show_alert=True)
        return

    # Proteção contra duplo-clique
    owner = await buscar_owner()
    if owner:
        await callback.answer("⚠️ Sistema já possui dono!", show_alert=True)
        return

    # Gerar hashes de segurança
    hash_verificacao = gerar_hash_seguranca(str(tid))
    signature_hash = gerar_hash_seguranca(f"{tid}:owner:master")
    installation_id = str(uuid.uuid4())

    # Criar owner
    try:
        owner = await criar_owner(
            telegram_id=tid,
            nome=callback.from_user.full_name or "Dono",
            username=callback.from_user.username or "",
            hash_verificacao=hash_verificacao,
            signature_hash=signature_hash,
            installation_id=installation_id
        )

        # Invalidar caches para acesso imediato
        from bot.middlewares.permission import invalidar_owner_cache
        from bot.config import invalidar_cache
        invalidar_owner_cache()
        invalidar_cache()

        logger.info(f"👑 DONO configurado: {tid} ({callback.from_user.full_name})")
        logger.info(f"🔑 Installation ID: {installation_id}")

        nome = escape_html(callback.from_user.full_name)
        install_short = installation_id[:8]
        hash_short = hash_verificacao[:12]
        await callback.message.edit_text(
            "✅ <b>DONO CONFIGURADO COM SUCESSO!</b>\n\n"
            f"👑 <b>Dono:</b> {nome}\n"
            f"🆔 <b>ID:</b> <code>{tid}</code>\n"
            f"🔑 <b>Instalação:</b> <code>{install_short}...</code>\n"
            f"🔒 <b>Hash:</b> <code>{hash_short}...</code>\n\n"
            "📋 <b>Próximos passos:</b>\n"
            "1️⃣ Use /dono para acessar o painel global\n"
            "2️⃣ Adicione admins (clientes pagantes)\n"
            "3️⃣ Configure os planos de revenda\n"
            "4️⃣ Configure as mensagens de marketing\n\n"
            "🚀 Seu sistema SaaS está pronto!",
            parse_mode='HTML'
        )
        await callback.answer("✅ Pronto!")

    except Exception as e:
        logger.error(f"❌ Erro ao definir dono: {e}")
        await callback.message.edit_text(
            f"❌ <b>Erro ao configurar dono:</b>\n<code>{escape_html(str(e))}</code>",
            parse_mode='HTML'
        )
        await callback.answer("❌ Erro!", show_alert=True)


@router.callback_query(lambda c: c.data == "definir_dono_cancel")
async def callback_definir_dono_cancel(callback: CallbackQuery):
    """Cancela definição de dono."""
    await callback.message.edit_text(
        "❌ Configuração de dono cancelada.\n"
        "Use /definir_dono novamente quando estiver pronto.",
        parse_mode='HTML'
    )
    await callback.answer()
