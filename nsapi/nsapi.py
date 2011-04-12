# -*- coding: utf-8 -*-

import web
import base64
import re
import httplib2
import cElementTree as ElementTree
from XmlDictConfig import XmlDictConfig
import simplejson
import time
import codecs

urls = (
    '/xml/(.*)', 'NSAPI',
    '/json/(.*)','ToJSON',
    '/irail/stations', 'ToIrailStations',
    '/irail/liveboard(.*)', 'ToIrailLiveboard',
)

app = web.application(urls,globals())

# Objects that should be made on time:
global dstations
dstations = {}

class NSAPI:
    def processor(self, content):
        return content

    def GET(self, request):
        cacheOutput = False
        if request in ['ns-api-stations']:
            f = codecs.open('/tmp/'+request, 'r', 'utf-8')
            if f:
                content = f.read().encode('utf-8')
                f.close()
                if len(content) > 0:
                    return self.processor(content)
            cacheOutput = True

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
            resp, content = h.request("https://webservices.ns.nl/"+request+web.ctx.query)

            if cacheOutput == True:
                f = codecs.open('/tmp/'+request, encoding='utf-8', mode='w')
                f.write(content)
                f.close()

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
        return NSAPI.GET(self, "ns-api-stations")

    def processor(self, content):
        if len(dstations) == 0:
            root = ElementTree.XML(content)
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

class ToIrailLiveboard(NSAPI):
    def __init__(self):
        station = ''

    def GET(self, station):
        user_data = web.input()
        self.station = user_data.station
        web.ctx.query = ''
        return NSAPI.GET(self, "ns-api-avt?station="+self.station)

    def getStationFromCache(self, name):
        name = name.lower()
        for (code, station) in dstations.items():
            if name == code.lower() or name == station['defaultname'].lower():
                return station
            elif name in sorted(station['alias'], key=str.lower):
                return station

        return None

    def renderStation(self, root, name):
        station = self.getStationFromCache(self.station)
        sub = ElementTree.SubElement(root, 'station')
        if station is not None:
            sub.attrib['locationX'] = station['locationX']
            sub.attrib['locationY'] = station['locationY']
            sub.attrib['defaultname'] = station['defaultname']
        sub.text = self.station

    def processor(self, content):
        # XSLT was invented for these kind of transformations
        
        dtreinen = []
        root = ElementTree.XML(content)
        treinen = root.findall('.//VertrekkendeTrein')
        for trein in treinen:
            result = {}
            result['vertrektijd'] = trein.find('.//VertrekTijd').text
            spoor = trein.find('.//VertrekSpoor')
            result['spoor'] = spoor.text
            result['spoorwijziging'] = spoor.attrib['wijziging']
            result['station'] = trein.find('.//EindBestemming')

            vehicle = trein.find('.//TreinSoort')
            if vehicle is not None:
                result['type'] = vehicle.text

            vertraging = trein.find('.//VetrekVertragingTekst')
            if vertraging:
                result['vertraging'] = vertraging.text

            dtreinen.append(result)

        root = ElementTree.Element('liveboard')
        root.attrib['version'] = "1.0"
        root.attrib['timestamp'] = str(int(time.time()))

        self.renderStation(root, self.station)

        departures = ElementTree.SubElement(root, 'departures')
        departures.attrib['number'] = str(len(dtreinen))

        for trein in dtreinen:
            departure = ElementTree.SubElement(departures, 'departure')
            if 'vertraging' in trein:
                departure.attrib['delay'] = trein['vertraging']

            self.renderStation(departure, self.station)

            if 'type' in trein:
                sub = ElementTree.SubElement(departure, 'vehicle')
                sub.text = trein['type']
            
            if 'vertrektijd' in trein:
                sub = ElementTree.SubElement(departure, 'time')
                sub.attrib['formatted'] = 'iso8601'
                sub.text = trein['vertrektijd']

            if 'spoor' in trein:
                sub = ElementTree.SubElement(departure, 'platform')
                sub.text = trein['spoor']

                if 'spoorwijziging' in trein:
                    sub.attrib['change'] = trein['spoorwijziging']

        return ElementTree.tostring(root)

application = app.wsgifunc()
