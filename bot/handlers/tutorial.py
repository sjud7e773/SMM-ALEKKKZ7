"""
Handler de Tutorial.
=====================
Seção de tutorial para admins (como configurar API,
vender serviços, gerar PIX, usar o painel).
FAQ automatizado com botões de resposta.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from bot.config import is_admin
from bot.utils.helpers import safe_edit_message
from bot.utils.logger import logger

router = Router()


# ==========================================
# TUTORIAL / FAQ
# ==========================================

@router.message(Command("tutorial"))
async def cmd_tutorial(message: Message):
    """Comando /tutorial — abre o guia."""
    if not await is_admin(message.from_user.id):
        await message.answer(
            "📚 <b>TUTORIAL</b>\n\n"
            "Esta seção está disponível apenas para administradores.\n"
            "Se você é um usuário, utilize o menu principal.",
            parse_mode='HTML'
        )
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Configurar API", callback_data="tut:api")],
        [InlineKeyboardButton(text="🛒 Como Vender", callback_data="tut:vender")],
        [InlineKeyboardButton(text="💰 Configurar PIX", callback_data="tut:pix")],
        [InlineKeyboardButton(text="🛠 Usar o Painel", callback_data="tut:painel")],
        [InlineKeyboardButton(text="📊 Entender Margens", callback_data="tut:margens")],
        [InlineKeyboardButton(text="🔄 Sync de Serviços", callback_data="tut:sync")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="tut:faq")],
        [InlineKeyboardButton(text="🔙 Fechar", callback_data="menu")],
    ])

    await message.answer(
        "📚 <b>TUTORIAL — GUIA COMPLETO</b>\n\n"
        "Selecione um tópico para aprender:",
        parse_mode='HTML',
        reply_markup=kb
    )


def _kb_tutorial_voltar():
    """Botão de voltar ao menu tutorial."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Menu Tutorial", callback_data="tut:menu")],
    ])


@router.callback_query(F.data == "tut:menu")
async def callback_tutorial_menu(callback: CallbackQuery):
    """Volta ao menu tutorial."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Configurar API", callback_data="tut:api")],
        [InlineKeyboardButton(text="🛒 Como Vender", callback_data="tut:vender")],
        [InlineKeyboardButton(text="💰 Configurar PIX", callback_data="tut:pix")],
        [InlineKeyboardButton(text="🛠 Usar o Painel", callback_data="tut:painel")],
        [InlineKeyboardButton(text="📊 Entender Margens", callback_data="tut:margens")],
        [InlineKeyboardButton(text="🔄 Sync de Serviços", callback_data="tut:sync")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="tut:faq")],
        [InlineKeyboardButton(text="🔙 Fechar", callback_data="menu")],
    ])

    await safe_edit_message(
        callback.message,
        "📚 <b>TUTORIAL — GUIA COMPLETO</b>\n\n"
        "Selecione um tópico para aprender:",
        reply_markup=kb
    )


@router.callback_query(F.data == "tut:api")
async def callback_tut_api(callback: CallbackQuery):
    """Tutorial: Configurar API."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "🔑 <b>COMO CONFIGURAR A API</b>\n\n"
        "<b>1.</b> Acesse o painel do fornecedor SMM\n"
        "(ex: baratosociais.com)\n\n"
        "<b>2.</b> Vá em <b>Configurações</b> ou <b>API</b>\n\n"
        "<b>3.</b> Copie a <b>API Key</b>\n\n"
        "<b>4.</b> No bot, use <code>/admin</code> → <b>Configurações</b>\n"
        "→ <b>API Key</b>\n\n"
        "<b>5.</b> Cole a API Key e envie\n\n"
        "<b>6.</b> O bot validará automaticamente a chave\n"
        "e mostrará seu saldo no fornecedor\n\n"
        "✅ <b>Dica:</b> Após configurar a API Key,\n"
        "sincronize os serviços para importar\n"
        "automaticamente todos os serviços disponíveis.",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:vender")
