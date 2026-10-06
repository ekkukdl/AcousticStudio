from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script' and a.get('src'):print('SCRIPT',urljoin('https://doillabs.com/',a['src']))
        if tag=='a' and a.get('href') and any(x in a['href'] for x in ['quote','gerber','dfm']):print('LINK',a['href'])
Links().feed(urlopen('https://doillabs.com/').read().decode())
