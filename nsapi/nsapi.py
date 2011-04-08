import web
import base64
import re
import httplib2
import cElementTree as ElementTree
from XmlDictConfig import XmlDictConfig
import simplejson
import time

urls = (
    '/xml/(.*)', 'NSAPI',
    '/json/(.*)','ToJSON',
    '/irail/stations', 'ToIrailStations',
)

app = web.application(urls,globals())

class NSAPI:
    def processor(self, content):
        return content

    def GET(self, request):
        auth = web.ctx.env.get('HTTP_AUTHORIZATION')
        authreq = False
        if auth is None:
            authreq = True
        else:
            auth = re.sub('^Basic ','',auth)
            username,password = base64.decodestring(auth).split(':')

            h = httplib2.Http()
            h.debuglevel = 1
            h.add_credentials(username, password)
            resp, content = h.request("https://webservices.ns.nl/"+request)

            if resp['status'] == '200':
                return self.processor(content)
            if resp['status'] == '404':
                return web.notfound()
            else:
                authreq = True
        if authreq:
            web.header('WWW-Authenticate','Basic realm="openOV-NS"')
            web.ctx.status = '401 Unauthorized'
            return 'Gelieve een geldig NS API account te gebruiken.'+request

class ToJSON(NSAPI):
    def processor(self, content):
        root = ElementTree.XML(content)
        xmldict = XmlDictConfig(root)
        web.header('Content-Type', 'application/json')
        return simplejson.dumps(xmldict)

class ToIrailStations(NSAPI):
    def GET(self):
        return NSAPI.GET(self, "/ns-api-stations")

    def processor(self, content):
        root = ElementTree.XML(content)
        dstations = {}
        stations = root.findall('.//station')
        for station in stations:
            if station.find('.//country').text == 'NL':
                code = station.find('.//code').text
                if code not in dstations:
                    dstations[code] = {'alias': [], 'defaultname': '', 'locationX': '', 'locationY': ''}
                if station.find('.//alias').text == 'true':
                    dstations[code]['alias'].append(station.find('.//name').text)
                else:
                    dstations[code]['defaultname'] = station.find('.//name').text
                    dstations[code]['locationX'] = station.find('.//lat').text
                    dstations[code]['locationY'] = station.find('.//long').text
                    dstations[code]['alias'].append(station.find('.//name').text)

        root = ElementTree.Element('stations')
        root.attrib['timestamp'] = str(int(time.time()))

        for station in dstations.values():
            for alias in station['alias']:
                sub = ElementTree.SubElement(root, 'station')
                sub.attrib['locationX'] = station['locationX']
                sub.attrib['locationY'] = station['locationY']
                sub.attrib['defaultname'] = station['defaultname']
                sub.text = alias

        web.header('Content-Type', 'application/xml')
        return ElementTree.tostring(root)


application = app.wsgifunc()
