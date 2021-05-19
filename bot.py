import os
import re
from os import remove, path


import discord
import requests
from bs4 import BeautifulSoup
from discord.ext import commands
from dotenv import load_dotenv

bot = commands.Bot(command_prefix="there is none")
load_dotenv()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    if not path.exists("blacklist.txt"):
        open("blacklist.txt", "w")

    


def Find(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    url = re.findall(regex, string)
    return [x[0] for x in url]


mimes = ["video", "image", "text/"]  # Note, checks five characters!


def checkContent(url):  # Uses Return HTTP headers to detect filetype
    r = requests.get(url, stream=True)
    contentType = r.headers["Content-Type"].split(";")[0]
    return checkMIME(contentType)


def checkMIME(mimeType):
    for x in mimes:
        if mimeType[0:5].lower() == x[0:5]:
            return mimeType  # Whatever mimeType is, it will be truthy
    return False


def checkFile(url):
    url = url.replace("\\", "")  # No need for backslash in the urls
    if "thumbs.gfycat.com" in url:  # Gfycat is the source for most of these
        # Both crash, only second is detectable
        url = url.replace("-max-1mb.gif", "-mobile.mp4")
        url = url.replace("-size_restricted.gif", "-mobile.mp4")  # see above
    # TODO Check Blacklist
    r = requests.get(url, allow_redirects=True)
    urlName = url[8:]
    urlName = f'{urlName}'.replace('/', '')  # Uses URL to name files
    open(urlName, "wb").write(r.content)
    with open(urlName, "rb") as f:
        s = f.read()
    exploitTypes = [
        # This is an abnormal part of some crash mp4's. Most, if not all mp4's need stts, but not (stts
        b"(stts",
        b"Lavf58", b"Lavc58"  # These are artifacts of ffmpeg
    ]

    for exploits in exploitTypes:
        test = s.find(exploits)
        if test != -1:
            remove(urlName)
            return True
    remove(urlName)  # Delete the file
    return False


def checkLink(url):  # Mostly applies to gfycat, but uses og:video to find what discord embeds
    url = url.replace("\\", "")
    r = requests.get(url, allow_redirects=True)
    soup = BeautifulSoup(str(r.content), "html.parser")
    mp4 = soup.find("meta", property="og:video")
    print(
        f'Was gfycat so now using: {mp4["content"]}' if mp4 else "No meta mp4 given")
    if mp4:
        return checkFile(mp4["content"])  # If there is an og:video
    else:
        return False


def updateBlacklist(url):  # Adds url to blacklist.txt if not already added
    if checkBlacklist(url):
        return
    else:
        with open("blacklist.txt", "a") as f:
            f.write(f'{url}\n')


def checkBlacklist(url):  # Reads blacklist.txt to check if url appears
    with open("blacklist.txt") as blacklist:
        for x in blacklist:
            if f"{url}\n" == x:
                return True
    return False


async def checkMessage(message):
    crashMessage = f"Fun Fact: {message.author.mention} does know crashing gifs are dumb. ||Like them||"
    urls = Find(message.content)  # Get URLs
    if message.attachments:  # If the message has attachments
        for Attachment in message.attachments:
            url = Attachment.url
        print(url)
        crasher = checkFile(url)
        if crasher:
            await message.delete()
            await message.channel.send(crashMessage, allowed_mentions=discord.AllowedMentions.none())
        else:
            print("This prob doesnt crash")
    if urls:  # If the message contains a url
        for url in urls:
            if checkBlacklist(url):
                await message.delete()
                await message.channel.send(crashMessage, allowed_mentions=discord.AllowedMentions.none())
                return
            print(f"Getting {url}")
            # If the site uses head meta tags for the file link
            if checkContent(url) == "text/html":
                crasher = checkLink(url)
            else:
                crasher = checkFile(url)
            if crasher:
                print(f"Found")
                await message.delete()
                updateBlacklist(url)
                await message.channel.send(crashMessage, allowed_mentions=discord.AllowedMentions.none())
            else:
                print("This prob doesnt crash")


@bot.event
async def on_message(message):
    await checkMessage(message)


@bot.event
async def on_message_edit(before, after):
    await checkMessage(after)


bot.run(os.getenv("token"))
