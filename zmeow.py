import asyncio
import random
from telethon import TelegramClient, events
# >>> StringSession इम्पोर्ट किया गया
from telethon.sessions import StringSession
from telethon.errors import (
    PeerIdInvalidError, ChannelPrivateError, ChatWriteForbiddenError,
    ChatAdminRequiredError, FloodWaitError, MessageNotModifiedError
)
import pickle
import os

# --- Configuration (Set by User) ---
api_id = 28415534
api_hash = '86b77cc6b5412617a62c50a4f1ac7df7'

# --- User-Provided Credentials ---
owner_id = 6492197417 # <<< Owner ID
track_channel = 'kenlogs1' # <<< Track Channel Username

# --- Base64 Session String (Provided by User) ---
SESSION_STRING = '1BVtsOLEBu3-mapM7uklP71ObcgddNvLciStp68jnuIBtpUvQPXTW9ZLg3zs1T6hRe79Hy1RwY0v3klh84VyezUdg7m3X2L05f-Q5Gqbn0fzpgmjibZ2iWNswRdrpVXxxLSgAlQTTvhPb0eg1Re0Kr26JlCr0KmgN91p-3mycBz7cJ95HqKyYQ4uWxz0gsPiUOkKPk-BbUzssf6oS65yuyHY0OHIOlWEsHFANPyHeM3fkt4LhUGhndzVF3gFC_IX-tabQW0QDodSAJZZjCI7eduleH9QZ2ykzCFo4H04mh6gxuW1KPxkObL6aesa1z-ZSpJe5q4RifVwgu-YLoNXjH1HgfR8v-54='


# Initialize client using StringSession for automatic login
client = TelegramClient(StringSession(SESSION_STRING), api_id, api_hash)

active_process = None
stop_signal = False
group_delay = 65
process_delay = 3800
platform_links = {}
current_platform = None
cached_message = None
cached_entity = None
cached_groups = []
cached_entities = {}

greeting_msg_data = None
greeted_users = set()
saved_tasks = {}
GREETING_FILE = 'greeting_data.pkl'
USERS_FILE = 'greeted_users.pkl'
TASKS_FILE = 'saved_tasks.pkl'

def load_greeting_data():
    global greeting_msg_data, greeted_users
    try:
        if os.path.exists(GREETING_FILE):
            with open(GREETING_FILE, 'rb') as f:
                greeting_msg_data = pickle.load(f)
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'rb') as f:
                greeted_users = pickle.load(f)
    except:
        greeting_msg_data = None
        greeted_users = set()

def save_greeting_data():
    try:
        if greeting_msg_data:
            with open(GREETING_FILE, 'wb') as f:
                pickle.dump(greeting_msg_data, f)
        with open(USERS_FILE, 'wb') as f:
            pickle.dump(greeted_users, f)
    except Exception as e:
        print(f"Error saving greeting: {e}")

def load_tasks():
    global saved_tasks
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, 'rb') as f:
                saved_tasks = pickle.load(f)
    except:
        saved_tasks = {}

def save_tasks():
    try:
        with open(TASKS_FILE, 'wb') as f:
            pickle.dump(saved_tasks, f)
    except Exception as e:
        print(f"Error saving tasks: {e}")

from telethon.tl.functions.messages import ForwardMessagesRequest
from telethon.tl.types import UpdateNewMessage, UpdateNewChannelMessage

async def cache_all_dialogs():
    global cached_groups, cached_entities
    try:
        cached_groups = []
        cached_entities = {}
        async for dialog in client.iter_dialogs():
            if hasattr(dialog.entity, 'username') and dialog.entity.username:
                cached_entities[dialog.entity.username.lower()] = dialog.entity
            cached_entities[str(dialog.entity.id)] = dialog.entity
            if dialog.is_group and not (hasattr(dialog.entity, 'forum') and dialog.entity.forum):
                if hasattr(dialog, 'top_message') and dialog.top_message == 1:
                    continue
                cached_groups.append(dialog)
        print(f"✅ Cached {len(cached_groups)} groups and {len(cached_entities)} entities")
        return True
    except Exception as e:
        print(f"❌ Error caching dialogs: {e}")
        return False

