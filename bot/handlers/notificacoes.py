"""
Handler de Notificações - Configuração e Envio.
================================================
Permite ao admin configurar notificações de novos usuários e vendas.
Destinos: chat do owner OU grupo/canal configurado.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.database.connection import get_db
from bot.database.queries_owner import buscar_owner
from bot.utils.helpers import safe_edit_message
from bot.utils.logger import logger

router = Router()


class NotificationStates(StatesGroup):
    """Estados para configuração de notificações."""
    aguardando_group_id_usuarios = State()
    aguardando_group_id_vendas = State()
    aguardando_button_text = State()
    aguardando_button_url = State()


# ==========================================
# HELPERS - Banco de Dados
# ==========================================

async def get_notif_setting(chave: str) -> dict:
    """Busca configuração de notificação."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT ativo, destino, valor FROM notification_settings WHERE chave = ?",
            (chave,)
        )
        row = await cursor.fetchone()
        if row:
            return {'ativo': bool(row['ativo']), 'destino': row['destino'], 'valor': row['valor']}
        return {'ativo': False, 'destino': 'owner', 'valor': ''}
    finally:
        await db.close()


async def set_notif_setting(chave: str, ativo: int = None, destino: str = None, valor: str = None):
    """Atualiza ou cria configuração de notificação."""
    db = await get_db()
    try:
        # Verificar se existe
        cursor = await db.execute("SELECT id FROM notification_settings WHERE chave = ?", (chave,))
        exists = await cursor.fetchone()
        
        if exists:
            # UPDATE
            updates = []
            params = []
            if ativo is not None:
                updates.append("ativo = ?")
                params.append(ativo)
            if destino is not None:
                updates.append("destino = ?")
                params.append(destino)
            if valor is not None:
                updates.append("valor = ?")
                params.append(valor)
            
            if updates:
                params.append(chave)
                await db.execute(
                    f"UPDATE notification_settings SET {', '.join(updates)}, atualizado_em = datetime('now') WHERE chave = ?",
                    tuple(params)
                )
        else:
            # INSERT
            await db.execute(
                "INSERT INTO notification_settings (chave, ativo, destino, valor) VALUES (?, ?, ?, ?)",
                (chave, ativo if ativo is not None else 0, destino or 'owner', valor or '')
            )
        
        await db.commit()
    finally:
        await db.close()


# ==========================================
# MENU PRINCIPAL DE NOTIFICAÇÕES
# ==========================================

@router.callback_query(F.data == "notif:menu")
async def callback_notif_menu(callback: CallbackQuery):
    """Menu principal de notificações."""
    await callback.answer()
    
    # Buscar status
    usuarios_cfg = await get_notif_setting('notif_new_user')
    vendas_cfg = await get_notif_setting('notif_sale')
    
    usuarios_status = "🟢 Ativado" if usuarios_cfg['ativo'] else "🔴 Desativado"
    vendas_status = "🟢 Ativado" if vendas_cfg['ativo'] else "🔴 Desativado"
    
    texto = (
        f"🔔 <b>NOTIFICAÇÕES DO SISTEMA</b>\n\n"
        f"Configure notificações automáticas para eventos importantes.\n\n"
        f"👤 <b>Novos Usuários:</b> {usuarios_status}\n"
        f"💰 <b>Vendas Realizadas:</b> {vendas_status}\n\n"
        f"Escolha uma opção para configurar:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Novos Usuários", callback_data="notif:usuarios")],
        [InlineKeyboardButton(text="💰 Vendas Realizadas", callback_data="notif:vendas")],
        [InlineKeyboardButton(text="🧪 Testar Notificação", callback_data="notif:test")],
        [InlineKeyboardButton(text="📊 Ver Status Completo", callback_data="notif:status")],
        [InlineKeyboardButton(text="🔙 Voltar ao Admin", callback_data="adm:menu")],
    ])
    
    await safe_edit_message(callback.message, texto, reply_markup=keyboard)


