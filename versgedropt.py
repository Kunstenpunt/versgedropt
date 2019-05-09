import musicbrainzngs
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from requests import get, exceptions
from json import loads
from dateparser import parse
from pandas import DataFrame
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from re import compile
from codecs import open


def get_soup(url):
    try:
        release_request = get(url, headers={'User-agent': 'Mozilla/5.0'})
        return BeautifulSoup(release_request.text, "html.parser")
    except exceptions.ConnectionError:
        sleep(5.0)
        return get_soup(url)


def parse_bc_release(url):
    soup = get_soup(url)
    if soup.find("h2", attrs={"class": "trackTitle"}):
        title = soup.find("h2", attrs={"class": "trackTitle"}).contents[0].strip()
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

app = 'versgedropt'
version = '0.1'

username = 'ruettet'
scope = 'user-follow-read'

musicbrainzngs.set_useragent(app, version, contact=None)

with open('spotify.txt', 'r') as f:
    client_id, client_secret = f.read().strip().split('\n')

client_credentials_manager = SpotifyClientCredentials(client_id='{0}', client_secret='{1}').format(client_id, client_secret)

mbids_test = [
    '3a354f76-9b95-43d6-8258-601ecd335ca9', #daemon
    '2d0ec174-2bff-4f46-ae1b-dfea0ed9391c', #deus
    '26895123-efb1-4b0b-9868-9fc2138d46b6', #poldoore
    'cedc1766-793e-40e9-a096-3a769932ae8c' #seizoensklanken
]

with open('mscbrnzids.txt', 'r') as f:
    mbids = f.read().split('\n')

data = []

with open('google.txt', 'r') as f:
    google_api_key = f.read().strip()

