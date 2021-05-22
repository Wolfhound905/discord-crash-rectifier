import os
import re
from os import path, remove
import discord
import requests
from bs4 import BeautifulSoup
from colored_print import ColoredPrint
from discord.ext import commands
from dotenv import load_dotenv

log = ColoredPrint()

bot = commands.Bot(command_prefix="there is none")
load_dotenv()


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user.name}\n")
    if not path.exists("blacklist.txt"):
        open("blacklist.txt", "w")


def Find(string):
    regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
    url = re.findall(regex, string)
    return [x[0] for x in url]


mimes = ["video", "image", "text/"]  # Note, checks five characters!


def checkContent(url):  # Uses Return HTTP headers to detect filetype
    r = requests.head(url, stream=True, allow_redirects=True)
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
        url = url.replace(".webp", "-mobile.mp4")
        url = url.replace("-size_restricted.gif", "-mobile.mp4")  # see above
    if "media.giphy.com" in url:  # mp4 are easier to read and less compressed.
        url = url.replace("media.", "i.")
        url = url.replace(".gif", ".mp4")
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
    ]

    for exploits in exploitTypes:
        test = s.find(exploits)
        if test != -1:
            remove(urlName)
            log.err(f"Found {exploits}. Character {test}\nThis was a client crasher\n")
            return True
    options_1 = s.find(b'options')
    if options_1 != -1:
        options_2 = s.find(b'options', options_1 + 1)
        if options_2 != -1:
            log.err("Found multiple options in same file.")  # discord doesnt like this
            remove(urlName)
            return True
    if checkFrame(urlName):
        log.err("File crafted using New method that changes size!.")
        remove(urlName)
        return True
    remove(urlName)  # Delete the file
    return False


def checkFrame(filePath):  # Slower Testing, but directly checks the file, to check files that may slip by
    # TODO Add report functionality, so we can find files that bypass
    try:  # Uses try because cv2 is not required for base functionality
        import cv2
        log.info("Starting Size Check - Will take time")
        cap = cv2.VideoCapture(filePath)
        x, firstFrame = cap.read()
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap = cv2.VideoCapture(filePath)
        cap.set(frames-2, frames-2)
        res, frame = cap.read()
        if frame.shape[0:2] != firstFrame.shape[0:2]:  # Checks second-to-last frame to First frame's size
            return True
        return False
    except ImportError:  # If person running does not have
        print("importError")
        return False


def checkLink(url):  # Mostly applies to (gfycat and giphy), but uses og:video to find what discord embeds
    url = url.replace("\\", "")
    r = requests.get(url, allow_redirects=True)
    soup = BeautifulSoup(str(r.content), "html.parser")
    mp4 = soup.find("meta", property="og:video")
    log.success(
        f'Has og:video, now using: {mp4["content"]}\n' if mp4 else "No meta mp4 given\n")
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


def checkBlacklist(url):  # Reads blacklist.txt to check if url or parts of url appear
    with open("blacklist.txt") as blacklist:
        for x in blacklist:
            if f"{url}" in x or x.replace("\n", "") in f"{url}":
                return True
    return False


async def checkMessage(message):
    crashMessage = f"Fun Fact: {message.author.mention} does know crashing gifs are dumb. ||Like them||"
    urls = Find(message.content)  # Get URLs
    if message.attachments:  # If the message has attachments
        for Attachment in message.attachments:
            url = Attachment.url
        log.info(url)
        crasher = checkFile(url)
        if crasher:
            await message.delete()
            await message.channel.send(crashMessage, allowed_mentions=discord.AllowedMentions.none())
            return
        else:
            log.success("This probably doesnt contain a crash\n")
    if urls:  # If the message contains a url
        for url in urls:
            if checkBlacklist(url):
                await message.delete()
                await message.channel.send(crashMessage, allowed_mentions=discord.AllowedMentions.none())
                log.err(f'Link "{url}" was found on the blacklist\n')
                return
            log.warn(f"Getting {url}")
            # If the site uses head meta tags for the file link
            content = checkContent(url)
            if content == "text/html":
                log.info("The link was text/html")
                crasher = checkLink(url)
            elif checkContent(url)[0:5] in ["video", "image"]:
                log.info("The link was video/gif")
                crasher = checkFile(url)
            else:
                log.info(f"The link uses an unrecognised type '{content}.' Exiting.\n")
                return
            if crasher:
                await message.delete()
                updateBlacklist(url)
                await message.channel.send(crashMessage, allowed_mentions=discord.AllowedMentions.none())
                return
            else:
                log.success("This probably doesnt contain a crash\n")


@bot.event
async def on_message(message):
    print(message)
    await checkMessage(message)


@bot.event
async def on_message_edit(before, after):
    print(after)
    if before != after:
        try:
            await checkMessage(after)
        except discord.errors.NotFound:
            pass


bot.run(os.getenv("token"))