# ==========================================
# CONFIGURAÇÃO - NOVOS USUÁRIOS
# ==========================================

@router.callback_query(F.data == "notif:usuarios")
async def callback_notif_usuarios(callback: CallbackQuery):
    """Configurar notificação de novos usuários."""
    await callback.answer()
    
    cfg = await get_notif_setting('notif_new_user')
    status = "🟢 Ativado" if cfg['ativo'] else "🔴 Desativado"
    destino = "Chat do Owner" if cfg['destino'] == 'owner' else f"Grupo: {cfg['valor']}"
    
    texto = (
        f"👤 <b>NOTIFICAÇÃO - NOVOS USUÁRIOS</b>\n\n"
        f"<b>Status Atual:</b> {status}\n"
        f"<b>Destino:</b> {destino}\n\n"
        f"<b>Funcionalidade:</b>\n"
        f"Quando um novo usuário envia /start, o bot enviará uma notificação "
        f"com os dados do usuário (nome, @username, ID, data de registro).\n\n"
        f"Escolha uma ação:"
    )
    
    ativar_texto = "🔴 Desativar" if cfg['ativo'] else "🟢 Ativar"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ativar_texto, callback_data="notif:usuarios:toggle")],
        [InlineKeyboardButton(text="📍 Chat do Owner", callback_data="notif:usuarios:dest:owner")],
        [InlineKeyboardButton(text="📍 Grupo/Canal", callback_data="notif:usuarios:dest:group")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="notif:menu")],
    ])
    
    await safe_edit_message(callback.message, texto, reply_markup=keyboard)


@router.callback_query(F.data == "notif:usuarios:toggle")
async def callback_usuarios_toggle(callback: CallbackQuery):
    """Ativar/desativar notificação de usuários."""
    await callback.answer()
    
    cfg = await get_notif_setting('notif_new_user')
    novo_status = 0 if cfg['ativo'] else 1
    await set_notif_setting('notif_new_user', ativo=novo_status)
    
    await callback.answer(f"✅ {'Ativado' if novo_status else 'Desativado'}!", show_alert=True)
    
    # Voltar ao menu de usuários
    await callback_notif_usuarios(callback)


@router.callback_query(F.data == "notif:usuarios:dest:owner")
async def callback_usuarios_dest_owner(callback: CallbackQuery):
    """Configurar destino para chat do owner."""
    await callback.answer()
    
    await set_notif_setting('notif_new_user', destino='owner', valor='')
    await callback.answer("✅ Destino alterado para chat do Owner!", show_alert=True)
    
    await callback_notif_usuarios(callback)


@router.callback_query(F.data == "notif:usuarios:dest:group")
async def callback_usuarios_dest_group(callback: CallbackQuery, state: FSMContext):
    """Solicitar ID do grupo."""
    await callback.answer()
    
    texto = (
        f"📍 <b>CONFIGURAR GRUPO/CANAL</b>\n\n"
        f"Para enviar notificações para um grupo ou canal:\n\n"
        f"1️⃣ Adicione este bot ao grupo/canal\n"
        f"2️⃣ Dê permissão de <b>enviar mensagens</b>\n"
        f"3️⃣ Envie o ID do grupo\n\n"
        f"<b>Como descobrir o ID:</b>\n"
        f"• Use @userinfobot no grupo\n"
        f"• OU envie qualquer mensagem no grupo e depois use /id neste chat\n\n"
        f"<b>Envie o ID do grupo agora:</b>\n"
        f"(Exemplo: <code>-1001234567890</code>)"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Cancelar", callback_data="notif:usuarios")],
    ])
    
    await callback.message.edit_text(texto, parse_mode='HTML', reply_markup=keyboard)
    await state.set_state(NotificationStates.aguardando_group_id_usuarios)


