import socket
import threading
import json, hashlib
import argparse
import os

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_port = 3939
sock.bind(('', server_port))
print(f"Server bound to {server_port}")

sock.listen()

while True:
    conn, addr = sock.accept()
    # threading.Thread(target=handle_peer, args=(conn,)).start() // Peer-Handling logic here. 
    print(f"Connected to {conn} and {addr}")

    

