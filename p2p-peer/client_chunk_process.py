import datetime
import socket
import threading
import json
import os
import hashlib
import time
import tqdm
import math
from pydantic import BaseModel
import sys
import random

# Add project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.common_models import endpointModel, requestedFileModel
from models.peer_request_models import RegisterRequest, FileChunkRequest, FileListRequest, FileLocationsRequest, ChunkRegisterRequest
from models.server_response_models import FileRegisterReply, FileListReply, FileLocationsReply

NUMBER_OF_PIECES = 10
SERVER_ADDRESS = ('127.0.0.1', 7777)
DOWNLOAD_DIRECTORY = "complete-files/" 

"""
Ensures that there are NUMBER_OF_PIECES pieces for each file transmitted.
"""
def calculate_chunk_size(file_len: int, num_chunks: int) -> int:
    return math.ceil(file_len / num_chunks)

"""
Class is chosen so that an object can be instantiated for every Seeder or Leecher
"""
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
        self.downloaded_chunks = {}

    """
    Send request_type and request payload to Server
    """
    def send_request(self, request_type: str, request_model: BaseModel):
        if not self.server_conn:
            print("Peer: Not connected to server.")
            return
        request = {"request_type": request_type, "payload": request_model.model_dump()}
        self.server_conn.sendall(json.dumps(request).encode())

    """
    Receive Response from Server
    """
    def receive_response(self, timeout = 5):
        self.server_conn.settimeout(timeout)
        try: 
            response_data = self.server_conn.recv(65536)
            if not response_data:
                print("Peer: No response data received.")
                return None
            return json.loads(response_data.decode())
        except Exception as e:
            print(f"Peer: Response receive error: {e}")
            return None
        finally:
            self.server_conn.settimeout(None)

    """
    Socket Connection to Server
    """
    def connect_to_server(self):
        try:
            self.server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_conn.connect(SERVER_ADDRESS)
            print(f"Peer: Connected to server at {SERVER_ADDRESS}")
        except Exception as e:
            print(f"Peer: Failed to connect to server at {SERVER_ADDRESS}. Error: {e}")
            self.server_conn = None

    """
    Register files in seeding directory of Peer with Server
    """
    def register_files_with_server(self):
        # Check if Server Connection exists
        if not self.server_conn:
            print("Peer: register_files_with_server: Not connected to server.")
            return
        
        # Build list of files to register
        seed_files = []
        for f in os.listdir(self.share_dir):
            if os.path.isfile(os.path.join(self.share_dir, f)):
                file_path = os.path.join(self.share_dir, f)
                seed_files.append(requestedFileModel(
                    file_name = f,
                    file_len = os.path.getsize(file_path)
                ))

        if not seed_files:
            print("Peer, register_files_with_server: No files to register.")
            return
         
        # Construct RegisterRequest payload
        register_request = RegisterRequest(
            endpoint = self.endpoint,
            number_of_files_to_register = len(seed_files),
            files = seed_files
        )

        # Sending REGISTER_REQUEST to Server
        print(f"Peer, register_files_with_server: Registering {len(seed_files)} files with server.")
        self.send_request("REGISTER_REQUEST", register_request)
        response_data = self.receive_response()
        if response_data:
            reply = FileRegisterReply.model_validate(response_data)
            print(f"Peer, register_files_with_server: Server response - Status: {reply.status}, Message: {reply.message}")
    """
    Register a single file with the server after leecher completes download.
    Leecher will now become seeder for this file.
    Hindsight: Could have easily passed number of files to transfer as parameter, but sticking to this because of time constraints.
    """
    def register_file_with_server(self, file_path: str):
        # Check if Server Connection exists
        # self.connect_to_server()
        if not self.server_conn:
            print("Peer, register_file_with_server: Not connected to server.")
            return
        
        # REGISTER_REQUEST for Each File
        file_name = os.path.basename(file_path)
        file_len = os.path.getsize(file_path)
        
        register_request = RegisterRequest(
            endpoint=self.endpoint,
            number_of_files_to_register=1,
            files=[requestedFileModel(file_name=file_name, file_len=file_len)]
        )

        # Sending REGISTER_REQUEST to Server
        print(f"Peer, register_file_with_server: Registering file {file_name} with server.")
        self.send_request("REGISTER_REQUEST", register_request)
        response_data = self.receive_response()
        if response_data:
            reply = FileRegisterReply.model_validate(response_data)
            print(f"Peer, register_file_with_server: Server response - Status: {reply.status}, Message: {reply.message}")



    def start_upload_server(self): 
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.endpoint.peer_ip, self.endpoint.peer_port))
        server_sock.listen()
        print(f"Peer: Seed listening on {self.endpoint.peer_ip}:{self.endpoint.peer_port} for uploads.")
        while True:
            conn, addr = server_sock.accept()
            print(f"Peer: Connected to leecher at {addr}")
            upload_thread = threading.Thread(target=self.handle_chunk_request, args=(conn, addr))
            upload_thread.start()


    """
   Process the file to be sent in chunks from Seeder to Leecher
    """
    def handle_chunk_request(self, conn, addr):
        try:
            # Leecher requests a chunk using FileChunkRequest
            request_json = conn.recv(1024).decode()
            request = FileChunkRequest.model_validate_json(request_json)
            
            file_name = request.file.file_name
            chunk_index = request.chunk_indicator
            print(f"Peer: handle_chunk_request: Received request for chunk {chunk_index} of {file_name} from {addr}")

            filepath = os.path.join(self.share_dir, file_name)
            file_len = os.path.getsize(filepath)
            
            # Chunk size based on number of pieces set statically
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
                print(f"Peer: handle_chunk_request: Showcase of Integrity Check: chunk_hash: {chunk_hash}")

        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Peer: handle_chunk_request: Error handling chunk request: {e}")
        finally:
            conn.close()

    """
    Receives the chunk and writes it to a piece file
    Piece files will be present in DOWNLOAD_DIRECTORY with naming convention: file_name-part{piece_index}.piece
    """
    def create_piece_file(self, file_info: requestedFileModel, piece_index: int, chunk_data: bytes):
        # Set file naming convention
        piece_name = f"{file_info.file_name}-part{piece_index}"
        piece_filename = f"{piece_name}.piece"
        piece_directory = os.path.join(DOWNLOAD_DIRECTORY, file_info.file_name + "_pieces")

        if not os.path.exists(piece_directory):
            os.makedirs(piece_directory)
        piece_filepath = os.path.join(piece_directory, piece_filename)
        with open(piece_filepath, 'wb') as pf:
            pf.write(chunk_data)
        print(f"Peer: create_piece_file: Saved piece {piece_index} of {file_info.file_name} to {piece_filepath}")
        
        if file_info.file_name not in self.downloaded_chunks:
            self.downloaded_chunks[file_info.file_name] = []
        self.downloaded_chunks[file_info.file_name].append(piece_filepath)

    """
     Register the received chunk with the server
     """
    def register_chunk_with_server(self, file_name, chunk_index):
        # Check if Server Connection exists
        print("Entered register_chunk_with_server")
        if not self.server_conn:
            print("Peer, register_chunk_with_server: Not connected to server.")
            return
        
        # Building CHUNK_REGISTER_REQUEST payload
        chunk_register_request = ChunkRegisterRequest(
            chunk_indicator = chunk_index,
            new_seeder_endpoint = self.endpoint,
            file_name = file_name
        )
        self.send_request("CHUNK_REGISTER_REQUEST", chunk_register_request)
        
        response_data = self.receive_response()
        if not response_data:
            print(f"Peer, register_chunk_with_server: No response from server for chunk {chunk_index}")

    """
    This function assembles the file from its pieces after all pieces have been downloaded.
    """
    def assemble_file(self, file_name, num_pieces):
        print(f"Peer: Assembling file {file_name} from pieces.")
        
        # Iterate through the piece directory and write them to single file
        piece_directory = os.path.join(DOWNLOAD_DIRECTORY, file_name + "_pieces")
        output_filepath = os.path.join(self.share_dir, file_name)
        with open(output_filepath, 'wb') as output_file:
            for i in range(num_pieces):
                piece_path = os.path.join(piece_directory, f"{file_name}-part{i}.piece")
                if os.path.exists(piece_path):
                    with open(piece_path, 'rb') as piece_file:
                        output_file.write(piece_file.read())
                else:
                    print(f"Error: Missing piece {i} for file {file_name}. Failed to construct file from pieces.")
                    return
        print(f"File {file_name} assembled successfully in {self.share_dir}.")
        self.register_file_with_server(output_filepath)


    """
    Main function for Leeching
    Design Choice: Limiting to 4096 bytes per read, to avoid large memory usage incase of large chunks
    """
    def leech_chunk(self, peer_endpoint: endpointModel, file_info: requestedFileModel, chunk_index: int):
        try:
            # Establish connection to Seeder, Request chunk
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
                
                with tqdm.tqdm(total=chunk_size_from_peer, 
                          desc= f"Peer: leech_chunk: Downloading chunk {chunk_index}/{NUMBER_OF_PIECES-1} from {peer_endpoint.peer_ip}:{peer_endpoint.peer_port}.", 
                          unit='b',
                          unit_divisor=1024, 
                          unit_scale=True, 
                          leave=False) as progressbar:
                    while len(chunk_data) < chunk_size_from_peer:
                        # Read only chunk_size_from_peer bytes
                        bytes_to_read = chunk_size_from_peer - len(chunk_data)
                        packet = sock.recv(min(bytes_to_read, 4096))
                        if not packet: break
                        chunk_data += packet
                        progressbar.update(len(packet))

                # Integrity Check
                if hashlib.sha256(chunk_data).hexdigest() != header['hash']:
                    print(f"Peer: leech_chunk: Piece {chunk_index} from {peer_endpoint.peer_ip}:{peer_endpoint.peer_port} does not have a valid hash. Dropping the piece.")
                    return

                print(f"Peer: leech_chunk: Piece {chunk_index} of {file_info.file_name} received successfully from {peer_endpoint.peer_ip}:{peer_endpoint.peer_port}.")                
                self.create_piece_file(file_info, chunk_index, chunk_data)
                print("Calling register_chunk_with_server")
                self.register_chunk_with_server(file_info.file_name, chunk_index)

        except Exception as e:
            print(f"Peer: leech_chunk: Failed to download chunk {chunk_index}: {e}")

    """
     Start a thread for a peer
     For seeders, we redirect to register_files_with_server
     For leechers, we redirect to leech_menu
     """
    def start(self):
        server_thread = threading.Thread(target=self.start_upload_server, daemon=True)
        server_thread.start()

        self.connect_to_server()
        if self.server_conn:
            if self.mode == 'seed':
                self.register_files_with_server()
            # Redirect to Leech Menu
            self.mode_selector()
            self.server_conn.close()

        
    """  
    List available files from server 
    """
    def list_files(self):
        # Send FILE_LIST_REQUEST to Server
        self.send_request("FILE_LIST_REQUEST", FileListRequest())
        # Read FILE_LIST_REPLY from Server
        response = self.receive_response()
        if response and "files" in response:
            for f in response["files"]:
                print(f"- {f['file_name']} (Size: {f['file_len']} bytes)")
        else:
            print("Could not retrieve file list.")

    """
    Leech Handler from Peers
    """
    def download_file(self):
        # Send FILE_LOCATIONS_REQUEST to Server
        file_name = input("Enter the name of the file to download: ")
        self.send_request("FILE_LOCATIONS_REQUEST", FileLocationsRequest(file_name=file_name))
        response = self.receive_response()
        print(response)

        # Get Peers List
        if response and "peers" in response:
            peers_with_file = response["peers"]
            chunk_endpoint_map = response["chunk_endpoint_map"]
            if not peers_with_file:
                print("No peers have this file.")
                return

            # Check if File is present in File List
            self.send_request("FILE_LIST_REQUEST", FileListRequest())
            file_list_response = self.receive_response()
            # file_info_dict = next((f for f in file_list_response.get("files", []) if f['file_name'] == file_name), None)
            file_info_dict = {}
            for f in file_list_response.get("files", []):
                if f['file_name'] == file_name:
                    file_info_dict = f
                    break

            if not file_info_dict:
                print("File info not found.")
                return
            
            file_info = requestedFileModel(**file_info_dict)

            # Rarest Chunk First
            all_chunks_possessed = [set(chunks) for chunks in chunk_endpoint_map.values()]
            chunk_counts = {}
            for i in range(NUMBER_OF_PIECES):
                count = sum(1 for chunks in all_chunks_possessed if i in chunks)
                chunk_counts[i] = count
            
            # Sort chunks by rarity (ascending)
            sorted_chunks = sorted(chunk_counts.keys(), key=lambda i: chunk_counts[i])

            download_threads = []
            for chunk_index in sorted_chunks:
                # Find the peer that has this chunk
                peers_with_chunk = [peer_id for peer_id, chunks in chunk_endpoint_map.items() if chunk_index in chunks]
                print(peers_with_chunk)
                if not peers_with_chunk:
                    # Should never happen -> The file should be present with at least one peer
                    continue
                
                # Randomly select a peer from those who have the chunk
                peer_id = peers_with_chunk[0]
                ip, port_str = peer_id.split(":")
                print(f"Seed: {ip}: {port_str}")
                peer_endpoint = endpointModel(peer_ip=ip, peer_port=int(port_str))
                print("Starting leech_chunk")
                thread = threading.Thread(target=self.leech_chunk, args=(peer_endpoint, file_info, chunk_index))
                download_threads.append(thread)
                thread.start()

            print("We HERE")
            # Wait for all threads to complete
            for t in download_threads:
                t.join()

            # Verify all chunks are downloaded before assembling
            if file_name in self.downloaded_chunks and len(self.downloaded_chunks[file_name]) == NUMBER_OF_PIECES:
                 self.assemble_file(file_name, NUMBER_OF_PIECES)
            else:
                print("Download incomplete. Not all pieces were received.")
        else:
            print(f"Could not find file '{file_name}' or no peers are seeding it.")
            

    """
    Leech Interface for User
    """
    def leech_menu(self):
        while True:
            print("\n--- Leech Menu ---")
            print("1. List available files")
            print("2. Download a file")
            print("3. Exit")
            choice = input("Enter your choice: ")

            if choice == '1':
                self.list_files()
            elif choice == '2':
                self.download_file()
            elif choice == '3':
                break
            else:
                print("Invalid choice.")

    """
    Mode Selector Abstraction for Setting the mode of Peer
    Seeds are just registering files and waiting for upload requests
    Leeches request file lists, download files or exit
    """
    def mode_selector(self):        
        if self.mode == 'seed':
            print("Peer: Establishing new Seeder")
            while True:
                time.sleep(1)
        elif self.mode == 'leech':
            print("Peer: Establishing new Leecher")
            self.leech_menu()