async def callback_tut_vender(callback: CallbackQuery):
    """Tutorial: Como Vender."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "🛒 <b>COMO VENDER SERVIÇOS</b>\n\n"
        "<b>1.</b> Configure a API Key (/admin → Config)\n\n"
        "<b>2.</b> Sincronize os serviços (/admin → Serviços → Sync)\n\n"
        "<b>3.</b> Configure a margem de lucro (/admin → Config → Margem)\n"
        "   ➡️ Recomendação: 50% a 100% de lucro\n\n"
        "<b>4.</b> Configure os gateways de pagamento\n"
        "   (/admin → Gateways)\n\n"
        "<b>5.</b> Compartilhe o link do bot com seus clientes\n\n"
        "<b>6.</b> Os clientes adicionam saldo via PIX\n"
        "   e compram serviços automaticamente!\n\n"
        "💡 <b>Dica:</b> Use o sistema de indicação\n"
        "(👥 Indicar Amigo) para atrair mais clientes.",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:pix")
async def callback_tut_pix(callback: CallbackQuery):
    """Tutorial: Configurar PIX."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "💰 <b>COMO CONFIGURAR PIX</b>\n\n"
        "<b>Mercado Pago:</b>\n"
        "1. Crie uma conta no mercadopago.com.br\n"
        "2. Vá em Configurações → Credenciais\n"
        "3. Copie o Access Token (Produção)\n"
        "4. No bot: /admin → Gateways → Mercado Pago\n"
        "5. Cole o token e ative\n\n"
        "<b>Hoopay:</b>\n"
        "1. Crie uma conta no hoopay.com.br\n"
        "2. Gere suas credenciais de API\n"
        "3. No bot: /admin → Gateways → Hoopay\n"
        "4. Configure client_id e client_secret\n\n"
        "⚠️ Ambos os gateways geram QR Code\n"
        "PIX automaticamente para seus clientes!",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:painel")
async def callback_tut_painel(callback: CallbackQuery):
    """Tutorial: Usar o Painel."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "🛠 <b>COMO USAR O PAINEL ADMIN</b>\n\n"
        "Acesse com <code>/admin</code>. Seções:\n\n"
        "📊 <b>Dashboard:</b> Estatísticas gerais\n\n"
        "⚙️ <b>Configurações:</b>\n"
        "• API Key, URL\n"
        "• Margem de lucro\n"
        "• Mensagem inicial do bot\n"
        "• Mensagem de PIX\n\n"
        "🛍 <b>Serviços:</b>\n"
        "• Sincronizar do fornecedor\n"
        "• Ativar/desativar serviços\n\n"
        "💳 <b>Gateways:</b>\n"
        "• Mercado Pago / Hoopay\n"
        "• Configurar credenciais\n\n"
        "👥 <b>Usuários:</b>\n"
        "• Ver lista de clientes\n"
        "• Ajustar saldo\n"
        "• Banir/desbanir",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:margens")
async def callback_tut_margens(callback: CallbackQuery):
    """Tutorial: Entender Margens."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "📊 <b>ENTENDENDO AS MARGENS</b>\n\n"
        "A margem define quanto você lucra em cada pedido.\n\n"
        "<b>Exemplo com margem 75%:</b>\n"
        "• Custo do fornecedor: R$ 10,00\n"
        "• Seu preço: R$ 10,00 × 1.75 = <b>R$ 17,50</b>\n"
        "• Seu lucro: <b>R$ 7,50</b> por pedido\n\n"
        "<b>Dicas de margem:</b>\n"
        "• 30%–50%: Preço competitivo, alto volume\n"
        "• 50%–100%: Equilíbrio ideal\n"
        "• 100%–200%: Alto lucro, clientes premium\n\n"
        "⚠️ Margens muito altas podem afastar clientes.\n"
        "Margens muito baixas reduzem seu lucro.\n\n"
        "💡 <b>Dica:</b> Comece com 75% e ajuste\n"
        "conforme o feedback dos clientes.",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:sync")
