# Start a peer_seed or a peer_leech based on command line args

import argparse
import client_chunk_process


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P2P Client")
    parser.add_argument('--mode', choices=['seed', 'leech'], required=True, help="Mode: 'seed' to send files, 'leech' to receive files")
    parser.add_argument('--share-dir', required=True, help="Directory of files to seed.")
    parser.add_argument('--peer-port', required=True, type=int, help="Port for this peer to listen on.")
    args = parser.parse_args()

    peer = client_chunk_process.PeerClient(
        mode = args.mode,
        share_dir = args.share_dir,
        peer_port = args.peer_port
    )

    peer.start()