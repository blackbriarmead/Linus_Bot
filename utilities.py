# This example requires the 'message_content' intent.

import discord
import psycopg2
import requests
import gc
import json
import asyncio
import io

from discord.ext import commands
from discord import app_commands

sensitiveInfo = json.loads(open("sensitiveInfo.json","r").read())
dbPass = sensitiveInfo["dbpass"]
key = sensitiveInfo["key"]
clientSecret = sensitiveInfo["clientSecret"]
uberduckAuth = sensitiveInfo["uberduckAuth"]

con = psycopg2.connect("dbname=linus_bot user=postgres password={}".format(dbPass))

cur = con.cursor()

def getplaylistID(channelID):
    query = "SELECT playlistid FROM playlists WHERE (channelid ='" + channelID + "')  LIMIT 1"
    cur.execute(query)
    gc.collect()
    return(cur.fetchone()[0])

def insertVideoFromJSON(item):
    videoId = item['contentDetails']['videoId']
    channelId = item['snippet']['channelId']
    videoPublishedAt = item['contentDetails']['videoPublishedAt']
    title = item['snippet']['title']
    description = item['snippet']['description']
    playlistId = item['snippet']['playlistId']
    query = "INSERT INTO videos(videoid, channelid, videoPublishedAt, title, description, playlistId) "
    query = query + "VALUES(%s,%s,%s,%s,%s,%s)"
    try:
        cur.execute(query,(videoId,channelId,videoPublishedAt,title,description,playlistId))
        con.commit()
    except:
        con.rollback()
        #print("could not insert video")
    gc.collect()

def insertThumbnailFromJSON(item):
    videoId = item['contentDetails']['videoId']
    for thumbnail in item['snippet']['thumbnails']:
        url = item['snippet']['thumbnails'][thumbnail]['url']
        width = item['snippet']['thumbnails'][thumbnail]['width']
        height = item['snippet']['thumbnails'][thumbnail]['height']
        query = "INSERT INTO thumbnails(videoId, url, width, height) "
        query = query + "VALUES(%s,%s,%s,%s)"
        try:
            cur.execute(query, (videoId,url,width,height))
            con.commit()
        except:
            con.rollback()
            #print("could not insert thumbnail")
    gc.collect()

#returns a JSON list of latest videos
def retrieveLatestVideosAPI(playlistID):
    request = "https://youtube.googleapis.com/youtube/v3/playlistItems?part=snippet%2C%20contentDetails&playlistId={playlistID}&key={API_KEY}".format(playlistID = playlistID, API_KEY = key)
    response = requests.get(request)
    if(response.status_code == 200):
        return(json.loads(response.text))#turn into json object for easy handling
    else:
        print("response failed with status code ",response.status_code)
    gc.collect()

#see if there are any new videos uploaded and update the database
def updateChannelVideos(channelID):
    playlistID = getplaylistID(channelID)
    latest = retrieveLatestVideosAPI(playlistID)
    for item in latest["items"]:
        insertVideoFromJSON(item)
        insertThumbnailFromJSON(item)

def getChannelList():
    query = "SELECT channelid FROM channels"
    print("attempting to get list of channelids: ")
    try:
        cur.execute(query)
        channels = cur.fetchall()
        return(channels)
    except Exception as e:
        print("There was an issue while trying to check for channelids: ",repr(e))
        con.rollback()
    gc.collect()

#this is the function that will be called regularly to check for new uploads
def updateAllChannelVideos():
    try:
        channels = getChannelList()
        for channel in channels:
            print("updating channel video: ",channel[0])
            updateChannelVideos(channel[0])
    except Exception as e:
        print("There was an issue while trying to check for new videos: ",repr(e))
    gc.collect()

def generateVideoUrlFromID(ID):
    return("https://www.youtube.com/watch?v={}".format(ID))

#get latest video for channel in database
'''
format:

{
kind:
etag:
nextPageToken:
items:[
    kind:
    etag:
    id:
    snippet:{
        publishedAt:
        channelId:
        title:
        description:
        thumbnails:{
            default:{
                url:
                width:
                height:
            },
            medium:
            high:
            standard:
            maxres:
        }
        channelTitle:
        playlistId:
        position:
        resourceId:{
            kind:
            videoId:
        }
        videoOwnerChannelTitle:
        videoOwnerChannelId:
    },
    contentDetails:{
        videoId:
        videoPublishedAt:
    }
],
...,
...
}
'''

def getLatestVideoDatabase(channelID):
    try:
        query = "SELECT * FROM videos WHERE (channelid = %s) ORDER BY videopublishedat DESC LIMIT 1"
        cur.execute(query,(channelID,))
        return(cur.fetchone())
    except Exception as e:
        print("There was an issue while trying to check for the latest video in the database: ",repr(e))
        con.rollback()
    gc.collect()

def setVideoAsNotified(videoID):
    try:
        print("updating video notification status",videoID)
        query = "UPDATE videos SET notified = TRUE WHERE videoid = %s RETURNING *"
        cur.execute(query,(videoID,))
        con.commit()
        print(cur.fetchone())

    except Exception as e:
        print("There was an issue while trying to update the notification status of the video",videoID,repr(e))
        con.rollback()
    gc.collect()

#videos = retrieveLatestVideosAPI("UUXuqSBlHAE6Xw-yeJA0Tunw")
#print(videos)

#print(getLatestVideoDatabase("UCFLFc8Lpbwt4jPtY1_Ai5yA"))

#getplaylistID("UCdBK94H6oZT2Q7l0-b0xmMg")

#updateChannelVideos("UCdBK94H6oZT2Q7l0-b0xmMg")

#updateAllChannelVideos()

#print(generateVideoUrlFromID("EUyaRYMzxEk"))

#setVideoAsNotified("oeU1xXDy5RE")

#print(getLatestVideoDatabase("UCFLFc8Lpbwt4jPtY1_Ai5yA"))

async def poll_tts(uuid):
    while(True):
        url = "https://api.uberduck.ai/speak-status?uuid={}".format(uuid)

        headers = {"accept": "application/json"}

        response = requests.get(url, headers=headers)
        responsejson = json.loads(response.text)
        print(response)
        print(responsejson)
        print(responsejson["finished_at"])
        if(("failed_at" in responsejson.keys()) and not responsejson["failed_at"] == None):
            return(None)
        if(("finished_at" in responsejson.keys()) and not responsejson["finished_at"] == None):
            return(responsejson["path"])
        else:
            await asyncio.sleep(1)
    return None


def tts_uuid(text):
    url = "https://api.uberduck.ai/speak"

    payload = {
        "voice": "lj",
        "pace": 1,
        "speech": text,
        "voicemodel_uuid": "80017978-a7e7-4c60-bef1-20e5fc3d62da"
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": "Basic " + uberduckAuth
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response)
    responsejson = json.loads(response.text)
    print(responsejson["uuid"])
    return(responsejson["uuid"])

def download_wav(wav_url):
    url = wav_url

    headers = {"accept": "application/json"}

    r = requests.get(url, headers=headers, stream=True)
    return(r.content)



async def tts(text):
    uuid = tts_uuid(text)
    audio_file_url = await poll_tts(uuid)
    return(download_wav(audio_file_url))