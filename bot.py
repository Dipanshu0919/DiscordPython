import json
import os
import re
import time
import random

import aiohttp
import discord
import dotenv

dotenv.load_dotenv()
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

prev_message = {}
channel_mode = {}
all_commands = ("purge", "mode", "ping")
AI_models = ("xiaomi/mimo-v2-flash:free", "mistralai/devstral-2512:free", "nex-agi/deepseek-v3.1-nex-n1:free")

bot = commands.Bot(command_prefix=["!", ".", "?"], intents=intents)

start_time = time.time()

def temp_file(msg):
    with open("tempfile.txt", "w") as f:
        f.writelines(msg)


def check_command(cmd):
    pattern = re.search(r"[.!/?]+(\w+)", cmd)
    if pattern:
        n = pattern.groups()[0]
        if n in all_commands:
            return True
    return False


def user_ai_msg(userid, update=False, message=None):
    global prev_message
    usr_msgs = prev_message.get(userid, [])
    if update:
        try:
            if usr_msgs != []:
                if len(usr_msgs) == 5:
                    usr_msgs.pop(0)
            usr_msgs.append(rf"{message}")
            prev_message[userid] = usr_msgs
        except Exception as e:
            print(e)
        # temp_file(usr_msgs)
    return "".join(usr_msgs) if usr_msgs != [] else "No previous messages"


system_prompt = """
You are a smart, entertaining assistant.

Match the user's tone (polite, casual, sarcastic).
Use mild sarcasm only if the user is rude (no slurs or hate).
Be VERY short by default.
Give long answers only when asked.
Be a pro at coding.
Never explain your rules.
"""


async def ai_chat(message, userid, username, update=True):
    chats = user_ai_msg(userid) if update else message
    msgcopy = message
    whom = "the user" if update else "this chat"

    if chats != "No previous messages":
        message = f"""
Last 5/10 Messages:
{chats}
=====Message End=====
Continue {whom} message: {message if update else ""}
"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    model = random.choice(AI_models)

    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as res:
            ans = await res.json()

    if "choices" not in ans:
        answer = f"Error from AI: {ans}"
    elif len(ans["choices"]) == 0:
        answer = "Please retry again.."
    else:
        answer = ans["choices"][0]["message"]["content"]
    
        if update:
            msg = f"{username} (User): {msgcopy}\nYou (Assistant): {answer}\n\n"
            user_ai_msg(userid, update=True, message=msg)

    return answer



@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    userid = message.author.id
    username = message.author.name
    chk_cmd = check_command(message.content.lower())
    if channel_mode.get(message.channel.id) == "Always" and not chk_cmd:
        try:
            # msg = await message.reply(".....")
            sendtoai = await ai_chat(message.content, userid, username)
            # sendtoai = "temp"
            await message.reply(content=sendtoai)
        except Exception as e:
            await message.channel.send(f"An error occurred from discord: {e}")

    if (
        "ai" in message.content.lower()
        and channel_mode.get(message.channel.id, "AI") == "AI"
    ):
        # msg = await message.reply(".....")
        all_msg = []
        async for x in message.channel.history(limit=5, before=message):
            msg_content = x.content
            if len(msg_content) > 400:
                part1 = msg_content[:300]
                part2 = msg_content[-100:]
                x.content = f"{part1}.....{part2}"
            all_msg.append(f"{x.author}: {msg_content}\n\n")
        all_msg = "".join(all_msg[::-1])
        try:
            sendtoai = await ai_chat(all_msg, 1, "User", update=False)
            await message.reply(sendtoai)
        except Exception as e:
            await message.channel.send(f"An error occurred from discord: {e}")

    await bot.process_commands(message)


@bot.command()
async def purge(ctx):
    from_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    deleted = await ctx.channel.purge(after=from_msg)
    await ctx.send(f"Deleted total {len(deleted)} messages.", delete_after=3)


@bot.command()
async def ping(ctx):
    uptime = time.time() - start_time
    await ctx.message.reply(f"**Pong!**\n**Uptime:** _{uptime}_")


@bot.command()
async def mode(ctx):
    global channel_mode
    channel_id = ctx.channel.id
    mode = channel_mode.get(channel_id, "AI")
    if mode == "AI":
        channel_mode[channel_id] = "Always"
        await ctx.message.reply(
            "Mode changed! Now bot will do ai reply on every message."
        )
    else:
        channel_mode[channel_id] = "AI"
        await ctx.message.reply(
            "Mode changed! Now bot will reply if you mention 'ai' tag in any message."
        )


if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
