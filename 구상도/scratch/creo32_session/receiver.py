from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import json
dest=Path(__file__).resolve().parent/'build_report.json'
class Receiver(BaseHTTPRequestHandler):
 def do_OPTIONS(self):
  self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Methods','POST,OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers()
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0'))
  if self.path!='/result' or n>2000000:self.send_error(400);return
  value=json.loads(self.rfile.read(n));dest.write_text(json.dumps(value,indent=2),encoding='utf-8')
  self.send_response(200);self.send_header('Access-Control-Allow-Origin','*');self.end_headers();self.wfile.write(b'OK')
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',9142),Receiver).serve_forever()
