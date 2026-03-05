import os
import asyncio
import shutil
import img2pdf
import cloudscraper
from bs4 import BeautifulSoup
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

if TELEGRAM_API_URL:
    UNIVERSAL_LIMIT_BYTES = 1.9 * 1024 * 1024 * 1024 
    session = AiohttpSession(api=TelegramAPIServer.from_base(TELEGRAM_API_URL))
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    UNIVERSAL_LIMIT_BYTES = 45 * 1024 * 1024
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

class DownloadFlow(StatesGroup):
    waiting_for_url = State()
    waiting_for_name = State()

async def handle_ping(request):
    return web.Response(text="Comic Bot is running securely with Cloudflare Bypass!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- THE CLOUDFLARE BUSTER FALLBACK SCRAPER ---
async def universal_fallback_scraper(url, temp_dir):
    """A Cloudflare-bypassing scraper for WP-Manga/Madara sites."""
    try:
        # Create a Cloudscraper instance that mimics a real Chrome browser
        scraper = cloudscraper.create_scraper(browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        })
        
        # Fetch the page bypassing Cloudflare
        response = await asyncio.to_thread(scraper.get, url, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        images = []
        # Target standard Madara/WP-Manga image classes
        for img in soup.select('.reading-content img, .wp-manga-chapter-img'):
            src = img.get('data-src') or img.get('src')
            if src:
                src = src.strip()
                if src.startswith('http'):
                    images.append(src)
        
        if not images:
            return False 
            
        # Download images using the same Cloudflare-bypassing session
        for i, img_url in enumerate(images):
            img_res = await asyncio.to_thread(scraper.get, img_url)
            with open(os.path.join(temp_dir, f"page_{i:03d}.jpg"), 'wb') as f:
                f.write(img_res.content)
                
        return True
    except Exception as e:
        print(f"Fallback Error: {e}")
        return False

# --- BOT LOGIC ---
@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await message.answer("📚 Send me a comic/manga URL from almost any site to start downloading!")
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

    status_msg = await message.answer("🚀 Starting extraction...")
    temp_dir = f"/tmp/comic_{message.message_id}"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        await status_msg.edit_text("⬇️ Downloading via gallery-dl...")
        process = await asyncio.create_subprocess_shell(
            f'gallery-dl --directory "{temp_dir}" "{url}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        error_log = stderr.decode('utf-8').strip() or stdout.decode('utf-8').strip()

        # --- THE FALLBACK HOOK ---
        if "Unsupported URL" in error_log or "403 Forbidden" in error_log:
            await status_msg.edit_text("⚠️ Site blocked or unsupported by primary tool. Engaging Cloudflare Buster...")
            fallback_success = await universal_fallback_scraper(url, temp_dir)
            
            if not fallback_success:
                await status_msg.edit_text(f"❌ **Both Scrapers Failed.** \nThe site either has extreme protection, or the link is to a main gallery instead of a readable chapter.\n\n`{error_log[:200]}`", parse_mode="Markdown")
                return

        # 2. Find images
        await status_msg.edit_text("⚙️ Compiling downloaded files...")
        image_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in sorted(files):
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    image_files.append(os.path.join(root, file))

        if not image_files:
            await status_msg.edit_text("❌ No images found after scanning.")
            return

        base_name = custom_name if custom_name.lower() != 'skip' else "Comic_Download"
        base_name = base_name.replace(" ", "_")

        await process_and_upload_in_chunks(image_files, base_name, message, status_msg)
        await status_msg.delete()

    except Exception as e:
        await message.answer(f"❌ An error occurred: {str(e)}")
    
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        await state.clear()

async def process_and_upload_in_chunks(image_paths, base_name, message_obj, status_msg):
    current_batch = []
    current_batch_size = 0
    part_num = 1
    
    for img_path in image_paths:
        img_size = os.path.getsize(img_path)
        if current_batch_size + img_size > UNIVERSAL_LIMIT_BYTES:
            await package_and_upload(current_batch, base_name, part_num, message_obj, status_msg)
            part_num += 1
            current_batch = [img_path]
            current_batch_size = img_size
        else:
            current_batch.append(img_path)
            current_batch_size += img_size

    if current_batch:
        if part_num == 1:
            await package_and_upload(current_batch, base_name, None, message_obj, status_msg)
        else:
            await package_and_upload(current_batch, base_name, part_num, message_obj, status_msg)

async def package_and_upload(image_batch, base_name, part_num, message_obj, status_msg):
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
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