for mbid in mbids:
    try:
        mbartist = musicbrainzngs.get_artist_by_id(mbid, includes=['url-rels'])
        if not 'url-relation-list' in mbartist['artist']:
            mbartist['artist']['url-relation-list'] = []
        print(mbartist)

        types = ['streaming music', 'purchase for download', 'bandcamp', 'soundcloud', 'youtube']

        spotify = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        for url in mbartist['artist']['url-relation-list']:
            if url['type'] in types:
                current_url = url['target']

                if 'youtube' in current_url:
                    username = current_url.strip('/').split('/')[-1]
                    channel_url = 'https://www.googleapis.com/youtube/v3/channels?part=contentDetails&forUsername={0}&key={1}'.format(username, google_api_key)
                    channel_info = loads(get(channel_url).text)
                    playlist_id = channel_info['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    items_url = 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId={0}&key={1}'.format(playlist_id, google_api_key)
                    items = loads(get(items_url).text)['items']
                    for item in items:
                        album_data = {
                            'band': mbartist['artist']['name'],
                            'band_id': username,
                            'platform': 'youtube',
                            'drop': item['snippet']['title'],
                            'drop_id': item['id'],
                            'drop_url': 'https://www.youtube.com/watch?v=' + item['snippet']['resourceId']['videoId'],
                            'drop_visual': item['snippet']['thumbnails']['default']['url'],
                            'release_date': parse(item['snippet']['publishedAt']).date()
                        }
                        print(album_data)
                        data.append(album_data)

                if 'spotify' in current_url:
                    birdy_uri = 'spotify:artist:{0}'.format(current_url.split('/')[-1])
                    try:
                        results = spotify.artist_albums(birdy_uri, album_type='album')
                        albums = results['items']
                        while results['next']:
                            results = spotify.next(results)
                            albums.extend(results['items'])
                        for album in albums:
                            album_data = {
                                'band': mbartist['artist']['name'],
                                'band_id': current_url.split('/')[-1],
                                'platform': 'spotify',
                                'drop': album['name'],
                                'drop_id': album['id'],
                                'drop_url': album['href'],
                                'drop_visual': album['images'][-1]['url'],
                                'release_date': parse(album['release_date']).date()
                            }
                            print(album_data)
                            data.append(album_data)
                    except Exception as e:
                        print(e)

                if 'deezer' in current_url:
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

                if 'itunes' in current_url:
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

                if 'bandcamp' in current_url:
                    current_url = current_url.rstrip('/')
                    try:
                        html = get(current_url + '/music', headers = {'User-agent': 'Mozilla/5.0'}).text
                        soup = BeautifulSoup(html, 'html.parser')
                        done = []
                        for a in soup.find_all('a', attrs={'href': compile('/album/')}):
                            href = a['href']
                            if href not in done and (current_url in href or href.startswith('/album/')):
                                album_url = href if href.startswith('http') else current_url + href
                                album_data = parse_bc_release(album_url)
                                album_data['band_id'] = current_url
                                album_data['platform'] = 'bandcamp'
                                print(album_data)
                                data.append(album_data)
                                done.append(href)
                    except Exception as e:
                        print(e)

                if 'soundcloud' in current_url:
                    current_url = current_url.rstrip('/')
                    try:
                        html = get(current_url, headers={'User-agent': 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/44.0.2403.155 Safari/537.36'}).text
                        soup = BeautifulSoup(html, 'html.parser')
                        for item in soup.find_all('article', attrs={'class': 'audible'}):
                            release_date = parse(item.find("time").contents[0], settings={'RETURN_AS_TIMEZONE_AWARE': False}).date()
                            drop = item.find('a', attrs={'itemprop': 'url'})
                            html_detail = get('https://soundcloud.com' + drop['href'], headers={'User-agent': 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML like Gecko) Chrome/44.0.2403.155 Safari/537.36'}).text
                            soup_detail = BeautifulSoup(html_detail, 'html.parser')
                            visual = soup_detail.find('img', attrs={'width': '500'})['src']
                            album_data = {
                                'band': mbartist['artist']['name'],
                                'band_id': current_url,
                                'platform': 'soundcloud',
                                'drop': drop.contents[0],
                                'drop_id': drop["href"],
                                'drop_url': 'https://soundcloud.com' + drop["href"],
                                'drop_visual': visual,
                                'release_date': release_date
                            }
                            print(album_data)
                            data.append(album_data)
                    except Exception as e:
                        print(e)
    except Exception as e:
        print(e)

df = DataFrame(data)
df.sort_values(by=['release_date'], ascending=False, inplace=True)
df.to_excel('versgedropt.xlsx')

########################################################################################################################

soundcloud_logo = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Antu_soundcloud.svg/1024px-Antu_soundcloud.svg.png'
deezer_logo = 'https://e-cdns-files.dzcdn.net/cache/slash/images/common/logos/deezer.c0869f01203aa5800fe970cf4d7b4fa4.png'
default_logo = 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/Vinyl_disc_icon.svg/240px-Vinyl_disc_icon.svg.png'

html = """
<!DOCTYPE html>
<html>
<body>
<h1>Versgedropt</h1>
<p>Drops op de online platformen soundcloud, itunes, deezer, bandcamp en spotify. Van artiesten in Belgie, volgens musicbrainz.</p>
<table>
<tr>
{0}
</tr>
</table>
</body>
</html>
"""

df = df.loc[(df['release_date'] >= datetime(2019, 1, 1).date()) & (df['release_date'] < datetime(2019, 12, 31).date())]

html_lines = []
rows = df.iterrows()
length = 0
width = 10
previous_release_date = ''

for row in rows:
    row = row[1]
    release_date = row['release_date'].isoformat()

    drop_visual = ''
    if not str(row['drop_visual']).startswith('http'):
        if row['platform'] == 'soundcloud':
            drop_visual = soundcloud_logo
        elif row['platform'] == 'deezer':
            drop_visual = deezer_logo
        else:
            drop_visual == default_logo
    else:
        drop_visual = row['drop_visual']

    drop_url = ''
    if not str(row['drop_url']).startswith('http'):
        if row['platform'] == 'soundcloud':
            drop_url = 'https://soundcloud.com' + row['drop_url']
    else:
        drop_url = row['drop_url']

    html_line = '<td width = 100 style = "vertical-align: top"><a href="{0}"><img src = "{1}" alt = "{2}" height = "100px" width = "100px">{2}</a></td>'.format(
        drop_url,
        drop_visual,
        row['band'] + ' - ' + row['drop']
    )
    print(html_line)

    if release_date != previous_release_date:
        html_lines.append('</tr></table><h3>{0}</h3><table><tr>'.format(release_date))
        length = 0

    html_lines.append(html_line)

    if length % width == width-1:
        html_lines.append('</tr><tr>')

    length += 1
    previous_release_date = release_date

with open('versgedropt.html', 'w', 'utf-8') as f:
    f.write(html.format('\n'.join(html_lines)))