async def callback_tut_sync(callback: CallbackQuery):
    """Tutorial: Sync de Serviços."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    await safe_edit_message(
        callback.message,
        "🔄 <b>SINCRONIZAÇÃO DE SERVIÇOS</b>\n\n"
        "A sincronização importa todos os serviços\n"
        "do seu fornecedor SMM para o bot.\n\n"
        "<b>Como funciona:</b>\n"
        "1. O bot consulta a API do fornecedor\n"
        "2. Importa nome, preço, limites de cada serviço\n"
        "3. Organiza por categoria automaticamente\n"
        "4. Calcula preço de venda baseado na sua margem\n\n"
        "<b>Quando sincronizar:</b>\n"
        "• Após configurar a API Key (obrigatório)\n"
        "• Quando o fornecedor adicionar novos serviços\n"
        "• Quando houver alteração de preços\n\n"
        "⏰ O bot sincroniza automaticamente\n"
        "a cada 60 minutos (configurável).\n\n"
        "📍 Caminho: /admin → Serviços → 🔄 Sincronizar",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:faq")
async def callback_tut_faq(callback: CallbackQuery):
    """FAQ."""
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Pedido não aparece?", callback_data="tut:faq1")],
        [InlineKeyboardButton(text="❓ PIX não confirmou?", callback_data="tut:faq2")],
        [InlineKeyboardButton(text="❓ Saldo no fornecedor?", callback_data="tut:faq3")],
        [InlineKeyboardButton(text="❓ Serviço lento?", callback_data="tut:faq4")],
        [InlineKeyboardButton(text="🔙 Menu Tutorial", callback_data="tut:menu")],
    ])

    await safe_edit_message(
        callback.message,
        "❓ <b>PERGUNTAS FREQUENTES (FAQ)</b>\n\n"
        "Selecione uma pergunta:",
        reply_markup=kb
    )


@router.callback_query(F.data == "tut:faq1")
async def callback_faq1(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()
    await safe_edit_message(
        callback.message,
        "❓ <b>PEDIDO NÃO APARECE NO STATUS?</b>\n\n"
        "Possíveis causas:\n"
        "• O pedido ainda está sendo processado\n"
        "• Verifique se o link está correto\n"
        "• O perfil precisa estar público\n"
        "• O fornecedor pode estar com atraso\n\n"
        "💡 O bot verifica status a cada 5 minutos.",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:faq2")
async def callback_faq2(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()
    await safe_edit_message(
        callback.message,
        "❓ <b>PIX NÃO FOI CONFIRMADO?</b>\n\n"
        "Possíveis causas:\n"
        "• O pagamento pode levar até 5 minutos\n"
        "• Verifique se pagou o valor exato\n"
        "• O QR Code pode ter expirado (gere outro)\n"
        "• Verifique as credenciais do gateway\n\n"
        "💡 O bot verifica pagamentos a cada 2 minutos.",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:faq3")
async def callback_faq3(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()
    await safe_edit_message(
        callback.message,
        "❓ <b>SALDO DO FORNECEDOR BAIXO?</b>\n\n"
        "O saldo no fornecedor é usado para\n"
        "processar os pedidos dos seus clientes.\n\n"
        "• Acesse o painel do fornecedor\n"
        "• Adicione saldo via PIX\n"
        "• Depois sincronize no bot\n\n"
        "⚠️ Se o saldo acabar, pedidos ficam pendentes\n"
        "até você adicionar mais saldo.",
        reply_markup=_kb_tutorial_voltar()
    )


@router.callback_query(F.data == "tut:faq4")
async def callback_faq4(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.answer()
    await safe_edit_message(
        callback.message,
        "❓ <b>SERVIÇO ESTÁ LENTO?</b>\n\n"
        "Velocidades de entrega variam por serviço.\n\n"
        "• Serviços 'Default' são mais estáveis\n"
        "• Serviços 'Premium' são mais rápidos\n"
        "• Quantidade grande = mais tempo\n\n"
        "💡 Consulte a descrição de cada serviço\n"
        "para saber a velocidade estimada.",
        reply_markup=_kb_tutorial_voltar()
    )
