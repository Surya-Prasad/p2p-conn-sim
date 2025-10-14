import socket
import threading
import json, hashlib
import argparse
import os
import datetime
import tqdm
from client_chunk_process import send_chunk
from client_chunk_process import receive_chunk

def peer_seed():

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    sender_port = 9999
    sender_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sender_sock.connect(('127.0.0.1', sender_port))

    send_chunk(sender_sock)

    sender_sock.close()

def peer_leech(): 

    # Read peer seeds from torrent file? 

    receiver_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    receiver_port = 9999
    receiver_sock.bind(('127.0.0.1', receiver_port))
    print(f"Receiver bound to {receiver_port}")

    receiver_sock.listen()

    while True:
        conn, addr = receiver_sock.accept()
        print(f"Connected to {conn} and {addr}")
        receive_chunk(conn)
        conn.close()
        # threading.Thread(target=handle_peer, args=(conn,)).start() // Peer-Handling logic here. 

        receiver_sock.close()   

    

