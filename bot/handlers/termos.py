"""
Handler de Termos de Uso.
===========================
Exibe termos de uso configuráveis por cada admin.
Suporta modo mensagem e modo WebApp.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.utils.helpers import safe_edit_message, escape_html
from bot.utils.logger import logger

router = Router()

# Termos padrão
TERMOS_PADRAO = """
📜 <b>TERMOS DE USO</b>

Ao utilizar este serviço, você concorda com os seguintes termos:

<b>1. Serviços</b>
Os serviços oferecidos são de marketing digital para redes sociais. Os resultados podem variar de acordo com o tipo de serviço e plataforma.

<b>2. Pagamentos</b>
Todos os pagamentos são processados de forma segura. O saldo adicionado é não-reembolsável após a confirmação do pagamento.

<b>3. Pedidos</b>
• Pedidos enviados não podem ser cancelados após o processamento.
• O prazo de entrega varia conforme o serviço escolhido.
• Reposições (refill) estão disponíveis apenas para serviços que as suportam.

<b>4. Responsabilidade</b>
• O usuário é responsável por fornecer links corretos e válidos.
• Perfis devem estar públicos durante o processamento.
• Não nos responsabilizamos por bloqueios em contas privadas.

<b>5. Proibições</b>
• É proibido usar o serviço para atividades ilegais.
• Tentativas de fraude resultarão em banimento permanente.

<b>6. Suporte</b>
Em caso de problemas, utilize o canal de suporte disponível no menu principal.

<b>7. Alterações</b>
Estes termos podem ser atualizados a qualquer momento sem aviso prévio.
""".strip()


@router.callback_query(F.data == "termos")
async def callback_termos(callback: CallbackQuery):
    """Exibe termos de uso."""
    await callback.answer()

    # Tentar buscar termos personalizados do admin
    termos_texto = TERMOS_PADRAO

    try:
        from bot.database.queries_owner import buscar_admin_por_telegram_id
        from bot.config import get_config

        # Por enquanto usa termos globais; no futuro, por admin
        termos_custom = await get_config('termos_texto', '')
        if termos_custom:
            termos_texto = termos_custom
    except Exception:
        pass

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Li e Concordo", callback_data="menu")],
        [InlineKeyboardButton(text="🔙 Menu Principal", callback_data="menu")]
    ])

    await safe_edit_message(
        callback.message,
        termos_texto[:4000],
        reply_markup=kb
    )
