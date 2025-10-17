import socket
import threading
import json

file_database = dict()
registry_lock = threading.Lock()

class P2PServer:
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
                peer_thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                peer_thread.daemon = True
                peer_thread.start()
        except KeyboardInterrupt:
            print("Server: Shutting down server.")
        finally:
            self.server_socket.close()

    def handle_client(self, conn, addr):
        peer_id = f"{addr[0]}:{addr[1]}"
        try:
            while True:
                data = conn.recv(4096).decode()
                if not data:
                    break

                request = json.loads(data)
                command = request.get("request_type") # Changed to match client
                payload = request.get("payload")

                if command == "REGISTER_REQUEST":
                    print(f"Server: Handling REGISTER_REQUEST from {peer_id}")
                    with registry_lock:
                        peer_ip = payload.get("endpoint", {}).get("peer_ip")
                        peer_port = payload.get("endpoint", {}).get("peer_port")
                        seeder_id = f"{peer_ip}:{peer_port}"

                        for file_info in payload.get("files", []):
                            file_name = file_info.get("file_name")
                            if file_name not in file_database:
                                file_database[file_name] = {"file_len": file_info.get("file_len"), "peers": {}}
                            file_database[file_name]["peers"][seeder_id] = list(range(100))
                    response = {"status": "success", "message": "File Registered successfully"}
                    conn.sendall(json.dumps(response).encode())

                elif command == "FILE_LIST_REQUEST":
                    print(f"Server: Handling FILE_LIST_REQUEST from {peer_id}")
                    with registry_lock:
                        file_list = [{"file_name": fn, "file_len": fi["file_len"]} for fn, fi in file_database.items()]
                    response = {"files": file_list}
                    conn.sendall(json.dumps(response).encode())

                elif command == "FILE_LOCATIONS_REQUEST":
                    print(f"Server: Handling FILE_LOCATIONS_REQUEST from {peer_id}")
                    file_name = payload.get("file_name")
                    with registry_lock:
                        if file_name in file_database:
                            peers = file_database[file_name]["peers"]
                            response = {"peers": peers}
                        else:
                            response = {"error": "File not found"}
                    conn.sendall(json.dumps(response).encode())

                elif command == "CHUNK_REGISTER_REQUEST":
                    print(f"Server: Handling CHUNK_REGISTER_REQUEST from {peer_id}")
                    file_name = payload.get("file_name")
                    chunk_index = payload.get("chunk_indicator")
                    peer_ip = payload.get("new_seeder_endpoint", {}).get("peer_ip")
                    peer_port = payload.get("new_seeder_endpoint", {}).get("peer_port")
                    leecher_id = f"{peer_ip}:{peer_port}"

                    with registry_lock:
                        if file_name in file_database:
                            if leecher_id not in file_database[file_name]["peers"]:
                                file_database[file_name]["peers"][leecher_id] = []
                            if chunk_index not in file_database[file_name]["peers"][leecher_id]:
                                file_database[file_name]["peers"][leecher_id].append(chunk_index)
                            response = {"status": "success", "message": "Chunk registered successfully"}
                        else:
                            response = {"status": "error", "message": "File not found"}
                    conn.sendall(json.dumps(response).encode())

                else:
                    # Status is now a string to prevent the client's validation error
                    response = {"status": "error", "message": "Unknown command"}
                    conn.sendall(json.dumps(response).encode())

        except Exception as e:
            print(f"Server: Error handling peer {peer_id}: {e}")
        finally:
            print(f"Server: Terminating Connection for {peer_id}")
            conn.close()