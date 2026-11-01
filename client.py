
import socket
import threading
import time

# Available server nodes
SERVERS = [
    ("127.0.0.1", 5000),  # Server Node 1
    ("127.0.0.1", 5001),  # Server Node 2
]

# Shared connection variables
current_socket = None
current_server = None

connection_lock = threading.Lock()
connected = threading.Event()
stop_event = threading.Event()


def connect_to_server():
    """Try connecting to available servers."""
    global current_socket, current_server

    while not stop_event.is_set():

        # Try the last successful server first
        servers = list(SERVERS)

        if current_server in servers:
            servers.remove(current_server)
            servers.insert(0, current_server)

        for host, port in servers:

            if stop_event.is_set():
                return None

            client = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            client.settimeout(3)

            try:
                client.connect((host, port))
                client.settimeout(None)

                with connection_lock:
                    if stop_event.is_set():
                        client.close()
                        return None

                    current_socket = client
                    current_server = (host, port)
                    connected.set()

                print(f"\nConnected to {host}:{port}")

                return client

            except OSError:
                client.close()

        print("\nNo server available. Retrying in 3 seconds...")
        stop_event.wait(3)

    return None


def receive_messages():
    """Receive messages and reconnect when disconnected."""
    global current_socket

    while not stop_event.is_set():

        client = connect_to_server()

        if client is None:
            break

        try:
            file = client.makefile(
                "r",
                encoding="utf-8"
            )

            for message in file:

                if stop_event.is_set():
                    break

                print(f"\n{message.rstrip()}")
                print("You: ", end="", flush=True)

            if not stop_event.is_set():
                print("\nServer connection lost.")

        except (OSError, UnicodeError) as error:
            if not stop_event.is_set():
                print(f"\nConnection error: {error}")

        finally:
            with connection_lock:

                if current_socket is client:
                    current_socket = None
                    connected.clear()

            try:
                client.close()
            except OSError:
                pass

        if not stop_event.is_set():
            print("Looking for another server...")


def send_message(message):
    """Send a message using the active connection."""
    global current_socket

    with connection_lock:
        client = current_socket

        if client is None:
            return False

        try:
            client.sendall(
                (message + "\n").encode("utf-8")
            )

            return True

        except OSError:
            print("\nMessage could not be sent.")

            if current_socket is client:
                current_socket = None
                connected.clear()

            try:
                client.close()
            except OSError:
                pass

            return False


def start_client():
    """Start the DistributedChat client."""
    print("================================")
    print("      DistributedChat Client")
    print("================================")
    print("Type your messages below.")
    print("Type /quit to exit.\n")

    receiver = threading.Thread(
        target=receive_messages,
        daemon=True
    )

    receiver.start()

    try:
        while not stop_event.is_set():

            message = input("You: ").strip()

            if message.lower() == "/quit":
                break

            if not message:
                continue

            # Wait until a server is available
            if not connected.wait(timeout=30):
                print("No server connection available.")
                continue

            if not send_message(message):
                print("Message not sent. Reconnecting...")

    except (KeyboardInterrupt, EOFError):
        print("\nClosing client...")

    finally:
        stop_event.set()
        connected.set()

        with connection_lock:
            client = current_socket
            current_socket = None

        if client:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            client.close()

        print("Client closed.")


if __name__ == "__main__":
    start_client()
