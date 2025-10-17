import datetime
import socket
import threading
import json
import os
import hashlib
import argparse
import time
import tqdm
import math
from pydantic import BaseModel

from models.common_models import endpointModel, requestedFileModel
from models.peer_request_models import RegisterRequest, FileChunkRequest, FileListRequest, FileLocationsRequest
from models.server_response_models import FileRegisterReply, FileListReply, FileLocationsReply

NUMBER_OF_PIECES = 100
SERVER_ADDRESS = ('127.0.0.1','9999')
DOWNLOAD_DIRECTORY = "complete-files/" 

"""
Ensures that there are NUMBER_OF_PIECES pieces for each file transmitted.
"""
def calculate_chunk_size(file_len: int, num_chunks: int) -> int:
    return math.ceil(file_len / num_chunks)

class Peer:
    def __init__(self, mode, share_dir, peer_port):
        self.share_dir = share_dir
        if not os.path.exists(self.share_dir):
            os.makedirs(self.share_dir)
        if not os.path.exists(DOWNLOAD_DIRECTORY):
            os.makedirs(DOWNLOAD_DIRECTORY)

        self.server_conn = None
        self.mode = mode
        self.endpoint = endpointModel(peer_ip='127.0.0.1', peer_port=peer_port)

    def send_request(self, request_model: BaseModel):
        if not self.server_conn:
            print("Peer: Not connected to server.")
            return
        self.server_conn.sendall(request_model.json().encode())

    def receive_response(self, timeout = 5):
        self.server_conn.settimeout(timeout)
        try: 
            response_data = self.server_conn.recv(65536)
            if not response_data:
                print("Peer: No response data received.")
            return response_data
        except socket.timeout:
            print("Peer: Response timed out.")
            return None
        finally:
            self.server_conn.settimeout(None)

    def connect_to_server(self):
        try:
            self.server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_conn.connect(SERVER_ADDRESS)
            print(f"Peer: Connected to server at {SERVER_ADDRESS}")
        except Exception as e:
            print(f"Peer: Failed to connect to server at {SERVER_ADDRESS}. Error: {e}")
            self.server_conn = None

    def register_files_with_server(self):
        if not self.server_conn:
            print("Peer, register_files_with_server: Not connected to server.")
            return
        
        seed_files = []
        for f in os.listdir(self.share_dir):
            if os.path.isfile(os.path.join(self.share_dir, f)):
                file_path =os.path.join(self.share_dir, f)
                seed_files.append(requestedFileModel(
                    file_name=f, 
                    file_len=os.path.getsize(file_path)
                ))

        if not seed_files:
            print("Peer, register_files_with_server: No files to register.")
            return
        
        register_request = RegisterRequest(
            endpoint=self.endpoint,
            number_of_files_to_register=len(seed_files),
            files=seed_files
        )

        print(f"Peer, register_files_with_server: Registering {len(seed_files)} files with server.")
        self.send_request(register_request)
        response_data = self.receive_response()
        if response_data:
            reply = FileRegisterReply.model_validate_json(response_data)
            print(f"Peer, register_files_with_server: Server response - Status: {reply.status}, Message: {reply.message}")



    def start_upload_server(self): 
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.endpoint.peer_ip, self.endpoint.peer_port))
        server_sock.listen()
        print(f"Peer: Seed listening on {self.endpoint.peer_ip}:{self.endpoint.peer_port} for uploads.")
        while True:
            conn, addr = server_sock.accept()
            print(f"Peer: Connected to leecher at {addr}")
            upload_thread = threading.Thread(target=self.handle_chunk_request, args=(conn,addr))
            upload_thread.start()

    def handle_chunk_request(self, conn, addr):
        try:
            request_json = conn.recv(1024).decode()
            request = FileChunkRequest.model_validate_json(request_json)
            
            file_name = request.file.file_name
            chunk_index = request.chunk_indicator
            print(f"Peer: handle_chunk_request: Received request for chunk {chunk_index} of {file_name} from {addr}")

            filepath = os.path.join(self.share_dir, file_name)
            file_len = os.path.getsize(filepath)
            
            # Chunk size based on size set above
            CHUNK_SIZE = calculate_chunk_size(file_len, NUMBER_OF_PIECES)
            # Start of chunk
            start_offset = chunk_index * CHUNK_SIZE

            with open(filepath, 'rb') as f:
                # Reads from chunk start to chunk size
                f.seek(start_offset)
                chunk_data = f.read(CHUNK_SIZE)

                # SHA-256 chosen for chunk integrity
                chunk_hash = hashlib.sha256(chunk_data).hexdigest()

                # Simple Header defined to contain size and hash of chunk
                header = {"size": len(chunk_data), "hash": chunk_hash}
                
                conn.sendall(json.dumps(header).encode() + b'\n')
                conn.sendall(chunk_data)

        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Peer: handle_chunk_request: Error handling chunk request: {e}")
        finally:
            conn.close()

    def create_piece_file(self, file_info: requestedFileModel, piece_index: int, chunk_data: bytes):
        piece_name = f"{file_info.file_name}-part{piece_index}"
        piece_filename = f"{piece_name}.piece"
        
        # Create a new directory for downloaded pieces if it doesn't exist
        piece_directory = os.path.join(DOWNLOAD_DIRECTORY, piece_name)
        if not os.path.exists(piece_directory):
            os.makedirs(piece_directory)
        piece_filepath = os.path.join(piece_directory, piece_filename)
        with open(piece_filepath, 'wb') as pf:
            pf.write(chunk_data)
        print(f"Peer: create_piece_file: Saved piece {piece_index} of {file_info.file_name} to {piece_filepath}")

    def leech_chunk(self, peer_endpoint: endpointModel, file_info: requestedFileModel, chunk_index: int):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((peer_endpoint.peer_ip, peer_endpoint.peer_port))
                
                request = FileChunkRequest(file=file_info, chunk_indicator=chunk_index)
                sock.sendall(request.model_dump_json().encode())

                header_data = b""
                while b'\n' not in header_data:
                    header_data += sock.recv(1)
                header = json.loads(header_data.strip())
                
                chunk_size_from_peer = header['size']
                chunk_data = b""
                
                # ** TQDM PROGRESS BAR INTEGRATION **
                
                with tqdm(total=chunk_size_from_peer, 
                          desc= f"Peer: leech_chunk:Downloading chunk {chunk_index}/{NUMBER_OF_PIECES-1} from {peer_endpoint.peer_ip}", 
                          unit='B', 
                          unit_scale=True, 
                          unit_divisor=1024, 
                          leave=False) as progressbar:
                    while len(chunk_data) < chunk_size_from_peer:
                        # Read only chunk_size_from_peer bytes
                        bytes_to_read = chunk_size_from_peer - len(chunk_data)
                        # Limiting to 4096 bytes per read, to avoid large memory usage
                        packet = sock.recv(min(bytes_to_read, 4096))
                        if not packet: break
                        chunk_data += packet
                        progressbar.update(len(packet))

                if hashlib.sha256(chunk_data).hexdigest() != header['hash']:
                    print(f"Peer: leech_chunk: Piece {chunk_index} from {peer_endpoint.peer_ip} does not have a valid hash. Dropping the piece.")
                    return

                print(f"Peer: leech_chunk: Piece {chunk_index} of {file_info.file_name} received successfully from {peer_endpoint.peer_ip}.")
                # TODO: Save chunk to a temp file and register completion with server
                
                self.create_piece_file(file_info, chunk_index, chunk_data)

        except Exception as e:
            print(f"Peer: leech_chunk: Failed to download chunk {chunk_index}: {e}")

    def start(self):
        server_thread = threading.Thread(target=self.start_upload_server, daemon=True)
        server_thread.start()

        self.connect_to_server()
        if self.server_conn:
            self.register_files_with_server()
            self.mode_selector(self.mode, self.share_dir, self.endpoint.peer_port)
            self.server_conn.close()

        

    def mode_selector(self, mode, share_dir, peer_port):
        mode = ''
        while True:
            time.sleep(1)
            if self.mode == 'seed':
                