def get_entity_from_cache(identifier):
    return cached_entities.get(identifier.lower() if isinstance(identifier, str) and not identifier.isdigit() else str(identifier))

def parse_topic_link(link):
    try:
        if link.startswith("https://t.me/c/"):
            parts = link.replace("https://t.me/c/", "").split("/")
            channel_id = int(f"-100{parts[0]}")
            topic_id = int(parts[1])
            return channel_id, topic_id
        elif link.startswith("https://t.me/"):
            parts = link.replace("https://t.me/", "").split("/")
            username = parts[0]
            topic_id = int(parts[1])
            return username, topic_id
        return None, None
    except:
        return None, None

async def forward_to_single_topic(reply_message, link):
    try:
        identifier, topic_id = parse_topic_link(link)
        if not identifier or not topic_id:
            return False
        if isinstance(identifier, int):
            try:
                entity = await client.get_entity(identifier)
            except Exception:
                entity = get_entity_from_cache(str(identifier))
                if not entity:
                    print(f"❌ Private channel {identifier} not found in cache")
                    return False
        else:
            entity = get_entity_from_cache(identifier)
            if not entity:
                try:
                    entity = await client.get_entity(identifier)
                except Exception:
                    print(f"❌ Public channel {identifier} not accessible")
                    return False
        result = await client(ForwardMessagesRequest(
            from_peer=reply_message.chat,
            to_peer=entity,
            id=[reply_message.id],
            with_my_score=False,
            drop_author=False,
            top_msg_id=topic_id
        ))
        forwarded_msg = None
        for update in result.updates:
            if isinstance(update, (UpdateNewMessage, UpdateNewChannelMessage)):
                forwarded_msg = update.message
                break
        if forwarded_msg:
            if link.startswith("https://t.me/c/"):
                channel_part = link.split("/")[4]
                track_link = f"https://t.me/c/{channel_part}/{forwarded_msg.id}"
            else:
                username = identifier
                track_link = f"https://t.me/{username}/{forwarded_msg.id}"
            await client.send_message(
                track_channel,
                f"✅ Message Forwarded to {current_platform} Topic: [TAP HERE]({track_link})",
                link_preview=False
            )
        return True
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds + 5)
        return None
    except Exception as e:
        print(f"❌ Error forwarding to topic {link}: {e}")
        return False

async def forward_to_single_group(reply_message, dialog):
    try:
        sent_msg = await client.forward_messages(dialog.id, reply_message)
        username = getattr(dialog.entity, "username", None)
        if username:
            track_link = f"https://t.me/{username}/{sent_msg.id}"
            await client.send_message(
                track_channel,
                f"✅ Message Sent to Group : [TAP HERE]({track_link})",
                link_preview=False
            )
        return True
    except FloodWaitError:
        return None
    except Exception as e:
        print(f"❌ Error forwarding to group: {e}")
        return False

async def forward_message_to_all(reply_message, command_event):
    global active_process, stop_signal
    stop_signal = False
    if active_process:
        active_process.cancel()
        active_process = None
        await command_event.reply("🛑 Previous Adbot stopped.\nStarting new one...")
    active_process = asyncio.create_task(manage_forwarding(reply_message, command_event))

