import os
import datetime
import tqdm

CHUNK_SIZE = 1024
# Implement chunk sizes
# Right now, one single file
def send_chunk(sender_sock):
    file = open("complete-files/image.png", 'rb')
    file_size = os.path.getsize('complete-files/image.png')

    timestamp = datetime.datetime.now().strftime("%d%m%Y-%H%M%S")
    sender_sock.send(f"sender_Image_{timestamp}.png".encode())
    sender_sock.send(str(file_size).encode())

    data = file.read()
    sender_sock.sendall(data)
    sender_sock.send(b"<EOF>")

    file.close()

def receive_chunk(receiver_sock):

    file_name = receiver_sock.recv(CHUNK_SIZE).decode()
    print(f"File Name: {file_name}")
    file_size = receiver_sock.recv(CHUNK_SIZE).decode()
    print(f"File Size: {file_size}")

    file = open(file_name, 'wb')

    file_chunk_stream = b""

    done = False

    progressbar = tqdm.tqdm(unit="B", unit_scale=True, unit_divisor=1000, total=int(file_size))

    while not done:
        data = receiver_sock.recv(CHUNK_SIZE)
        
        if file_chunk_stream[-5:] == b"<EOF>":
            done = True
        else: 
            file_chunk_stream += data
        progressbar.update(CHUNK_SIZE)

    file.write(file_chunk_stream)
    file.close()

