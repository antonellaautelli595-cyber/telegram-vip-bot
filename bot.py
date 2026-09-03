import os
import json
import asyncio
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    ChatMemberHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)


BOT_TOKEN = os.environ["BOT_TOKEN"]

CANAL_ID = -1002452324945

# TU ID DE TELEGRAM
ADMIN_ID = 8765547410

ARCHIVO_DATOS = "suscriptores.json"


def cargar_suscriptores():
    try:
        with open(ARCHIVO_DATOS, "r") as archivo:
            return json.load(archivo)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_suscriptores(suscriptores):
    with open(ARCHIVO_DATOS, "w") as archivo:
        json.dump(suscriptores, archivo, indent=2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 Bot VIP activo.\n\n"
        "Yo me encargo de controlar los vencimientos del canal."
    )


async def nuevo_suscriptor(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cambio = update.chat_member

    if not cambio or cambio.chat.id != CANAL_ID:
        return

    estado_anterior = cambio.old_chat_member.status
    estado_nuevo = cambio.new_chat_member.status
    usuario = cambio.new_chat_member.user

    print(
        f"CAMBIO DETECTADO: {usuario.full_name} | "
        f"{estado_anterior} -> {estado_nuevo}"
    )

    if estado_anterior in ("left", "kicked") and estado_nuevo == "member":

        usuario_id = str(usuario.id)

        teclado = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📅 7 días",
                    callback_data=f"duracion_7_{usuario.id}"
                ),
                InlineKeyboardButton(
                    "📅 15 días",
                    callback_data=f"duracion_15_{usuario.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🗓️ 1 mes",
                    callback_data=f"duracion_30_{usuario.id}"
                ),
                InlineKeyboardButton(
                    "🗓️ 2 meses",
                    callback_data=f"duracion_60_{usuario.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "✍️ Elegir fecha",
                    callback_data=f"fecha_{usuario.id}"
                )
            ]
        ])

        nombre_usuario = (
            f"@{usuario.username}"
            if usuario.username
            else "Sin nombre de usuario"
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🔔 ¡NUEVO MIEMBRO EN EL VIP!\n\n"
                f"👤 Nombre: {usuario.full_name}\n"
                f"📱 Usuario: {nombre_usuario}\n"
                f"🆔 ID: {usuario.id}\n\n"
                "¿Cuánto tiempo tendrá acceso?"
            ),
            reply_markup=teclado
        )

        print(f"NUEVO MIEMBRO DETECTADO: {usuario.full_name}")


async def elegir_duracion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    consulta = update.callback_query

    if consulta.from_user.id != ADMIN_ID:
        await consulta.answer(
            "No tenés permiso para usar estos botones.",
            show_alert=True
        )
        return

    await consulta.answer()

    partes = consulta.data.split("_")

    if partes[0] == "duracion":

        dias = int(partes[1])
        usuario_id = partes[2]

        vencimiento = (
            datetime.now(timezone.utc)
            + timedelta(days=dias)
        )

        suscriptores = cargar_suscriptores()

        suscriptores[usuario_id] = {
            "nombre": "Usuario VIP",
            "vence": vencimiento.isoformat(),
            "estado": "activo"
        }

        guardar_suscriptores(suscriptores)

        await consulta.edit_message_text(
            text=(
                "✅ ACCESO CONFIGURADO\n\n"
                f"⏳ Duración: {dias} días\n"
                f"📅 Vence: {vencimiento.strftime('%d/%m/%Y')}\n\n"
                "El bot eliminará automáticamente "
                "a esta persona cuando venza su acceso."
            )
        )

        print(
            f"SUSCRIPCIÓN CONFIGURADA: "
            f"{usuario_id} | {dias} días"
        )

    elif partes[0] == "fecha":

        usuario_id = partes[1]

        context.user_data[
            "usuario_fecha_personalizada"
        ] = usuario_id

        await consulta.edit_message_text(
            "📅 FECHA PERSONALIZADA\n\n"
            "Ahora escribime la fecha de vencimiento "
            "en este formato:\n\n"
            "DD/MM/AAAA\n\n"
            "Por ejemplo:\n"
            "15/11/2026"
        )


async def recibir_fecha_personalizada(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        return

    usuario_id = context.user_data.get(
        "usuario_fecha_personalizada"
    )

    if not usuario_id:
        return

    texto = update.message.text.strip()

    try:

        fecha = datetime.strptime(
            texto,
            "%d/%m/%Y"
        )

        vencimiento = fecha.replace(
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone.utc
        )

        suscriptores = cargar_suscriptores()

        suscriptores[usuario_id] = {
            "nombre": "Usuario VIP",
            "vence": vencimiento.isoformat(),
            "estado": "activo"
        }

        guardar_suscriptores(suscriptores)

        del context.user_data[
            "usuario_fecha_personalizada"
        ]

        await update.message.reply_text(
            "✅ FECHA CONFIGURADA\n\n"
            f"📅 Esta persona tendrá acceso hasta "
            f"el {vencimiento.strftime('%d/%m/%Y')}.\n\n"
            "El bot la eliminará automáticamente "
            "cuando llegue esa fecha."
        )

    except ValueError:

        await update.message.reply_text(
            "❌ No entendí la fecha.\n\n"
            "Escribila así:\n"
            "DD/MM/AAAA\n\n"
            "Por ejemplo:\n"
            "15/11/2026"
        )


async def revisar_vencimientos(
    context: ContextTypes.DEFAULT_TYPE
):

    suscriptores = cargar_suscriptores()

    ahora = datetime.now(timezone.utc)

    cambios = False

    for usuario_id, datos in suscriptores.items():

        if datos.get("estado") == "vencido":
            continue

        vencimiento = datetime.fromisoformat(
            datos["vence"]
        )

        if ahora >= vencimiento:

            try:

                await context.bot.ban_chat_member(
                    chat_id=CANAL_ID,
                    user_id=int(usuario_id)
                )

                datos["estado"] = "vencido"
                cambios = True

                print(
                    f"SUSCRIPCIÓN VENCIDA: {usuario_id}"
                )

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        "⛔ ACCESO VENCIDO\n\n"
                        f"🆔 Usuario: {usuario_id}\n"
                        "📅 Su suscripción terminó."
                    )
                )

            except Exception as error:

                print(
                    f"ERROR AL EXPULSAR "
                    f"A {usuario_id}: {error}"
                )

    if cambios:
        guardar_suscriptores(suscriptores)


async def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Responde al comando /start
    application.add_handler(
        CommandHandler("start", start)
    )

    # Detecta cuando alguien entra o sale
    application.add_handler(
        ChatMemberHandler(
            nuevo_suscriptor,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    # Detecta los botones
    application.add_handler(
        CallbackQueryHandler(elegir_duracion)
    )

    # Recibe una fecha personalizada
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            recibir_fecha_personalizada
        )
    )

    # Revisa los vencimientos cada hora
    application.job_queue.run_repeating(
        revisar_vencimientos,
        interval=3600,
        first=10
    )

    print("BOT INICIADO")
    print("ESPERANDO NUEVOS MIEMBROS...")

    await application.initialize()
    await application.start()

    await application.updater.start_polling(
        allowed_updates=[
            "chat_member",
            "callback_query",
            "message"
        ]
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
