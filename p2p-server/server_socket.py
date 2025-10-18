import socket
import threading
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import server_response_models
from models.common_models import requestedFileModel

NUMBER_OF_PIECES = 10
file_database = dict()
file_metadata = dict()
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
        try:
            while True:
                peer_id = str(addr[0])+":"+str(addr[1])
                data = conn.recv(4096).decode()
                if not data:
                    break
                request = json.loads(data)
                request_type = request.get("request_type")
                payload = request.get("payload")

                try:
                    if request_type == "REGISTER_REQUEST":
                        peer_ip = payload.get("endpoint",{}).get("peer_ip")
                        peer_port = payload.get("endpoint",{}).get("peer_port")
                        number_of_files_to_register = payload.get("number_of_files_to_register")
                        peer_id = str(peer_ip) + ":" + str(peer_port)
                        all_chunks = list(range(NUMBER_OF_PIECES))
                        with registry_lock:
                            for file in payload.get("files",[]):
                                file_name = file.get("file_name")
                                file_len = file.get("file_len")
                                if file_name not in file_database:
                                    file_database[file_name] = {peer_id:all_chunks}
                                    file_metadata[file_name] = file_len
                                else:
                                    if peer_id not in file_database[file_name]:
                                        file_database[file_name][peer_id] = all_chunks
                        response = {"status": "success", "message": "File Registered successfully"}
                        conn.sendall(json.dumps(response).encode())

                except Exception as e:
                    response = {"status":"502","message":str(e)}
                    conn.sendall(json.dumps(response).encode())

                try:   
                    if request_type == "FILE_LIST_REQUEST":
                        number_of_files = len(file_database.keys())
                        files_list_models = [requestedFileModel(file_name=name, file_len=length) 
                                            for name, length in file_metadata.items()]
                        
                        response = server_response_models.FileListReply(
                            number_of_files=number_of_files,
                            files=files_list_models # Pass the new list here
                        )
                        conn.sendall(response.model_dump_json().encode())
                except Exception as e:
                    response = {"status":"502","message":str(e)}
                    conn.sendall(json.dumps(response).encode())
                    
                try:  
                    if request_type == "FILE_LOCATIONS_REQUEST":
                        file_name = payload.get("file_name")
                        peers = len(file_database.get(file_name,{}))
                        chunkendpoint_map = file_database.get(file_name,{})
                        response = server_response_models.FileLocationsReply(peers=peers,chunk_endpoint_map=chunkendpoint_map)
                        conn.sendall(response.model_dump_json().encode())
                except Exception as e:
                    response = {"status":"502","message":str(e)}
                    conn.sendall(json.dumps(response).encode())

                try:  
                    if request_type == "CHUNK_REGISTER_REQUEST":
                        chunk_indicator = payload.get("chunk_indicator")
                        fname = payload.get("file_name")
                        pid = payload.get("new_seeder_endpoint")
                        peer_ip = pid.get("peer_ip")
                        peer_port = pid.get("peer_port")
                        peer_id = f"{peer_ip}:{peer_port}"
                        
                        
                        with registry_lock:
                            if fname not in file_database:
                                file_database[fname] = {peer_id:[]}
                            if peer_id not in file_database[fname]:
                                file_database[fname][peer_id] = []
                            if chunk_indicator not in file_database[fname][peer_id]:
                                file_database[fname][peer_id].append(chunk_indicator)
                        
                        response = {"status": "success", "message": "File Registered successfully"}
                        conn.sendall(json.dumps(response).encode())

                except Exception as e:
                    response = {"status":"502","message":str(e)}
                    conn.sendall(json.dumps(response).encode())
        except Exception as e:
            print(str(e))   


            

            