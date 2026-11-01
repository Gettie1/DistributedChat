
import socket
import threading
import sys
import time

HOST = "127.0.0.1"

# Choose which server node to run.
NODE = int(sys.argv[1]) if len(sys.argv) > 1 else 1

if NODE == 1:
    CLIENT_PORT = 5000
    PEER_PORT = 6000
    PEER_HOST = "127.0.0.1"
    PEER_TARGET_PORT = 6001
else:
    CLIENT_PORT = 5001
    PEER_PORT = 6001
    PEER_HOST = "127.0.0.1"
    PEER_TARGET_PORT = 6000

clients = []
clients_lock = threading.Lock()

peer_connection = None
peer_lock = threading.Lock()



def send_to_peer(message):
    """Forward a message and reset a failed peer connection."""
    global peer_connection

    with peer_lock:
        peer = peer_connection

        if peer is None:
            print("Peer unavailable. Message not forwarded.")
            return

        try:
            peer.sendall((message + "\n").encode("utf-8"))

        except OSError:
            print("Peer connection lost.")

            if peer_connection is peer:
                peer_connection = None

            try:
                peer.close()
            except OSError:
                pass



def broadcast_local(message):
    """Broadcast a message to clients connected to this node."""
    with clients_lock:
        connected_clients = list(clients)

    for client in connected_clients:
        try:
            client.sendall((message + "\n").encode("utf-8"))
        except OSError:
            remove_client(client)


def remove_client(client):
    """Remove a disconnected client."""
    with clients_lock:
        if client in clients:
            clients.remove(client)


def handle_client(client, address):
    """Handle messages from a local chat client."""
    print(f"Client connected: {address}")

    try:
        with client:
            file = client.makefile("r", encoding="utf-8")

            with clients_lock:
                clients.append(client)

            for line in file:
                message = line.rstrip("\r\n")

                if not message:
                    continue

                formatted = (
                    f"Node {NODE} | "
                    f"{address[0]}:{address[1]} | "
                    f"{message}"
                )

                print(formatted)

                # Deliver to clients on this node.
                broadcast_local(formatted)

                # Forward to the other node.
                send_to_peer(formatted)

    except (OSError, UnicodeError) as error:
        print(f"Client error: {error}")

    finally:
        remove_client(client)
        print(f"Client disconnected: {address}")


def handle_peer(peer, address):
    """Receive messages forwarded from the other server."""
    global peer_connection

    print(f"Peer connected: {address}")

    try:
        with peer:
            file = peer.makefile("r", encoding="utf-8")

            for line in file:
                message = line.rstrip("\r\n")

                if message:
                    print(f"Received from peer: {message}")

                    # Only broadcast locally.
                    # Do not forward it back to the peer.
                    broadcast_local(message)

    except (OSError, UnicodeError) as error:
        print(f"Peer error: {error}")

    finally:
        with peer_lock:
            if peer_connection is peer:
                peer_connection = None

        print("Peer connection closed.")


def start_listener(port, handler):
    """Listen for incoming client or peer connections."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((HOST, port))
    server.listen()

    print(f"Node {NODE} listening on port {port}")

    while True:
        connection, address = server.accept()

        thread = threading.Thread(
            target=handler,
            args=(connection, address),
            daemon=True
        )
        thread.start()


def connect_to_peer():
    """Keep trying to connect to the other server."""
    global peer_connection

    while True:
        with peer_lock:
            connected = peer_connection is not None

        if not connected:
            try:
                peer = socket.socket(
                    socket.AF_INET,
                    socket.SOCK_STREAM
                )

                peer.connect((PEER_HOST, PEER_TARGET_PORT))

                with peer_lock:
                    if peer_connection is None:
                        peer_connection = peer
                        peer = None

                if peer is None:
                    print("Connected to the other server.")

                    # The server can now receive messages from this peer.
                    # Outgoing messages use the same connection.
                    continue

                peer.close()

            except OSError:
                print("Waiting for peer server...")

        time.sleep(3)


def start_server():
    print(f"Starting Server Node {NODE}")

    threading.Thread(
        target=start_listener,
        args=(CLIENT_PORT, handle_client),
        daemon=True
    ).start()

    threading.Thread(
        target=start_listener,
        args=(PEER_PORT, handle_peer),
        daemon=True
    ).start()

    threading.Thread(
        target=connect_to_peer,
        daemon=True
    ).start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    start_server()
