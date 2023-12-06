from flask import stream_with_context, Response, send_file, redirect
from sanitize_filename import sanitize
import os
import requests
import time
import sys
from clases.config import config as c
from clases.worker import worker as w
from clases.folders import folders as f
from clases.nfo import nfo as n
from threading import Thread, Timer, Event
from random import randint
from subprocess import TimeoutExpired
import signal

## -- TWITCH CLASS
class Twitch:
    def __init__(self, channel):
        self.channel = channel
        self.twitch_channel_url = "https://www.twitch.tv/{}".format(channel)
        self.channel_name = self.get_name()
        self.images = self.get_thumbs()
        self.direct = self.get_direct()
        self.videos = self.get_videos()

    def get_name(self):
        command = [
            'yt-dlp', 
            'https://www.twitch.tv/{}'.format(
                self.channel
            ), 
            '--print', '"%(uploader)s"', 
            '--playlist-items', '1',
            '--restrict-filenames',
            '--ignore-errors',
            '--no-warnings',
            '--compat-options', 'no-youtube-channel-redirect',
            '--no-warnings'
        ]

        channel_name = w.worker(
            command
        ).output()
        
        if 'ERROR' in channel_name:
            channel_name = self.channel
        
        return channel_name

    def get_direct(self):
        #Get current livestream
        print("Processing live video in channel")

        command = [
            'yt-dlp', 
            '--print', '"%(id)s;%(title)s"', 
            '--ignore-errors',
            '--no-warnings',
            '{}'.format(
                self.twitch_channel_url
            )
        ]

        return w.worker(
            command
        ).output().split('\n')

    def get_pictures(self):
        headers = {
            'Accept': '*/*',
            'Client-Id': '{}'.format(client_id),
            'Client-Version': '{}'.format(client_version),
            'Connection': 'keep-alive',
            'Content-Type': 'text/plain;charset=UTF-8',
            'Origin': 'https://www.twitch.tv',
            'Referer': 'https://www.twitch.tv/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
        data = [
            {
                "operationName":"ChannelShell",
                "variables":{
                    "login":"{}".format(
                        self.channel
                    )
                },
                "extensions":{
                    "persistedQuery":{
                        "versions":1,
                        "sha256Hash":"{}".format(
                            sha256_channelShell
                        )
                    }
                }
            }
        ]

        response = requests.post(
            'https://gql.twitch.tv/gql', 
            headers=headers, 
            json=data
        )

        return response.json()
    
    def get_thumbs(self):
        #Table thumbnails
        c = 0
        command = [
            'yt-dlp', 
            'https://www.twitch.tv/{}/{}'.format(
                self.channel,"videos"
            ),
            '--list-thumbnails',
            '--restrict-filenames',
            '--ignore-errors',
            '--no-warnings',
            '--no-download',
            '--playlist-items', '1'
        ]
        #The madness begins... 
        #No comments between lines, smoke a joint if you want understand it
        lines = w.worker(
            command
        ).output().split('\n')
        headers = []
        thumbnails = []
        for line in lines:
            line = ' '.join(line.split())
            if not '[' in line and not 'has no' in line:
                data = line.split(' ')
                if c == 0:
                    headers = data
                else:
                    if not 'ID' in data[0]:
                        row = {}
                        for i, d in enumerate(data):
                            row[headers[i]] = d
                        thumbnails.append(row)
                c += 1
        #finally...

        preview = ""
        try:
            url_avatar_uncropped_index = next((index for (index, d) in enumerate(thumbnails) if d["ID"] == "0"), None)
            preview = thumbnails[url_avatar_uncropped_index]['URL'].replace(
                '320x180',
                '1920x1080'
            )
        except:
            print("No poster detected")

        pictures = self.get_pictures()
        poster = ""
        landscape = ""

        for picture in pictures:
            poster = picture['data']['userOrError']['profileImageURL'].replace(
                '70x70',
                '300x300'
            )
            landscape = picture['data']['userOrError']['bannerImageURL']

        return {
            "poster" : poster,
            "landscape" : landscape,
            "preview" : preview
        }

    def get_videos(self):
        command = [
            'yt-dlp', 
            '--print', '"%(id)s;%(title)s;%(upload_date)s"', 
            '--dateafter', "today-{}days".format(days_after),
            '--playlist-start', '1', 
            '--playlist-end', videos_limit, 
            '--ignore-errors',
            '--no-warnings',
            '{}/{}'.format(
                self.twitch_channel_url,
                "videos"
            )
        ]
    
        return w.worker(
            command
        ).output().split('\n')
## -- END

## -- LOAD CONFIG AND CHANNELS FILES
ytdlp2strm_config = c.config(
    './config/config.json'
).get_config()

config = c.config(
    './plugins/twitch/config.json'
).get_config()

channels = c.config(
    config["channels_list_file"]
).get_channels()

media_folder = config["strm_output_folder"]
channels_list = config["channels_list_file"]
source_platform = "twitch"
sha256_channelShell = "580ab410bcd0c1ad194224957ae2241e5d252b2c5173d8e0cce9d32d5bb14efe"
client_id = "kimne78kx3ncx6brgo4mv6wki5h1ko"
client_version = "21e5a00f-b4e2-4fe7-a6a1-13de6e72e9b1"

if 'days_dateafter' in config:
    days_after = config["days_dateafter"]
    videos_limit = config['videos_limit']
else:
    days_after = "10"
    videos_limit = "10"
## -- END

## -- MANDATORY TO_STRM FUNCTION 
def to_strm(method, *args):
    no_live = 'no_live' in args
    no_videos = 'no_videos' in args

    for twitch_channel in channels:
        print("Preparing channel {}".format(twitch_channel))
        twitch_channel = twitch_channel.replace('https://www.twitch.tv/', '')
        twitch = Twitch(twitch_channel)

        # -- MAKES CHANNEL DIR IF NOT EXIST,
        f.folders().make_clean_folder(
            "{}/{}".format(
                media_folder,  
                sanitize(
                    "{}".format(
                        twitch.channel
                    )
                )
            ),
            False,
            config
        )
        ## -- END

        ## -- BUILD CHANNEL NFO FILE
        n.nfo(
            "tvshow",
            "{}/{}".format(
                media_folder, 
                "{}".format(
                    twitch.channel
                )
            ),
            {
                "title" : twitch.channel_name,
                "plot" : "",
                "season" : "1",
                "episode" : "-1",
                "landscape" : twitch.images['landscape'],
                "poster" : twitch.images['poster'],
                "studio" : "Twitch"
            }
        ).make_nfo()
        ## -- END 

        ## -- GET ON AIR STREAMING
        if not no_live:
            for line in twitch.direct:
                if line != "":
                    if not 'ERROR' in line:
                        video_id = str(line).rstrip().split(';')[0]
                        video_name = str(line).rstrip().split(';')[1].split(" ")
                        try:
                            video_name.pop(3)
                        except:
                            pass

                        video_name = "{} [{}]".format(
                            ' '.join(
                                video_name
                            ),
                            video_id
                        )

                        file_content = "http://{}:{}/{}/{}/{}".format(
                            ytdlp2strm_config['ytdlp2strm_host'], 
                            ytdlp2strm_config['ytdlp2strm_port'], 
                            source_platform, 
                            method, "{}@{}".format(
                                twitch_channel, 
                                video_id
                                )
                            )
                        
                        file_path = "{}/{}/{}.{}".format(
                            media_folder,  
                            sanitize(
                                "{}".format(
                                    twitch_channel)
                                ), 
                            sanitize(
                                "!000-live-{}".format(
                                    twitch_channel
                                )
                            ), 
                            "strm"
                        )

                        data = {
                            "video_id" : video_id, 
                            "video_name" : video_name
                        }

                        if not os.path.isfile(file_path):
                            f.folders().write_file(
                                file_path, 
                                file_content
                            )
                    else:
                        try:
                            os.remove(
                                    "{}/{}/{}.{}".format(
                                    media_folder,  
                                    sanitize(
                                        "{}".format(
                                            twitch_channel
                                        )
                                    ),  
                                    sanitize(
                                        "!000-live-{}".format(
                                            twitch_channel
                                        )
                                    ), 
                                    "strm"
                                )
                            )

                        except:
                            pass
            ## -- END

        ## -- GET VIDEOS TAB
        if not no_videos:
            for line in twitch.videos:
                if line != "":
                    if not 'ERROR' in line:
                        video_id = str(line).rstrip().split(';')[0]
                        video_name = str(line).rstrip().split(';')[1].split(" ")
                        upload_date = str(line).rstrip().split(';')[2]
                        try:
                            video_name.pop(3)
                        except:
                            pass

                        video_name = "{} [{}]".format(
                            ' '.join(
                                video_name
                            ), 
                            video_id
                        )

                        file_content = "http://{}:{}/{}/{}/{}".format(
                            ytdlp2strm_config['ytdlp2strm_host'], 
                            ytdlp2strm_config['ytdlp2strm_port'], 
                            source_platform,
                            method, 
                            "{}@{}".format(
                                twitch_channel, 
                                video_id
                            )
                        )

                        file_path = "{}/{}/{}.{}".format(
                            media_folder,  
                            sanitize(
                                "{}".format(
                                    twitch_channel
                                )
                            ), 
                            sanitize(
                                "{}-{}".format(
                                    upload_date,
                                    video_name
                                )
                            ), 
                            "strm"
                        )

                        data = {
                            "video_id" : video_id, 
                            "video_name" : video_name
                        }
                        
                        if not os.path.isfile(file_path):
                            f.folders().write_file(
                                file_path, 
                                file_content
                            )
        ## --END
    
    return True 
## -- END

## --  REDIRECT VIDEO DATA 
def direct(twitch_id): 
    print(twitch_id)
    channel = twitch_id.split("@")[0]
    video_id = twitch_id.split("@")[1]
    command = [
        'yt-dlp', 
        '-f', 'best',
        '--no-warnings',
        'https://www.twitch.tv/videos/{}'.format(
            video_id
        ),
        '--get-url'
    ]

    twitch_url = w.worker(
        [
            'yt-dlp', 
            '-f', 'best',
            '--no-warnings',
            'https://www.twitch.tv/videos/{}'.format(
                video_id
            ),
            '--get-url'
        ]   
    ).output()

    if 'ERROR' in twitch_url:
        twitch_url = w.worker(
            [
                'yt-dlp', 
                '-f', 'best',
                '--no-warnings',
                'https://www.twitch.tv/videos/{}'.format(
                    video_id.replace(
                        'v',
                        ''
                    )            
                ),
                '--get-url'
            ]   
        ).output()

        if 'ERROR' in twitch_url:
            twitch_url = w.worker(
                [
                    'yt-dlp', 
                    '-f', 'best',
                    '--no-warnings',
                    'https://www.twitch.tv/{}'.format(
                        channel          
                    ),
                    '--get-url'
                ]   
            ).output()

    return redirect(
        twitch_url, 
        code=301
    )

class Lockfile(object):
    def __init__(self, file_name, port):
        self.file_name = file_name
        self.port = port
     
    def __enter__(self):
        self.file = open(self.file_name, 'x')
        self.file.write("{}\n".format(self.port))
        self.file.close()
 
    def __exit__(self, *args):
        os.remove(self.file_name)

def bridge(twitch_id):
    channel = twitch_id.split("@")[0]
    video_id = twitch_id.split("@")[1]
    lock_name = "/tmp/{}_lock".format(channel)

    turl = 'twitch.tv/{}'.format(
        channel
    )

    port = 43000 + randint(1, 100)
    stream_started = Event()

    def generate():
        with Lockfile(lock_name, port):
            startTime = time.time()
            buffer = []
            sentBurst = False
            event = Event()
            command = [
                'streamlink',
                turl,
                'best',
                '--player-external-http',
                '--player-external-http-port', '{}'.format(port),
                '--player-external-http-interface', "127.0.0.1",
                '--player-external-http-continuous', 'true',
                '--twitch-disable-ads',
                '-l', 'info'
            ]

            def timeout():
                event.set()

            print(' '.join(command))
            process = w.worker(command).pipe()
            try:
                t = Timer(10.0, timeout)
                stream_started.set()
                while not event.is_set():
                    try:
                        line = process.stdout.readline()
                        if line:
                            if "Got HTTP request" in license:
                                t.cancel()
                            elif "HTTP connection closed" in line:
                                t.start()
                    except TimeoutExpired:
                        pass

                    process.poll()
                    if isinstance(process.returncode, int):
                        if process.returncode > 0:
                            print('streamlink Error', process.returncode)
                        break
                    
                process.send_signal(signal.SIGINT)
                time.sleep(1)
            finally:
                process.kill()

    if not os.path.isfile(lock_name):
        Thread(target=generate, args=[]).run()
        stream_started.wait(1)
    else:
        with open(lock_name, 'r') as f:
            str = f.readline()
            port = int(str)

    return redirect(
        "http://127.0.0.1:{}/".format(port), 
        code=301
    )

## -- END