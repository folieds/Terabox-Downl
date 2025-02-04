import requests
import aria2p
from datetime import datetime, timedelta
import asyncio
import os
import time
import logging
import html

# Store user downloads count
user_downloads = {}

aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=6800,
        secret=""
    )
)

# Function to generate a progress bar
def generate_progress_bar(percentage, length=20):
    completed = int(length * percentage / 100)
    remaining = length - completed
    return "█" * completed + "░" * remaining

async def check_download_limit(user_id, user_mention, reply_msg):
    today = datetime.now().date()
    
    # Reset daily limit at midnight
    if user_id in user_downloads:
        last_download_date = user_downloads[user_id]["date"]
        if last_download_date != today:
            user_downloads[user_id] = {"count": 0, "date": today}

    # Check if user exceeded the limit
    if user_id in user_downloads and user_downloads[user_id]["count"] >= 3:
        warning_message = f"""
<b><blockquote>⚠️ Daily Limit Exceeded</blockquote></b>

<i>Hello <a href="tg://user?id={user_id}">{html.escape(user_mention)}</a>,</i>  
You have already downloaded <b>3 files</b> today.  
Please wait until <b>Midnight</b> to download again.  

<b>If You Want To Continue Your Downloading Then Check Out Our Second Bot!!
🤖 @TeraboxVideosRoBot
🤖 @TeraboxVideosRoBot</b>
"""
        await reply_msg.edit_text(warning_message, parse_mode="HTML")
        return False
    
    return True

async def download_video(url, reply_msg, user_mention, user_id):
    try:
        if not await check_download_limit(user_id, user_mention, reply_msg):
            return None, None

        response = requests.get(f"https://pika-terabox-dl.vercel.app/?url={url}")
        response.raise_for_status()
        data = response.json()

        if not data.get("ok") or "downloadLink" not in data or "filename" not in data:
            raise Exception("Invalid API response format")

        fast_download_link = data["downloadLink"]
        video_title = data["filename"]

        download = aria2.add_uris([fast_download_link])
        start_time = datetime.now()

        while not download.is_complete:
            download.update()
            percentage = download.progress
            done = download.completed_length
            total_size = download.total_length
            speed = download.download_speed
            eta = int(download.eta.total_seconds()) if isinstance(download.eta, timedelta) else int(download.eta)
            elapsed_time = int((datetime.now() - start_time).total_seconds())

            progress_bar = generate_progress_bar(percentage)

            progress_text = f"""
<b>📂 File Name :</b> <code>{html.escape(video_title)}</code>
<b>______________________________</b>
<b>📊 Progress :</b> <code>{percentage:.2f}%</code> | <code>[{progress_bar}]</code>
<b>📹 Size :</b> <code>{done / (1024 * 1024):.2f}MB / {total_size / (1024 * 1024):.2f}MB</code>
<b>⚙️ Status :</b> <code><i>Downloading...</i></code>
<b>🚀 Speed :</b> <code>{speed / (1024 * 1024):.2f} MB/s</code>
<b>⏳ Elapsed Time :</b> <code>{elapsed_time // 60}m {elapsed_time % 60}s</code>
<b>⏰ ETA :</b> <code>{eta // 60}m {eta % 60}s</code>
<b>______________________________</b>
<b>👤 User :</b> <a href="tg://user?id={user_id}">{html.escape(user_mention)}</a> | <b>📮 ID</b> <code>{user_id}</code>
<b>______________________________</b>"""
            await reply_msg.edit_text(progress_text, parse_mode="HTML")
            await asyncio.sleep(2)

        if download.is_complete:
            file_path = download.files[0].path
            await reply_msg.edit_text("✅ <b>Download Complete! Uploading...</b>", parse_mode="HTML")

            # Increment user's download count
            if user_id not in user_downloads:
                user_downloads[user_id] = {"count": 1, "date": datetime.now().date()}
            else:
                user_downloads[user_id]["count"] += 1

            return file_path, video_title  
        else:
            raise Exception("Download failed")

    except Exception as e:
        logging.error(f"Error in download_video: {e}")
        await reply_msg.edit_text("⚠️ <b>Error downloading the video. Please try again later.</b>", parse_mode="HTML")
        return None, None

async def upload_video(client, file_path, video_title, reply_msg, collection_channel_id, user_mention, user_id, message):
    try:
        file_size = os.path.getsize(file_path)
        uploaded = 0
        start_time = datetime.now()
        last_update_time = time.time()

        async def progress(current, total):
            nonlocal uploaded, last_update_time
            uploaded = current
            percentage = (current / total) * 100
            elapsed_time = int((datetime.now() - start_time).total_seconds())

            if time.time() - last_update_time > 2:
                progress_bar = generate_progress_bar(percentage)

                progress_text = f"""
<b>📂 File Name :</b> <code>{html.escape(video_title)}</code>
<b>______________________________</b>
<b>📊 Progress :</b> <code>{percentage:.2f}%</code> | <code>[{progress_bar}]</code>
<b>📹 Size :</b> <code>{uploaded / (1024 * 1024):.2f}MB / {file_size / (1024 * 1024):.2f}MB</code>
<b>⚙️ Status :</b> <i>Uploading...</i>
<b>🚀 Speed :</b> <code>{uploaded / (1024 * 1024) / elapsed_time:.2f} MB/s</code>
<b>⏳ Elapsed Time :</b> <code>{elapsed_time // 60}m {elapsed_time % 60}s</code>
<b>______________________________</b>
<b>👤 User :</b> <a href="tg://user?id={user_id}">{html.escape(user_mention)}</a> | <b>📮 ID</b> <code>{user_id}</code>
<b>______________________________</b>"""
                try:
                    await reply_msg.edit_text(progress_text, parse_mode="HTML")
                    last_update_time = time.time()
                except Exception as e:
                    logging.warning(f"Error updating progress message: {e}")

        with open(file_path, 'rb') as file:
            collection_message = await client.send_video(
                chat_id=collection_channel_id,
                video=file,
                caption=f"✨ {html.escape(video_title)}\n👤 Uploaded by : {html.escape(user_mention)}\n📥 User Link: [{html.escape(user_mention)}](tg://user?id={user_id})\n\nJoin : @PythonBotz",
                progress=progress
            )

            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=collection_channel_id,
                message_id=collection_message.id
            )

        await reply_msg.delete()
        os.remove(file_path)
        return collection_message.id

    except Exception as e:
        logging.error(f"Error in upload_video: {e}")
        await reply_msg.edit_text("⚠️ <b>Error uploading the video. Please try again later.</b>", parse_mode="HTML")
        return None
                                           
