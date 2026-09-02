import os
import json
import asyncio
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import (
    Application,
    ChatMemberHandler,
    ContextTypes,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
CANAL_ID = -1002452324945
DURACION_DIAS = 30
ARCHIVO_DATOS = "suscriptores.json"


def cargar_suscriptores():
    try:
        with open(ARCHIVO_DATOS, "r") as archivo:
            return json.load(archivo)
    except FileNotFoundError:
        return {}


def guardar_suscriptores(suscriptores):
    with open(ARCHIVO_DATOS, "w") as archivo:
        json.dump(suscriptores, archivo, indent=2)


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

        suscriptores = cargar_suscriptores()
        usuario_id = str(usuario.id)

        if usuario_id not in suscriptores:

            vencimiento = (
                datetime.now(timezone.utc)
                + timedelta(days=DURACION_DIAS)
            )

            suscriptores[usuario_id] = {
                "nombre": usuario.full_name,
                "vence": vencimiento.isoformat(),
                "estado": "activo"
            }

            guardar_suscriptores(suscriptores)

            print(
                f"NUEVO SUSCRIPTOR: {usuario.full_name} | "
                f"Vence: {vencimiento.date()}"
            )

        else:
            datos = suscriptores[usuario_id]

            print(
                f"USUARIO YA REGISTRADO: {usuario.full_name} | "
                f"Estado: {datos.get('estado', 'activo')} | "
                f"Vence: {datos['vence']}"
            )


async def revisar_vencimientos(context: ContextTypes.DEFAULT_TYPE):
    suscriptores = cargar_suscriptores()
    ahora = datetime.now(timezone.utc)
    cambios = False

    for usuario_id, datos in suscriptores.items():

        # Si ya fue marcado como vencido, no hacemos nada más.
        if datos.get("estado") == "vencido":
            continue

        vencimiento = datetime.fromisoformat(datos["vence"])

        if ahora >= vencimiento:
            try:
                await context.bot.ban_chat_member(
                    chat_id=CANAL_ID,
                    user_id=int(usuario_id)
                )

                datos["estado"] = "vencido"
                cambios = True

                print(
                    f"SUSCRIPCIÓN VENCIDA Y USUARIO EXPULSADO: "
                    f"{datos['nombre']}"
                )

            except Exception as error:
                print(
                    f"ERROR AL EXPULSAR A {datos['nombre']}: {error}"
                )

    if cambios:
        guardar_suscriptores(suscriptores)


async def main():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        ChatMemberHandler(
            nuevo_suscriptor,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    application.job_queue.run_repeating(
        revisar_vencimientos,
        interval=3600,
        first=10
    )

    print("BOT INICIADO")
    print("ESPERANDO CAMBIOS EN EL CANAL...")

    await application.initialize()
    await application.start()

    await application.updater.start_polling(
        allowed_updates=["chat_member"]
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