@router.message(NotificationStates.aguardando_group_id_usuarios)
async def receber_group_id_usuarios(message: Message, state: FSMContext):
    """Recebe e valida ID do grupo para usuários."""
    group_id = message.text.strip()
    
    # Validar formato
    try:
        group_id_int = int(group_id)
    except ValueError:
        await message.answer(
            "❌ <b>ID inválido!</b>\n\n"
            "O ID do grupo deve ser um número.\n"
            "Exemplo: <code>-1001234567890</code>\n\n"
            "Tente novamente:",
            parse_mode='HTML'
        )
        return
    
    # Testar envio
    try:
        test_msg = await message.bot.send_message(
            group_id_int,
            "✅ Bot configurado com sucesso!\nAs notificações de novos usuários serão enviadas aqui."
        )
        await test_msg.delete()
        
        # Salvar
        await set_notif_setting('notif_new_user', destino='group', valor=str(group_id_int))
        await state.clear()
        
        await message.answer(
            f"✅ <b>Grupo configurado com sucesso!</b>\n\n"
            f"ID: <code>{group_id_int}</code>\n\n"
            f"As notificações de novos usuários serão enviadas para este grupo.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Voltar", callback_data="notif:usuarios")]
            ])
        )
    except Exception as e:
        await message.answer(
            f"❌ <b>Erro ao enviar mensagem para o grupo!</b>\n\n"
            f"<b>Possíveis causas:</b>\n"
            f"• Bot não foi adicionado ao grupo\n"
            f"• Bot não tem permissão de enviar mensagens\n"
            f"• ID incorreto\n\n"
            f"<b>Erro:</b> <code>{str(e)}</code>\n\n"
            f"Tente novamente:",
            parse_mode='HTML'
        )


# ==========================================
# CONFIGURAÇÃO - VENDAS
# ==========================================

@router.callback_query(F.data == "notif:vendas")
async def callback_notif_vendas(callback: CallbackQuery):
    """Configurar notificação de vendas."""
    await callback.answer()
    
    cfg = await get_notif_setting('notif_sale')
    status = "🟢 Ativado" if cfg['ativo'] else "🔴 Desativado"
    
    # Parse valor JSON (group_id, button_text, button_url)
    import json
    try:
        dados = json.loads(cfg['valor']) if cfg['valor'] else {}
        group_id = dados.get('group_id', '')
        btn_text = dados.get('button_text', 'Comprar Agora')
        btn_url = dados.get('button_url', '')
    except:
        group_id = ''
        btn_text = 'Comprar Agora'
        btn_url = ''
    
    destino_text = f"Grupo: {group_id}" if group_id else "❌ Não configurado"
    
    texto = (
        f"💰 <b>NOTIFICAÇÃO - VENDAS REALIZADAS</b>\n\n"
        f"<b>Status Atual:</b> {status}\n"
        f"<b>Destino:</b> {destino_text}\n"
        f"<b>Botão Personalizado:</b> {btn_text}\n\n"
        f"<b>Funcionalidade:</b>\n"
        f"Quando um pagamento for confirmado, o bot enviará uma notificação "
        f"profissional no grupo/canal com os detalhes da venda e um botão para atrair mais clientes.\n\n"
        f"Escolha uma ação:"
    )
    
    ativar_texto = "🔴 Desativar" if cfg['ativo'] else "🟢 Ativar"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ativar_texto, callback_data="notif:vendas:toggle")],
        [InlineKeyboardButton(text="📍 Configurar Grupo/Canal", callback_data="notif:vendas:dest:group")],
        [InlineKeyboardButton(text="🎨 Personalizar Botão", callback_data="notif:vendas:button")],
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="notif:menu")],
    ])
    
    await safe_edit_message(callback.message, texto, reply_markup=keyboard)


@router.callback_query(F.data == "notif:vendas:toggle")
async def callback_vendas_toggle(callback: CallbackQuery):
    """Ativar/desativar notificação de vendas."""
    await callback.answer()
    
    cfg = await get_notif_setting('notif_sale')
    novo_status = 0 if cfg['ativo'] else 1
    await set_notif_setting('notif_sale', ativo=novo_status)
    
    await callback.answer(f"✅ {'Ativado' if novo_status else 'Desativado'}!", show_alert=True)
    await callback_notif_vendas(callback)


