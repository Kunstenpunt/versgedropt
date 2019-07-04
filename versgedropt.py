import spotipy
import musicbrainzngs
from spotipy.oauth2 import SpotifyClientCredentials
from requests import get, exceptions
from json import loads
from dateparser import parse
from pandas import DataFrame, read_excel
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime, timedelta
from re import compile, sub
from codecs import open
import pysftp
from glob import glob
import os


class Platform(object):
    def __init__(self):
        self.test = None
        self.platform = None

    def do_it(self, current_url):
        return self.platform in current_url

    def authenticate(self):
        pass

    def get_drops_for_artist(self, mbartist, current_url):
        pass


class Youtube(Platform):
    def __init__(self):
        super().__init__()
        self.google_api_key = None
        self.platform = "youtube"

    def authenticate(self):
        with open('resources/google.txt', 'r') as f:
            self.google_api_key = f.read().strip()

    def get_drops_for_artist(self, mbartist, current_url):
        data = []
        try:
            tiepeurl = current_url.strip('/').split('/')[-2]
            username = current_url.strip('/').split('/')[-1]
            if tiepeurl != "channel":
                channel_url = 'https://www.googleapis.com/youtube/v3/channels?part=contentDetails&forUsername={0}&key={1}'.format(username, self.google_api_key)
                channel_info = loads(get(channel_url).text)
                playlist_id = channel_info['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                items_url = 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId={0}&key={1}'.format(playlist_id, self.google_api_key)
            else:
                items_url = "https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={0}&type=video&key={1}".format(username, self.google_api_key)

            items = loads(get(items_url).text)['items']
            for item in items:
                album_data = {
                    'band': mbartist['artist']['name'],
                    'band_id': username,
                    'platform': 'youtube',
                    'drop': item['snippet']['title'],
                    'drop_id': item['id']["videoId"] if tiepeurl == "channel" else item["id"],
                    'drop_url': 'https://www.youtube.com/watch?v=' + item['snippet']['resourceId']['videoId'] if tiepeurl == "user" else 'https://www.youtube.com/watch?v=' + item['id']['videoId'],
                    'drop_visual': item['snippet']['thumbnails']['default']['url'],
                    'release_date': parse(item['snippet']['publishedAt']).date()
                }
                print(album_data)
                data.append(album_data)

        except Exception as e:
            print("youtube says", e)

        return data


class Spotify(Platform):
    def __init__(self):
        super().__init__()
        self.spotify = None
        self.platform = "spotify"

    def authenticate(self):
        with open('resources/spotify.txt', 'r') as f:
            client_id, client_secret = f.read().strip().split('\n')
        client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        self.spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    def get_drops_for_artist(self, mbartist, current_url):
        data = []

        birdy_uri = 'spotify:artist:{0}'.format(current_url.split('/')[-1])
        results = self.spotify.artist_albums(birdy_uri, album_type='album')
        albums = results['items']
        while results['next']:
            results = self.spotify.next(results)
            albums.extend(results['items'])

        results = self.spotify.artist_albums(birdy_uri, album_type='single')
        albums.extend(results['items'])
        while results['next']:
            results = self.spotify.next(results)
            albums.extend(results['items'])

        results = self.spotify.artist_albums(birdy_uri, album_type='compilation')
        albums.extend(results['items'])
        while results['next']:
            results = self.spotify.next(results)
            albums.extend(results['items'])

        for album in albums:
            album_data = {
                'band': mbartist['artist']['name'],
                'band_id': current_url.split('/')[-1],
                'platform': 'spotify',
                'drop': album['name'],
                'drop_id': album['id'],
                'drop_url': 'https://open.spotify.com/album/' + album['id'],
                'drop_visual': album['images'][-2]['url'],
                'release_date': parse(album['release_date']).date()
            }
            print(album_data)
            data.append(album_data)

        return data


class Itunes(Platform):
    def __init__(self):
        super().__init__()
        self.platform = "itunes"

    def authenticate(self):
        pass

    def get_drops_for_artist(self, mbartist, current_url):
        data = []
        url = 'https://itunes.apple.com/lookup?id={0}&entity=album'.format(current_url.split('/')[-1].lstrip('id'))
        d = get(url)
        if 'results' in loads(d.text):
            for item in loads(d.text)['results']:
                if item['wrapperType'] == 'collection':
                    album_data = {
                        'band': mbartist['artist']['name'],
                        'band_id': current_url.split('/')[-1].lstrip('id'),
                        'platform': 'itunes',
                        'drop': item['collectionName'],
                        'drop_id': item['collectionId'],
                        'drop_url': item['collectionViewUrl'],
                        'drop_visual': item['artworkUrl100'],
                        'release_date': parse(item['releaseDate']).date()
                    }
                    print(album_data)
                    data.append(album_data)
        return data


class Deezer(Platform):
    def __init__(self):
        super().__init__()
        self.platform = "deezer"

    def authenticate(self):
        pass

    def get_drops_for_artist(self, mbartist, current_url):
        data = []
        deezer_id = current_url.split('/')[-1]
        d = get('https://api.deezer.com/artist/{0}/albums'.format(deezer_id))
        for item in loads(d.text)['data']:
            print(item)
            album_data = {
                'band': mbartist['artist']['name'],
                'band_id': deezer_id,
                'platform': 'deezer',
                'drop': item['title'],
                'drop_id': item['id'],
                'drop_url': item['link'],
                'drop_visual': item['cover_medium'],
                'release_date': parse(item['release_date']).date()
            }
            print(album_data)
            data.append(album_data)
        return data


class Bandcamp(Platform):
    def __init__(self):
        super().__init__()
        self.platform = "bandcamp"

    def authenticate(self):
        pass

    def get_drops_for_artist(self, mbartist, current_url):
        data = []
        current_url = current_url.rstrip('/')
        print("current_url", current_url)
        html = get(current_url + '/music', headers={'User-agent': 'Mozilla/5.0'}).text
        soup = BeautifulSoup(html, 'html.parser')
        done = []
        if soup.find("div", attrs={"class": "playbutton"}):
            album_data = self.parse_bc_release(current_url + "/music")
            print(current_url, album_data)
            if album_data:
                album_data['band_id'] = current_url
                album_data['platform'] = 'bandcamp'
                print(album_data)
                data.append(album_data)
                done.append(current_url)
        else:
            for a in soup.find_all('a', attrs={'href': compile('album|track')}):
                href = a['href']
                if href not in done and (current_url in href or href.startswith('/album/') or href.startswith('/track/')):
                    album_url = href if href.startswith('http') else current_url + href
                    album_data = self.parse_bc_release(album_url)
                    if album_data:
                        album_data['band_id'] = current_url
                        album_data['platform'] = 'bandcamp'
                        print(album_data)
                        data.append(album_data)
                        done.append(href)
        return data

    def get_soup(self, url):
        try:
            release_request = get(url, headers={'User-agent': 'Mozilla/5.0'})
            return BeautifulSoup(release_request.text, "html.parser")
        except exceptions.ConnectionError:
            sleep(5.0)
            return self.get_soup(url)

    def parse_bc_release(self, url):
        soup = self.get_soup(url)
        if soup.find("h2", attrs={"class": "trackTitle"}):
            title = soup.find("h2", attrs={"class": "trackTitle"}).get_text().strip()
            artist = soup.find("span", attrs={"itemprop": "byArtist"}).a.contents[0].strip()
            releasedate_str = soup.find("meta", attrs={"itemprop": "datePublished"})["content"]
            releasedate = datetime(int(releasedate_str[0:4]), int(releasedate_str[4:6]), int(releasedate_str[6:8])).date()
            visual = soup.find('div', attrs={'id': 'tralbumArt'}).find('img')['src']
            return {
                "drop": title,
                "band": artist,
                "release_date": releasedate,
                "drop_url": url,
                "drop_id": url,
                "drop_visual": visual
            }


class Soundcloud(Platform):
    def __init__(self):
        super().__init__()
        self.platform = "soundcloud"

    def authenticate(self):
        pass

    def get_drops_for_artist(self, mbartist, current_url):
        data = []
        current_url = current_url.rstrip('/')
        try:
            html = get(current_url, headers={
                'User-agent': 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/44.0.2403.155 Safari/537.36'}).text
            soup = BeautifulSoup(html, 'html.parser')
            for item in soup.find_all('article', attrs={'class': 'audible'}):
                release_date = parse(item.find("time").contents[0],
                                     settings={'RETURN_AS_TIMEZONE_AWARE': False}).date()
                drop = item.find('a', attrs={'itemprop': 'url'})
                html_detail = get('https://soundcloud.com' + drop['href'], headers={
                    'User-agent': 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/44.0.2403.155 Safari/537.36'}).text
                soup_detail = BeautifulSoup(html_detail, 'html.parser')
                visual = soup_detail.find('img', attrs={'width': '500'})['src']
                album_data = {
                    'band': mbartist['artist']['name'],
                    'band_id': current_url,
                    'platform': 'soundcloud',
                    'drop': str(drop.contents[0]),
                    'drop_id': drop["href"],
                    'drop_url': 'https://soundcloud.com' + drop["href"],
                    'drop_visual': visual,
                    'release_date': release_date
                }
                print(album_data)
                data.append(album_data)
        except Exception as e:
            print("soundcloud says", e)
        return data


class Versgedropt(object):
    def set_mbids(self, mscbrnz_path):
        if self.test:
            self.mbids = [
                "2d0ec174-2bff-4f46-ae1b-dfea0ed9391c", #deus
                "5481f951-8a58-4f13-8ad5-8f0dad360bda", #jamaican jazz orchestra
                "26895123-efb1-4b0b-9868-9fc2138d46b6", #poldoore
            ]
        else:
            mscbrnz_path = "/home/tom/PycharmProjects/buitenlandse_concerten_grabber/resources/belgian_mscbrnz_artists.xlsx"
            mscbrnzs = read_excel(mscbrnz_path)
            self.mbids = mscbrnzs["mbid"].unique().tolist()

    def __init__(self, test=False):
        self.test = test

        self.youtube = Youtube()
        self.youtube.authenticate()

        self.spotify = Spotify()
        self.spotify.authenticate()

        self.deezer = Deezer()
        self.deezer.authenticate()

        self.itunes = Itunes()
        self.itunes.authenticate()

        self.bandcamp = Bandcamp()
        self.bandcamp.authenticate()

        self.soundcloud = Soundcloud()
        self.soundcloud.authenticate()

        self.mbids = []

        self.data = []
        self.df = None

    def get_drops_for_musicbrainz_belgians(self):
        for mbid in self.mbids:
            try:
                musicbrainzngs.set_useragent("versgeperst", "0.1", contact=None)
                mbartist = musicbrainzngs.get_artist_by_id(mbid, includes=['url-rels'])
                if 'url-relation-list' not in mbartist['artist']:
                    mbartist['artist']['url-relation-list'] = []
                print(mbartist)

                types = ['streaming music', 'purchase for download', 'bandcamp', 'soundcloud', 'youtube']

                for url in mbartist['artist']['url-relation-list']:
                    if url['type'] in types:
                        current_url = url['target']

                        for platform in ["youtube", "spotify", "deezer", "itunes", "bandcamp", "soundcloud"]:
                            cls = getattr(self, platform)
                            if cls.do_it(current_url):
                                platform_data = cls.get_drops_for_artist(mbartist, current_url)
                                self.data.extend(platform_data)

            except Exception as e:
                print(e)

        self.df = DataFrame(self.data)
        self.df.sort_values(by=['release_date', 'band', 'drop'], ascending=False, inplace=True)
        self.df.to_excel('output/versgedropt.xlsx')

    def put_website_online(self):
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        with open("resources/sftp.txt", "r") as f:
            user, pwd = tuple(f.read().split("\n"))
        with pysftp.Connection('sftp.dc2.gpaas.net', username=user, password=pwd, cnopts=cnopts) as sftp:
            with sftp.cd('/lamp0/web/vhosts/versgeperst.be/htdocs/versgedropt'):
                files = sftp.listdir()
                for file in files:
                    if file.endswith(".html"):
                        sftp.remove(file)

                for html_file in glob("output/*.html"):
                    print("pushing", html_file)
                    sftp.put(html_file, html_file.split("/")[-1])

    def generate_website(self):
        # purge previous version of html files
        fl = glob("output/*.html")
        for f in fl:
            os.remove(f)

        soundcloud_logo = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Antu_soundcloud.svg/1024px-Antu_soundcloud.svg.png'
        deezer_logo = 'https://e-cdns-files.dzcdn.net/cache/slash/images/common/logos/deezer.c0869f01203aa5800fe970cf4d7b4fa4.png'
        default_logo = 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/Vinyl_disc_icon.svg/240px-Vinyl_disc_icon.svg.png'

        with open("resources/template.html", "r", "utf-8") as f:
            html = f.read()
            template = BeautifulSoup(html, "html.parser")

        #set last updated line
        template.find("p", attrs={"id": "last_updated"}).insert(0, datetime.now().strftime('%d/%m/%Y, %H:%M:%S'))

        filtered_df = self.df.loc[(self.df['release_date'] >= (datetime(2010, 1, 1).date())) & (self.df['release_date'] <= (datetime.now() + timedelta(days=120)).date())]
        rows = filtered_df.iterrows()

        previous_release_date = ''
        previous_page_name = ''
        previous_previous_page_name = ''

        for row in rows:
            row = row[1]
            release_date = row['release_date'].isoformat()
            release_date_str = row['release_date'].strftime('%d %b %Y')
            page_name = row['release_date'].strftime('%b %Y').replace(' ', '') + ".html"

            if not str(row['drop_visual']).startswith('http'):
                if row['platform'] == 'soundcloud':
                    drop_visual = soundcloud_logo
                elif row['platform'] == 'deezer':
                    drop_visual = deezer_logo
                else:
                    drop_visual = default_logo
            else:
                drop_visual = row['drop_visual']

            if not str(row['drop_url']).startswith('http'):
                if row['platform'] == 'soundcloud':
                    drop_url = 'https://soundcloud.com' + row['drop_url']
                else:
                    drop_url = row["drop_url"]
            else:
                drop_url = row['drop_url']

            if row['platform'] == 'soundcloud':
                drop_icon = 'images/dropicon-soundcloud.png'
            elif row['platform'] == 'deezer':
                drop_icon = 'images/dropicon-deezer.png'
            elif row['platform'] == 'itunes':
                drop_icon = 'images/dropicon-apple.png'
            elif row['platform'] == 'bandcamp':
                drop_icon = 'images/dropicon-bandcamp.png'
            elif row['platform'] == 'spotify':
                drop_icon = 'images/dropicon-spotify.png'
            elif row['platform'] == 'youtube':
                drop_icon = 'images/dropicon-youtube.png'
            else:
                drop_icon = default_logo

            if page_name != previous_page_name and previous_page_name != '':
                print("making", previous_page_name)

                template.find("a", attrs={"id": "vorige-maand"})["href"] = page_name if page_name != datetime.now().strftime('%b %Y').replace(' ', '') + ".html" else "index.html"
                template.find("a", attrs={"id": "volgende-maand"})["href"] = previous_previous_page_name
                template.find("a", attrs={"id": "deze-maand"}).string = previous_page_name

                current_page_name = "index.html" if previous_page_name == datetime.now().strftime('%b %Y').replace(' ', '') + ".html" else previous_page_name

                with open("output/" + current_page_name, 'w', 'utf-8') as f:
                    f.write(template.prettify(formatter="html"))

                with open("resources/template.html", "r", "utf-8") as f:
                    html = f.read()
                    template = BeautifulSoup(html, "html.parser")

                previous_previous_page_name = current_page_name

            previous_page_name = page_name

            if release_date != previous_release_date:
                new_date_tag = BeautifulSoup('<li class="dropdate"><span>{0}<br />&rarr;</span></li>'.format(release_date_str), "html.parser")
                template.find("ul", attrs={"id": "da-thumbs"}).append(new_date_tag)

            new_drop_tag_str = '<li><a href="{0}"><span class="hoes" style="background:url({1});background-size: 175px 175px;"><img src="{2}" /></span><div><span>{3}</span></div></a></li>'.format(
                    drop_url,
                    drop_visual,
                    drop_icon,
                    sub('', '', (row['band'] + ' - ' + row['drop'])[0:85])
            )
            new_drop_tag = BeautifulSoup(new_drop_tag_str, "html.parser")
            template.find("ul", attrs={"id": "da-thumbs"}).append(new_drop_tag)

            previous_release_date = release_date


if __name__ == "__main__":
    vg = Versgedropt(test=False)
    vg.set_mbids(mscbrnz_path="")
    while True:
        if datetime.now().hour == 22:
            vg.get_drops_for_musicbrainz_belgians()
            vg.generate_website()
