import socket
import threading
import json, hashlib
import argparse
import os

file_database = dict()
registry_lock = threading.Lock()

class P2P_Server:
    def __init__(self, host='0.0.0.0', port=7777):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Server: Listening on {self.host}:{self.port}")

    def start_server(self):
        try:
            while True:
                conn, addr = self.server_socket.accept()
                print(f"Server: Connected to {addr}")
                peer_thread = threading.Thread(target=self.handle_client, args=(conn,))
                peer_thread.daemon = True
                peer_thread.start()
        except KeyboardInterrupt:
            print("Server: Shutting down server.")
        finally:
            self.server_socket.close()

    def peer_process(self, conn, addr):
        peer_id = f"{addr[0]}:{addr[1]}"
        try:
            while True:
                data = conn.recv(4096).decode()
                if not data:
                    break

                request = json.loads(data)
                command = request.get("command")
                payload = request.get("payload")

                if command == "REGISTER_REQUEST":
                    print(f"Server: Handling REGISTER_REQUEST from {peer_id}")
                    # Add Registration of Files to file_database

                    response = {"status": 200, "message": "File Registered successfully"}
                    conn.sendall(json.dumps(response).encode())

                elif command == "FILE_LIST_REQUEST":
                    print(f"Server: Handling FILE_LIST_REQUEST from {peer_id}")
                    # Query file_database and send list of files

                    response = {} # Build response with file list
                    conn.sendall(json.dumps(response).encode())

                elif command == "FILE_LOCATIONS_REQUEST":
                    print(f"Server: Handling FILE_LOCATIONS_REQUEST from {peer_id}")
                    # Query file_database and build list of endpoints

                    response = {} # Build response with file location peers
                    conn.sendall(json.dumps(response).encode())

                elif command == "CHUNK_REGISTER_REQUEST":
                    print(f"Server: Handling CHUNK_REGISTER_REQUEST from {peer_id}")
                    # Update file_database with new chunk info
                    response = {"status": 200, "message": "Chunk Registered successfully"}
                    conn.sendall(json.dumps(response).encode())

                else:
                    response = {"status": 500, "message": "Unknown command"}
                    conn.sendall(json.dumps(response).encode())

        except Exception as e:
            print(f"Server: Error handling peer: {e}")
        finally:
            print(f"Server: Terminating Connection for {peer_id}")
            conn.close()
    