@router.callback_query(F.data == "notif:vendas:dest:group")
async def callback_vendas_dest_group(callback: CallbackQuery, state: FSMContext):
    """Solicitar ID do grupo para vendas."""
    await callback.answer()
    
    texto = (
        f"📍 <b>CONFIGURAR GRUPO/CANAL - VENDAS</b>\n\n"
        f"Para enviar notificações de vendas:\n\n"
        f"1️⃣ Adicione este bot ao grupo/canal\n"
        f"2️⃣ Dê permissão de <b>enviar mensagens</b>\n"
        f"3️⃣ Envie o ID do grupo\n\n"
        f"<b>Envie o ID do grupo agora:</b>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Cancelar", callback_data="notif:vendas")],
    ])
    
    await callback.message.edit_text(texto, parse_mode='HTML', reply_markup=keyboard)
    await state.set_state(NotificationStates.aguardando_group_id_vendas)


@router.message(NotificationStates.aguardando_group_id_vendas)
async def receber_group_id_vendas(message: Message, state: FSMContext):
    """Recebe e valida ID do grupo para vendas."""
    group_id = message.text.strip()
    
    try:
        group_id_int = int(group_id)
    except ValueError:
        await message.answer("❌ ID inválido! Envie um número.", parse_mode='HTML')
        return
    
    # Testar envio
    try:
        test_msg = await message.bot.send_message(
            group_id_int,
            "✅ Bot configurado para notificações de vendas!"
        )
        await test_msg.delete()
        
        # Carregar config anterior
        cfg = await get_notif_setting('notif_sale')
        import json
        try:
            dados = json.loads(cfg['valor']) if cfg['valor'] else {}
        except:
            dados = {}
        
        dados['group_id'] = str(group_id_int)
        
        # Salvar
        await set_notif_setting('notif_sale', valor=json.dumps(dados))
        await state.clear()
        
        await message.answer(
            f"✅ <b>Grupo configurado!</b>\n\n"
            f"ID: <code>{group_id_int}</code>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Voltar", callback_data="notif:vendas")]
            ])
        )
    except Exception as e:
        await message.answer(
            f"❌ Erro: <code>{str(e)}</code>\n\nVerifique se o bot está no grupo com permissões!",
            parse_mode='HTML'
        )


@router.callback_query(F.data == "notif:vendas:button")
async def callback_vendas_button(callback: CallbackQuery, state: FSMContext):
    """Personalizar botão da notificação de venda."""
    await callback.answer()
    
    texto = (
        f"🎨 <b>PERSONALIZAR BOTÃO</b>\n\n"
        f"O botão personalizado aparecerá nas notificações de venda.\n"
        f"Use para direcionar clientes para seu canal, grupo ou site.\n\n"
        f"<b>Envie o TEXTO do botão:</b>\n"
        f"(Exemplo: 'Compre no nosso canal!')"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Cancelar", callback_data="notif:vendas")],
    ])
    
    await callback.message.edit_text(texto, parse_mode='HTML', reply_markup=keyboard)
    await state.set_state(NotificationStates.aguardando_button_text)


@router.message(NotificationStates.aguardando_button_text)
async def receber_button_text(message: Message, state: FSMContext):
    """Recebe texto do botão."""
    btn_text = message.text.strip()
    
    if len(btn_text) > 50:
        await message.answer("❌ Texto muito longo! Máximo 50 caracteres.")
        return
    
    await state.update_data(button_text=btn_text)
    
    await message.answer(
        f"✅ Texto salvo: <b>{btn_text}</b>\n\n"
        f"Agora envie a <b>URL/link</b> do botão:\n"
        f"(Exemplo: https://t.me/seu_canal)",
        parse_mode='HTML'
    )
    
    await state.set_state(NotificationStates.aguardando_button_url)


