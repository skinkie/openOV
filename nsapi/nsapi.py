import web
import base64
import re
import httplib2
import cElementTree as ElementTree
from XmlDictConfig import XmlDictConfig
import simplejson

urls = (
    '/xml/(.*)', 'NSAPI',
    '/json/(.*)','ToJSON'
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

application = app.wsgifunc()
