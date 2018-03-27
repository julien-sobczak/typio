#!/usr/bin/env python3
"""
Very simple HTTP server in python for saving POST requests into a folder.

Body should be valid JSON.
 
Usage::
    ./collector.py [<port>] [<directory>]

Notes: 

- You can pass the filename as a query parameter named `name`. 
Ex: http://localhost:8080?name=en.js
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import json
import os
import time
import urllib

directory = "."

class S(BaseHTTPRequestHandler):
    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        logging.info("GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers))
        self._set_response()
        self.wfile.write("GET request for {}".format(self.path).encode('utf-8'))

    def do_POST(self):
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length) # <--- Gets the data itself
        logging.info("POST %s\n", str(self.path))

        path = str(self.path)
        parameters = {}
        if '?' in path:
            parameters = urllib.parse.parse_qs(path[path.find('?') + 1:])
        
        self._set_response()
        self.wfile.write("POST request for {}".format(self.path).encode('utf-8'))

        if "name" in parameters:
            filename = parameters['name'][0]
        else:
            filename = 'data' + str(time.time()) + '.json'
        
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w') as f:
            json.dump(json.loads(post_data), f, sort_keys=True, indent=4, ensure_ascii=False)
            print('Saved to file %s' % filepath)

def run(server_class=HTTPServer, handler_class=S, port=8080):
    logging.basicConfig(level=logging.INFO)
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logging.info('Starting httpd...\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping httpd...\n')

if __name__ == '__main__':
    from sys import argv

    if len(argv) == 3:
        directory = argv[2]        
    if len(argv) >= 2:
        run(port=int(argv[1]))
    else:
        run()