async def manage_forwarding(reply_message, command_event):
    global active_process, stop_signal, group_delay, process_delay
    process_counter = 1
    while True:
        if process_counter == 1:
            status_msg = f"🟢**Adbot is live... Messages going out as scheduled !! (Process #{process_counter})**\n"
        else:
            status_msg = f"🔄**Adbot is resuming... (Process #{process_counter})**\n"
        status_msg += f"⏱️ Group Delay: {group_delay}s | Batch Delay: {process_delay}s\n"
        if current_platform and current_platform in platform_links:
            status_msg += f"🎯 Mode: `Groups & {current_platform}`"
        else:
            status_msg += f"🎯 Mode: `Only Group MPs`"
        await command_event.reply(status_msg)
        sent = failed = skipped = 0
        if current_platform and current_platform in platform_links:
            platform_links_list = platform_links[current_platform][:]
            groups_list = cached_groups[:]
            combined_targets = []
            combined_targets.extend([('topic', link) for link in platform_links_list])
            combined_targets.extend([('group', dialog) for dialog in groups_list])
            random.shuffle(combined_targets)
            for target_type, target in combined_targets:
                if stop_signal or active_process is None:
                    return
                if target_type == 'topic':
                    result = await forward_to_single_topic(reply_message, target)
                else:
                    result = await forward_to_single_group(reply_message, target)
                if result is True:
                    sent += 1
                    await asyncio.sleep(random.uniform(group_delay, group_delay + 1))
                elif result is False:
                    failed += 1
                else:
                    skipped += 1
        else:
            for dialog in cached_groups:
                if stop_signal or active_process is None:
                    return
                result = await forward_to_single_group(reply_message, dialog)
                if result is True:
                    sent += 1
                    await asyncio.sleep(random.uniform(group_delay, group_delay + 1))
                elif result is False:
                    failed += 1
                else:
                    skipped += 1
        if not stop_signal:
            summary = (
                f"✅**Process #{process_counter} Completed**\n"
                f"📤Sent: {sent}\n"
                f"❌Failed: {failed}\n"
                f"⏳Skipped: {skipped} (FloodWait)\n"
                f"🕒Interval delay active for {process_delay}s..."
            )
            await command_event.reply(summary)
        process_counter += 1
        await asyncio.sleep(process_delay)

@client.on(events.NewMessage(pattern=r'\.task (.+)'))
async def save_task(event):
    if event.sender_id != owner_id:
        return
    if not event.is_reply:
        await event.reply("❌ Reply to a message to save it as task.")
        return
    if event.chat_id != owner_id:
        await event.reply("❌ This command only works in Saved Messages.")
        return
    reply = await event.get_reply_message()
    
    # Check if message is forwarded
    if reply.fwd_from:
        await event.reply("❌ **Forwarded messages cannot be saved as tasks.**\nPlease use original messages only.")
        return
    
    task_name = event.pattern_match.group(1).strip().lower()
    saved_tasks[task_name] = reply.id
    save_tasks()
    await event.reply(f"✅ **Task saved as:** `{task_name}`\nUse `.start {task_name}` to run it.")

@client.on(events.NewMessage(pattern=r'\.greet'))
async def set_greeting(event):
    global greeting_msg_data, greeted_users
    if event.sender_id != owner_id:
        return
    reply = await event.get_reply_message()
    if not reply:
        await event.reply("❌ Please reply to a message to set it as greeting.")
        return
    greeting_msg_data = {'chat_id': reply.chat_id, 'msg_id': reply.id}
    greeted_users = set()
    save_greeting_data()
    await event.reply("✅ **Greeting message set successfully!**\nThis will be sent to users who message you for the first time.")

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def auto_greet_handler(event):
    global greeting_msg_data, greeted_users
    if event.sender_id == owner_id or not greeting_msg_data:
        return
    if event.sender_id in greeted_users:
        return
    try:
        msg = await client.get_messages(greeting_msg_data['chat_id'], ids=greeting_msg_data['msg_id'])
        if msg:
            if msg.media:
                await event.respond(msg.message, file=msg.media, formatting_entities=msg.entities)
            else:
                await event.respond(msg.message, formatting_entities=msg.entities)
            greeted_users.add(event.sender_id)
            save_greeting_data()
            print(f"✅ Greeted user {event.sender_id}")
    except Exception as e:
        print(f"❌ Error sending greeting: {e}")

