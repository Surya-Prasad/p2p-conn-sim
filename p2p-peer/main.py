# Start a peer_seed or a peer_leech based on command line args

import argparse
from client_socket import peer_seed
from client_socket import peer_leech


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P2P Client")
    parser.add_argument('--mode', choices=['seed', 'leech'], required=True, help="Mode: 'seed' to send files, 'leech' to receive files")
    args = parser.parse_args()
    print("args:", args)

    if args.mode == 'seed':
        print("Starting in seed mode...")
        peer_seed()
    elif args.mode == 'leech':
        print("Starting in leech mode...")
        peer_leech()
    else:
        print("Invalid mode. Use --mode seed or --mode leech.")