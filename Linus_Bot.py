
import discord
import psycopg2
import requests
import json
import tempfile
from io import BytesIO
import asyncio
import os
import re

import utilities

from discord.ext import commands, tasks
from discord import app_commands

sensitiveInfo = json.loads(open("sensitiveInfo.json","r").read())
dbPass = sensitiveInfo["dbpass"]
key = sensitiveInfo["key"]
clientSecret = sensitiveInfo["clientSecret"]

con = psycopg2.connect("dbname=linus_bot user=postgres password={}".format(dbPass))

cur = con.cursor()

intents = discord.Intents.all()
intents.message_content = True
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn -loglevel level+info'}
guildid = 432389356058181655 #id of my home huild


class MyClient(discord.Client):

    #init from superclass using intents
    def __init__(self):
        super().__init__(intents=intents)
        self.feed_id = 1034001424180314232#linus feed channel id. May give more elegant solution later
        
    
    #runs when bot is ready
    async def on_ready(self):
        await self.wait_until_ready()
        print(f'Logged on as {self.user}!')
        self.feed_channel = self.get_channel(self.feed_id)
        print(self.feed_channel)
        self.pollVideos.start()#start process so it can do the big loop

    #this command runs every time a message is sent in the server
    async def on_message(self, message):
        if message.author == discord.Client.user:
            return #ignore your own messages
        print("message sent")
        print(message.content)
        if message.content == "l!usc":
            print("ALERT")
            await message.channel.send("updating slash commands. Anyone else, do not use this command or I will beat you to a pulp")
            await tree.sync()
        if message.content == "l!uploadaudio":
            await self.uploadAudio(message)
    
    async def uploadAudio(self, message):
        outputdir = "sound_files/"
        if(len(message.attachments) > 0):
            for attachment in message.attachments:
                files = os.listdir(outputdir)
                print(attachment.filename)
                print(attachment.content_type)

                if attachment.filename not in files and re.search("audio/.*",attachment.content_type):
                    await attachment.save(outputdir + attachment.filename, seek_begin = True)
                else:
                    if attachment.filename in files:
                        await message.channel.send("File " + attachment.filename + " already exists in bot directory")
                    if not re.search("audio/.*",attachment.content_type):
                        await message.channel.send("File " + attachment.filename + " is not of type audio/mpeg")

    #There is currently no use for this command
    @app_commands.command(name="config")
    async def config(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("CONFIG HEARS YOU LOUD AND CLEAR", ephemeral=True)
    
    async def joinVoiceChannel(self, channel):
        """
        joins voice channel or accquires already running voiceClient if already in channel
        takes channel to join as an argument
        """
        if(not channel == None):
            if(len(client.voice_clients) > 0 and client.voice_clients[0].channel == channel):
                return(client.voice_clients[0])
            else:
                vc = await channel.connect()
            return vc
        else:
            await interaction.response.send_message("I CAN'T PLAY AUDIO IF YOU'RE NOT IN A CHANNEL DUMMY")
            return None
        return(0)



    async def voiceNotification(self):
        """
        Go through every voice channel of server with >0 users and notify user of a new LTT video
        """
        channels = self.get_guild(guildid).voice_channels

        if(len(channels)==0):
            return

        for vc in channels:
            if(len(vc.members) > 0):
                voiceClient = await self.joinVoiceChannel(vc)
                voiceClient.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source="sound_files/linus_thanks.wav"))
                while(voiceClient.is_playing()):
                    await asyncio.sleep(1)
                await voiceClient.disconnect()
    
   


    @tasks.loop(minutes=15.0)
    async def pollVideos(self):
        """
        calls youtube API to update the database
        if there is a new video, notify in the corresponding channel
        call voiceNotification() to vocally notify as well
        """
        print("polling videos")
        utilities.updateAllChannelVideos()
        
        notification = False
        for channel in utilities.getChannelList():
            print("polling channel ",channel)
            latestVideo = utilities.getLatestVideoDatabase(channel)
            if(not latestVideo[6]):
                #do the notification
                await self.feed_channel.send(utilities.generateVideoUrlFromID(latestVideo[0]))             
                notification = True
                #only set video as notified at end of method
                utilities.setVideoAsNotified(latestVideo[0])
        if(notification):
            await self.voiceNotification()


client = MyClient()
tree = app_commands.CommandTree(client)

@tree.command(name = "config", description = "configure your shiny new linus bot")
async def config(interaction: discord.Interaction):
    await interaction.response.send_message("CONFIG HEARS YOU LOUD AND CLEAR!")

async def joinUserVoiceChannel(user):
    userVoiceState = user.voice
    channel = userVoiceState.channel
    if(not channel == None):
        if(len(client.voice_clients) > 0):
            print(client.voice_clients)
            print(client.voice_clients[0].channel)
            return(client.voice_clients[0])
        else:
            vc = await channel.connect()
        return vc
    else:
        await interaction.response.send_message("I CAN'T PLAY AUDIO IF YOU'RE NOT IN A CHANNEL DUMMY")
        return None
    return(0)

@tree.command(name = "playaudio", description = "play sound files on Anthony's Computer")
async def playaudio(interaction: discord.Interaction, audio_source: str):
    user = interaction.user

    voiceClient = await joinUserVoiceChannel(user)
    if(not voiceClient == None):
        await interaction.response.send_message("playing audio successfully")
        voiceClient.play(discord.FFmpegPCMAudio(executable="ffmpeg.exe", source="sound_files/"+audio_source))
        while(voiceClient.is_playing()):
            await asyncio.sleep(1)
        await voiceClient.disconnect()
    else:
        await interaction.response.send_message("ERROR - unable to connect to voice channel")


#give linus bot audio to store. can play these sound files with /playaudio
@tree.command(name = "listaudio", description = "lists audio files that are currently able to be played")
async def listaudio(interaction: discord.Interaction):
    user = interaction.user
    files = os.listdir("sound_files")
    emb = discord.Embed(title='Sound Files', color=discord.Color.blue(),
                                description=f'These are the sounds files that you can play '
                                            f':smiley:\n')
    for file in files:
        emb.add_field(name=file,value=None,inline=False)
    await interaction.channel.send(embed=emb)


@tree.command(name = "say", description = "make linus join and say things into your earholes")
async def say(interaction: discord.Interaction, text: str):
    wav_response = await utilities.tts(text)
    user = interaction.user
    voiceClient = await joinUserVoiceChannel(user)
    await interaction.response.send_message("saying words now")
    audioSource = discord.FFmpegPCMAudio(executable="ffmpeg.exe", source=BytesIO(wav_response), pipe=True, **FFMPEG_OPTIONS)
    voiceClient.play(audioSource)
    
    while(voiceClient.is_playing()):
        await asyncio.sleep(1)
    audioSource.cleanup()
    await voiceClient.disconnect()



client.run(clientSecret)