@router.message(NotificationStates.aguardando_button_url)
async def receber_button_url(message: Message, state: FSMContext):
    """Recebe URL do botão."""
    btn_url = message.text.strip()
    
    if not btn_url.startswith(('http://', 'https://', 't.me/')):
        await message.answer("❌ URL inválida! Deve começar com http://, https:// ou t.me/")
        return
    
    data = await state.get_data()
    btn_text = data.get('button_text', 'Comprar Agora')
    
    # Salvar
    cfg = await get_notif_setting('notif_sale')
    import json
    try:
        dados = json.loads(cfg['valor']) if cfg['valor'] else {}
    except:
        dados = {}
    
    dados['button_text'] = btn_text
    dados['button_url'] = btn_url
    
    await set_notif_setting('notif_sale', valor=json.dumps(dados))
    await state.clear()
    
    await message.answer(
        f"✅ <b>Botão personalizado configurado!</b>\n\n"
        f"<b>Texto:</b> {btn_text}\n"
        f"<b>URL:</b> {btn_url}",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Voltar", callback_data="notif:vendas")]
        ])
    )


# ==========================================
# VER STATUS COMPLETO
# ==========================================

@router.callback_query(F.data == "notif:status")
async def callback_notif_status(callback: CallbackQuery):
    """Mostra status completo das notificações."""
    await callback.answer()
    
    usuarios_cfg = await get_notif_setting('notif_new_user')
    vendas_cfg = await get_notif_setting('notif_sale')
    
    import json
    try:
        vendas_dados = json.loads(vendas_cfg['valor']) if vendas_cfg['valor'] else {}
    except:
        vendas_dados = {}
    
    texto = (
        f"📊 <b>STATUS DAS NOTIFICAÇÕES</b>\n\n"
        f"👤 <b>NOVOS USUÁRIOS</b>\n"
        f"Status: {'🟢 Ativado' if usuarios_cfg['ativo'] else '🔴 Desativado'}\n"
        f"Destino: {('Chat do Owner' if usuarios_cfg['destino'] == 'owner' else f\"Grupo {usuarios_cfg['valor']}\")}\n\n"
        f"💰 <b>VENDAS REALIZADAS</b>\n"
        f"Status: {'🟢 Ativado' if vendas_cfg['ativo'] else '🔴 Desativado'}\n"
        f"Grupo: {vendas_dados.get('group_id', '❌ Não configurado')}\n"
        f"Botão: {vendas_dados.get('button_text', 'Não configurado')}\n"
        f"URL: {vendas_dados.get('button_url', 'Não configurado')}\n\n"
        f"Use o menu para configurar as notificações."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Voltar", callback_data="notif:menu")],
    ])
    
    await safe_edit_message(callback.message, texto, reply_markup=keyboard)


# ==========================================
# TESTAR NOTIFICAÇÃO
# ==========================================

@router.callback_query(F.data == "notif:test")
async def callback_notif_test(callback: CallbackQuery):
    """Envia notificação de teste."""
    await callback.answer()
    
    # Testar envio de novo usuário
    usuarios_cfg = await get_notif_setting('notif_new_user')
    
    if not usuarios_cfg['ativo']:
        await callback.answer("⚠️ Notificação de novos usuários está desativada!", show_alert=True)
        return
    
    owner = await buscar_owner()
    dest_id = owner['telegram_id'] if usuarios_cfg['destino'] == 'owner' else int(usuarios_cfg['valor'])
    
    try:
        await callback.bot.send_message(
            dest_id,
            f"🧪 <b>TESTE - Notificação de Novo Usuário</b>\n\n"
            f"📥 Novo usuário registrado!\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 Nome: Usuário Teste\n"
            f"🔗 @teste_usuario\n"
            f"🆔 ID: 123456789\n"
            f"🕒 Data: 15/02/2026 19:30\n"
            f"━━━━━━━━━━━━━━",
            parse_mode='HTML'
        )
        await callback.answer("✅ Notificação de teste enviada!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Erro: {str(e)}", show_alert=True)
