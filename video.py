import requests
import aria2p
from datetime import datetime
from status import format_progress_bar
import asyncio
import os, time
import logging
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure aria2
aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=6800,
        secret=""
    )
)
options = {
    "max-tries": "50",
    "retry-wait": "3",
    "continue": "true"
}
aria2.set_global_options(options)


# Function to download video
async def download_video(url, reply_msg, user_mention, user_id):
    try:
        # Fetch video details from the API
        response = requests.get(f"https://teraboxvideodownloader.nepcoderdevs.workers.dev/?url={url}")
        response.raise_for_status()
        data = response.json()

        # Extract video details
        resolutions = data["response"][0]["resolutions"]
        fast_download_link = resolutions.get("Fast Download")
        hd_download_link = resolutions.get("HD Video")
        thumbnail_url = data["response"][0]["thumbnail"]
        video_title = data["response"][0]["title"]

        logging.info(f"Video Title: {video_title}, Fast Link: {fast_download_link}, HD Link: {hd_download_link}")

        # Start aria2 download
        download = aria2.add_uris([fast_download_link])
        start_time = datetime.now()

        while not download.is_complete:
            download.update()
            percentage = download.progress
            done = download.completed_length
            total_size = download.total_length
            speed = download.download_speed
            eta = download.eta
            elapsed_time_seconds = (datetime.now() - start_time).total_seconds()

            # Update progress bar
            progress_text = format_progress_bar(
                filename=video_title,
                percentage=percentage,
                done=done,
                total_size=total_size,
                status="Downloading",
                eta=eta,
                speed=speed,
                elapsed=elapsed_time_seconds,
                user_mention=user_mention,
                user_id=user_id,
                aria2p_gid=download.gid
            )
            await reply_msg.edit_text(progress_text)
            await asyncio.sleep(2)

        # Handle download completion
        if download.is_complete:
            file_path = download.files[0].path

            # Save thumbnail locally
            thumbnail_path = "thumbnail.jpg"
            thumbnail_response = requests.get(thumbnail_url)
            with open(thumbnail_path, "wb") as thumb_file:
                thumb_file.write(thumbnail_response.content)

            await reply_msg.edit_text("Uploading the video...")
            return file_path, thumbnail_path, video_title
    except requests.exceptions.RequestException as e:
        logging.error(f"API Request Error: {e}")
        await reply_msg.edit_text(f"❌ Error fetching video details: {e}")
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        buttons = [
            [InlineKeyboardButton("🚀 HD Video", url=hd_download_link)],
            [InlineKeyboardButton("⚡ Fast Download", url=fast_download_link)]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await reply_msg.reply_text(
            "Fast Download Link for this video is broken. Please download manually using the links below.",
            reply_markup=reply_markup
        )
    return None, None, None


# Function to upload video
async def upload_video(client, file_path, thumbnail_path, video_title, reply_msg, collection_channel_id, user_mention, user_id, message):
    file_size = os.path.getsize(file_path)
    uploaded = 0
    start_time = datetime.now()
    last_update_time = time.time()

    # Progress callback
    async def progress(current, total):
        nonlocal uploaded, last_update_time
        uploaded = current
        percentage = (current / total) * 100
        elapsed_time_seconds = (datetime.now() - start_time).total_seconds()

        if time.time() - last_update_time > 2:
            progress_text = format_progress_bar(
                filename=video_title,
                percentage=percentage,
                done=current,
                total_size=total,
                status="Uploading",
                eta=(total - current) / (current / elapsed_time_seconds) if current > 0 else 0,
                speed=current / elapsed_time_seconds if current > 0 else 0,
                elapsed=elapsed_time_seconds,
                user_mention=user_mention,
                user_id=user_id,
                aria2p_gid=""
            )
            try:
                await reply_msg.edit_text(progress_text)
                last_update_time = time.time()
            except Exception as e:
                logging.warning(f"Error updating progress message: {e}")

    # Upload video
    with open(file_path, 'rb') as file:
        collection_message = await client.send_video(
            chat_id=collection_channel_id,
            video=file,
            caption=f"✨ {video_title}\n👤 Leech by: {user_mention}\n📥 User Link: tg://user?id={user_id}",
            thumb=thumbnail_path,
            progress=progress
        )
        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=collection_channel_id,
            message_id=collection_message.id
        )
        await asyncio.sleep(1)
        await message.delete()

    # Cleanup
    await reply_msg.delete()
    sticker_message = await message.reply_sticker("CAACAgIAAxkBAAEZdwRmJhCNfFRnXwR_lVKU1L9F3qzbtAAC4gUAAj-VzApzZV-v3phk4DQE")
    os.remove(file_path)
    os.remove(thumbnail_path)
    await asyncio.sleep(5)
    await sticker_message.delete()
    return collection_message.id
