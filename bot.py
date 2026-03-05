import os
import asyncio
import shutil
import img2pdf
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, FSInputFile
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

# --- CONFIGURATION & SMART DETECTION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API_URL = os.environ.get("TELEGRAM_API_URL")

# Smartly decide which limits to use based on the environment variables
if TELEGRAM_API_URL:
    # PRO MODE: 1.9 GB Limit (Using Custom Local Server)
    UNIVERSAL_LIMIT_BYTES = 1.9 * 1024 * 1024 * 1024 
    session = AiohttpSession(api=TelegramAPIServer.from_base(TELEGRAM_API_URL))
    bot = Bot(token=BOT_TOKEN, session=session)
    print(f"Starting in PRO MODE (1.9GB limit) using API: {TELEGRAM_API_URL}")
else:
    # STANDARD MODE: 45 MB Limit (Safe for standard Telegram API and Render Free Tier)
    UNIVERSAL_LIMIT_BYTES = 45 * 1024 * 1024
    bot = Bot(token=BOT_TOKEN)
    print("Starting in STANDARD MODE (45MB limit) using default Telegram API.")

dp = Dispatcher()

class DownloadFlow(StatesGroup):
    waiting_for_url = State()
    waiting_for_name = State()

# --- RENDER WEB SERVER PING ---
# Render requires a web service to bind to a port to stay alive
async def handle_ping(request):
    mode = "PRO (1.9GB)" if TELEGRAM_API_URL else "STANDARD (45MB)"
    return web.Response(text=f"Comic Bot is running securely in {mode} mode!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- BOT LOGIC ---
@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    max_size = "1.9GB" if TELEGRAM_API_URL else "45MB"
    await message.answer(f"📚 Send me a comic/manga URL from almost any site to start downloading!\n\n*(Current Chunk Limit: {max_size})*")
    await state.set_state(DownloadFlow.waiting_for_url)

@dp.message(DownloadFlow.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    await state.update_data(url=message.text)
    await message.answer("URL received! \n\nType a **custom name** for the PDF, or reply with **'skip'** to use the default name.")
    await state.set_state(DownloadFlow.waiting_for_name)

@dp.message(DownloadFlow.waiting_for_name)
async def process_name_and_download(message: Message, state: FSMContext):
    user_data = await state.get_data()
    url = user_data['url']
    custom_name = message.text

    status_msg = await message.answer("🚀 Starting extraction... (This may take a while)")
    
    # Create a unique temporary directory for this download
    temp_dir = f"/tmp/comic_{message.message_id}"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # 1. Download with gallery-dl
        await status_msg.edit_text("⬇️ Downloading images via gallery-dl...")
        process = await asyncio.create_subprocess_shell(
            f'gallery-dl --directory "{temp_dir}" "{url}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        # 2. Find images
        await status_msg.edit_text("⚙️ Analyzing downloaded files...")
        image_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in sorted(files):
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    image_files.append(os.path.join(root, file))

        if not image_files:
            await status_msg.edit_text("❌ No images found. Site might be protected or link is invalid.")
            return

        # 3. Handle Naming
        base_name = custom_name if custom_name.lower() != 'skip' else "Comic_Download"
        base_name = base_name.replace(" ", "_")

        # 4. Trigger the smart PDF chunking system
        await process_and_upload_in_chunks(image_files, base_name, message, status_msg)
        await status_msg.delete()

    except Exception as e:
        await message.answer(f"❌ An error occurred: {str(e)}")
    
    finally:
        # 5. Clean up server space!
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        await state.clear()


async def process_and_upload_in_chunks(image_paths, base_name, message_obj, status_msg):
    """Packages images into PDFs and uploads BEFORE hitting the size limit."""
    current_batch = []
    current_batch_size = 0
    part_num = 1
    
    for img_path in image_paths:
        img_size = os.path.getsize(img_path)
        
        # Check if adding this image exceeds our limit
        if current_batch_size + img_size > UNIVERSAL_LIMIT_BYTES:
            await package_and_upload(current_batch, base_name, part_num, message_obj, status_msg)
            part_num += 1
            current_batch = [img_path]
            current_batch_size = img_size
        else:
            current_batch.append(img_path)
            current_batch_size += img_size

    # Upload the remaining files
    if current_batch:
        if part_num == 1: # Only 1 part needed
            await package_and_upload(current_batch, base_name, None, message_obj, status_msg)
        else:
            await package_and_upload(current_batch, base_name, part_num, message_obj, status_msg)


async def package_and_upload(image_batch, base_name, part_num, message_obj, status_msg):
    """Converts a batch to PDF, uploads it, and deletes the local file."""
    pdf_filename = f"{base_name}_Part_{part_num}.pdf" if part_num else f"{base_name}.pdf"
    pdf_path = f"/tmp/{pdf_filename}"
    
    await status_msg.edit_text(f"⚙️ Compiling {pdf_filename}...")
    
    try:
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(image_batch))
            
        await status_msg.edit_text(f"⬆️ Uploading {pdf_filename}...")
        document = FSInputFile(pdf_path)
        await message_obj.answer_document(document)
        
    finally:
        # Delete PDF to free space immediately
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
