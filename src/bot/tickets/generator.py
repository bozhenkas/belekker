import os
from pathlib import Path
from PIL import Image
import qrcode
import logging
import asyncio

# Захардкодленные пути для продакшена (Docker)
TICKET_TEMPLATE_PATH = Path("/app/src/bot/tickets/ticket_template.png")
TICKETS_DIR = Path("/app/src/bot/tickets/tickets")
TICKET_BOT_USERNAME = 'be_lekker_bot'

async def generate_ticket_image(
        token: str,
        bot_username: str,
        template_path: Path,
        qr_size: tuple[int, int],
        qr_position: tuple[int, int],
        output_dir: Path
) -> str:
    logging.info(f"Template path: {template_path}")
    logging.info(f"Output dir: {output_dir}")
    if not template_path.exists():
        logging.error(f"Template file does not exist: {template_path}")
        raise FileNotFoundError(f"Template file does not exist: {template_path}")
    os.makedirs(output_dir, exist_ok=True)
    qr_data = f"https://t.me/{bot_username}?start={token}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color=(70, 70, 70), back_color="transparent")
    qr_img = qr_img.resize(qr_size, Image.Resampling.LANCZOS)
    ticket_img = Image.open(template_path).convert("RGBA")
    ticket_img.paste(qr_img, qr_position, qr_img)
    ticket_img = ticket_img.convert("RGB")
    ticket_path = output_dir / f"ticket_{token}.jpg"
    ticket_img.save(ticket_path)
    logging.info(f"Ticket saved at: {ticket_path}")
    return str(ticket_path)