#!/bin/bash

apt update && apt upgrade -y
apt install -y python3 python3-pip squid apache2-utils

mkdir -p /opt/yt_proxy
pip3 install pytubefix urllib3

cat > /opt/yt_proxy/yt_server.py << 'EOF'
from urllib.parse import urlparse, unquote
from pytubefix import YouTube
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class YTRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            if parsed_path.path.startswith("/yt/"):
                yt_url = unquote(parsed_path.path[4:])
                if "youtube.com" in yt_url or "youtu.be" in yt_url:
                    yt = YouTube(yt_url)
                    video_data = {
                        "title": yt.title,
                        "author": yt.author,
                        "length": yt.length,
                        "views": yt.views,
                        "description": yt.description,
                        "thumbnail_url": yt.thumbnail_url,
                        "streams": [
                            {
                                "itag": stream.itag,
                                "mime_type": stream.mime_type,
                                "resolution": stream.resolution,
                                "url": stream.url,
                            }
                            for stream in yt.streams
                        ],
                    }
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps(video_data, indent=4).encode("utf-8"))
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"400 Bad Request: Invalid YouTube URL")
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"404 Not Found")
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

def run_server(port=3341):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, YTRequestHandler)
    print(f"Server running on http://127.0.0.1:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
EOF

chmod +x /opt/yt_proxy/yt_server.py

cat > /etc/systemd/system/yt_proxy.service << 'EOF'
[Unit]
Description=YouTube Proxy Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/yt_proxy/yt_server.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable yt_proxy
systemctl start yt_proxy

htpasswd -bc /etc/squid/passwd proxyuser gyatgyat

cat > /etc/squid/squid.conf << 'EOF'
http_port 3128
acl authenticated proxy_auth REQUIRED
http_access allow authenticated
http_access deny all
auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/passwd
auth_param basic realm Proxy
EOF

systemctl restart squid
systemctl enable squid

echo "Setup complete. The YouTube proxy server is running on port 3341, and Squid is running on port 3128 with authentication."