@client.on(events.NewMessage(pattern=r'\.start (.+)'))
async def start_command(event):
    global active_process, cached_message, cached_entity
    if event.sender_id != owner_id:
        return
    if active_process:
        await event.reply("⚠️**A forwarding process is already running. Use `.stop` to stop it.**")
        return
    param = event.pattern_match.group(1).strip()
    if param.lower() in saved_tasks:
        task_name = param.lower()
        task_msg_id = saved_tasks[task_name]
        await event.reply(f"📋 Loading task: `{task_name}`...")
        if not await cache_all_dialogs():
            await event.reply("❌ Failed to cache dialogs. Must try again.")
            return
        try:
            task_message = await client.get_messages(owner_id, ids=task_msg_id)
            if not task_message:
                await event.reply("❌ Task message not found in Saved Messages.")
                return
            await event.reply(f"✅ Task loaded. Starting forwarding...")
            await forward_message_to_all(task_message, event)
        except Exception as e:
            await event.reply(f"❌ Error loading task: {str(e)}")
        return
    link = param
    try:
        if not link.startswith("https://t.me/"):
            await event.reply("❌ Invalid link format. Use: https://t.me/channel/messageID or task name")
            return
        if link.startswith("https://t.me/c/"):
            parts = link.replace("https://t.me/c/", "").split("/")
            if len(parts) < 2:
                await event.reply("❌ Invalid private channel link format.")
                return
            channel_id = f"-100{parts[0]}"
            message_id = int(parts[1])
            channel_identifier = channel_id
        else:
            parts = link.replace("https://t.me/", "").split("/")
            if len(parts) < 2:
                await event.reply("❌ Invalid link format. Use: https://t.me/channel/messageID")
                return
            channel_username = parts[0]
            message_id = int(parts[1])
            channel_identifier = channel_username
        await event.reply("📋 Fetching your ads message from link...")
        if not await cache_all_dialogs():
            await event.reply("❌ Failed to cache dialogs. Must try again.")
            return
        cached_entity = get_entity_from_cache(channel_identifier)
        if not cached_entity:
            await event.reply(f"❌ Could not find source channel in your acc.\nMust join the source channel to continue.")
            return
        cached_message = await client.get_messages(cached_entity, ids=message_id)
        if not cached_message:
            await event.reply("❌ Message not found or inaccessible.")
            return
        await event.reply(f"✅ Message loaded. Starting forwarding...")
        await forward_message_to_all(cached_message, event)
    except ValueError:
        await event.reply("❌ Invalid message ID in link.")
    except Exception as e:
        await event.reply(f"❌ Error loading message: {str(e)}")
        print(f"❌ Detailed error: {e}")

@client.on(events.NewMessage(pattern=r'\.stop'))
async def stop_command(event):
    global active_process, stop_signal, cached_message, cached_entity, cached_groups, cached_entities
    if event.sender_id != owner_id:
        return
    if active_process:
        stop_signal = True
        active_process.cancel()
        try:
            await active_process
        except asyncio.CancelledError:
            pass
        active_process = None
        cached_message = None
        cached_entity = None
        cached_groups = []
        cached_entities = []
        await event.reply("🛑**Adbot Process completely stopped.**\n**You can restart the process using .start command.**\n\n🥀 𝐅𝐭~ @AdGenie")
    else:
        await event.reply("⚠️ No active process to stop.")

@client.on(events.NewMessage(pattern=r'\.group (\d+)'))
async def set_group_delay(event):
    global group_delay
    if event.sender_id != owner_id:
        return
    group_delay = int(event.pattern_match.group(1))
    await event.reply(f"✅**Group delay set to {group_delay} seconds.**")

@client.on(events.NewMessage(pattern=r'\.process (\d+)'))
async def set_process_delay(event):
    global process_delay
    if event.sender_id != owner_id:
        return
    process_delay = int(event.pattern_match.group(1))
    await event.reply(f"✅**Batch delay set to {process_delay} seconds.**")

