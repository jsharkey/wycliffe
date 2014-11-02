
import SocketServer
import BaseHTTPServer

from string import Template

val = {
    "cur": "start",
    "curLabel": "STARTED",
    "next": "stop",
    "nextLabel": "STOP",
    "curVideo": "vSTAGE",
    "curVideoAgo": "30 sec",
    "curAudio": "[aPLVOX, aWLINST, aDRUMS, aBASS]",
    "danteRmsAgo": "30 sec",
    "danteRebootAgo": "5 hrs",
    "debugLog": "00:00:00 Meow debug text",
}

with open("template.html") as f:
    status_templ = Template(f.read())

print status_templ

class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        if "stop=STOP" in self.path:
            print "ZOMG STOP!"

            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if "start=START" in self.path:
            print "ZOMG START!"

            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        # always dump current status
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        self.wfile.write(status_templ.substitute(val))






SocketServer.TCPServer.allow_reuse_address = True
server = SocketServer.TCPServer(("",8080), MyHandler)
server.serve_forever()