@client.on(events.NewMessage(pattern=r'\.reset'))
async def cmd_reset(event):
    global current_platform
    if event.sender_id != owner_id:
        return
    current_platform = None
    await event.reply("✅**Platform Mode deactivated.\nResuming normal forwarding to all groups/forums.**")

@client.on(events.NewMessage(pattern=r'\.set (\w+)'))
async def cmd_set_links(event):
    if event.sender_id != owner_id:
        return
    reply = await event.get_reply_message()
    if not reply or not reply.text:
        await event.reply("✅**Reply to a message containing your topic links.**")
        return
    name = event.pattern_match.group(1).lower()
    links = []
    for line in reply.text.splitlines():
        line = line.strip()
        if line.startswith("https://t.me/") and ('/' in line[13:] or '/c/' in line):
            links.append(line)
    if not links:
        await event.reply("❌No valid t.me topic links found.")
        return
    platform_links[name] = links
    await event.reply(f"✅Saved {len(links)} topic links under platform `{name}`.")

@client.on(events.NewMessage(pattern=r'\.platform (\w+)'))
async def cmd_activate_platform(event):
    global current_platform
    if event.sender_id != owner_id:
        return
    name = event.pattern_match.group(1).lower()
    if name not in platform_links:
        await event.reply(f"❌No platform named `{name}`. Use `.set {name}` first.")
        return
    current_platform = name
    await event.reply(f"✅Platform Mode activated: `{name}`\nOnly those topics will receive ads.")

@client.on(events.NewMessage(pattern=r'\.faq'))
async def help_command(event):
    if event.sender_id != owner_id:
        return
    await event.reply(
        "**❓Adbot FAQs & Help**\n\n"
        "➤ `.start <telegram_link or task_name>`\nStarts forwarding message from link or saved task.\n\n"
        "➤ `.task <name>`\nReply to any message in Saved Messages to save it as task.\n\n"
        "➤ `.stop`\nStops any running forward process immediately.\n\n"
        "➤ `.group <seconds>`\nSet delay time between sending in each group or topic.\n\n"
        "➤ `.process <seconds>`\nSet delay time between each full batch run.\n\n"
        "➤ `.set <platform_name>`\nReply to a message that contains multiple topic-links.\n\n"
        "➤ `.platform <platform_name>`\nEnable Platform Mode.\n\n"
        "➤ `.show`\nShow all saved platforms & tasks.\n\n"
        "➤ `.reset`\nExit Platform Mode.\n\n"
        "➤ `.track`\nShow the channel where track logs are sent.\n\n"
        "➤ `.greet`\nReply to any message to set it as auto-greeting.\n\n"
        "➤ `.faq`\n**Adbot Usage & Settings Overview**\n\n**𝐅𝐭~ @AdGenie 🥀**"
    )

@client.on(events.NewMessage(pattern=r'\.track'))
async def track_command(event):
    if event.sender_id != owner_id:
        return
    await event.reply(f"📍 Your ads are being tracked at: @{track_channel}")

@client.on(events.NewMessage(pattern=r'\.show'))
async def show_saved_platforms(event):
    if event.sender_id != owner_id:
        return
    message = ""
    if platform_links:
        message += "⬇️ **Saved Platforms:**\n\n"
        for name in platform_links:
            message += f"‼️ `{name}`\n"
    if saved_tasks:
        message += "\n📋 **Saved Tasks:**\n\n"
        for name in saved_tasks:
            message += f"✅ `{name}`\n"
    if not message:
        await event.reply("❌ No platforms or tasks saved yet.")
    else:
        await event.reply(message)

async def main():
    print("✅Adbot is live...")
    load_greeting_data()
    load_tasks()
    # The client starts here, using the SESSION_STRING for immediate login.
    await client.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
