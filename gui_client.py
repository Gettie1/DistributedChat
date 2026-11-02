
import socket
import threading
import tkinter as tk
from tkinter import scrolledtext
from queue import Queue, Empty

# Server nodes: Node 1 is tried first, then Node 2.
SERVERS = [
    ("127.0.0.1", 5000),
    ("127.0.0.1", 5001),
]

current_socket = None
current_server = None

connection_lock = threading.Lock()
messages_queue = Queue()
stop_event = threading.Event()


# -------------------- CONNECTION --------------------

def connect_to_server():
    """Try the server nodes until a connection succeeds."""
    global current_socket, current_server

    while not stop_event.is_set():
        for server in SERVERS:
            if stop_event.is_set():
                return

            host, port = server

            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.settimeout(3)
                client.connect((host, port))
                client.settimeout(None)

                with connection_lock:
                    current_socket = client
                    current_server = server

                messages_queue.put(("status", f"Connected to Node {SERVERS.index(server) + 1}"))
                messages_queue.put(("system", "Connection established."))

                receive_messages(client)
                return

            except OSError:
                try:
                    client.close()
                except (OSError, UnboundLocalError):
                    pass

        if not stop_event.is_set():
            messages_queue.put(("status", "Reconnecting..."))
            messages_queue.put(("system", "Servers unavailable. Retrying..."))
            stop_event.wait(2)


def receive_messages(client):
    """Receive messages from the connected server."""
    global current_socket, current_server

    try:
        reader = client.makefile("r", encoding="utf-8")

        for message in reader:
            if stop_event.is_set():
                break

            message = message.rstrip("\n")
            if message:
                messages_queue.put(("message", message))

    except (OSError, UnicodeError):
        pass

    finally:
        try:
            client.close()
        except OSError:
            pass

        with connection_lock:
            if current_socket is client:
                current_socket = None
                current_server = None

        if not stop_event.is_set():
            messages_queue.put(("status", "Reconnecting..."))
            messages_queue.put(("system", "Connection lost. Trying another server..."))
            connect_to_server()


# -------------------- SEND MESSAGE --------------------

def send_message(event=None):
    """Send the text in the message input box."""
    global current_socket

    message = message_input.get().strip()

    if not message:
        return

    if message.lower() == "/quit":
        close_app()
        return

    with connection_lock:
        client = current_socket

    if client is None:
        messages_queue.put(("system", "Not connected. Please wait for reconnection."))
        return

    try:
        client.sendall((message + "\n").encode("utf-8"))
        messages_queue.put(("sent", message))
        message_input.delete(0, tk.END)

    except OSError:
        messages_queue.put(("system", "Message could not be sent. Reconnecting..."))

        with connection_lock:
            if current_socket is client:
                current_socket = None

        try:
            client.close()
        except OSError:
            pass


# -------------------- UI --------------------

def add_message(message, message_type="message"):
    """Display a message in the chat window."""
    chat_display.configure(state="normal")

    if message_type == "sent":
        chat_display.insert(tk.END, f"You: {message}\n", "sent")

    elif message_type == "system":
        chat_display.insert(tk.END, f"{message}\n", "system")

    else:
        chat_display.insert(tk.END, f"{message}\n", "received")

    chat_display.see(tk.END)
    chat_display.configure(state="disabled")


def process_queue():
    """Update the UI using messages received from background threads."""
    try:
        while True:
            message_type, message = messages_queue.get_nowait()

            if message_type == "status":
                status_label.config(text=message)

                if message.startswith("Connected"):
                    status_label.config(fg="#15803d")
                else:
                    status_label.config(fg="#b45309")

            else:
                add_message(message, message_type)

    except Empty:
        pass

    if not stop_event.is_set():
        root.after(100, process_queue)


def close_app():
    """Close the GUI and socket connection."""
    stop_event.set()

    with connection_lock:
        client = current_socket

    if client is not None:
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        try:
            client.close()
        except OSError:
            pass

    root.destroy()


# -------------------- WINDOW --------------------

root = tk.Tk()
root.title("Distributed Chat Application")
root.geometry("650x600")
root.minsize(500, 450)
root.configure(bg="#f1f5f9")

# Header
header = tk.Frame(root, bg="#1e293b", padx=16, pady=14)
header.pack(fill="x")

title_label = tk.Label(
    header,
    text="Distributed Chat",
    font=("Segoe UI", 18, "bold"),
    fg="white",
    bg="#1e293b",
)
title_label.pack(anchor="w")

status_label = tk.Label(
    header,
    text="Connecting...",
    font=("Segoe UI", 10),
    fg="#b45309",
    bg="#1e293b",
)
status_label.pack(anchor="w", pady=(4, 0))

# Chat display
chat_display = scrolledtext.ScrolledText(
    root,
    wrap=tk.WORD,
    font=("Segoe UI", 11),
    bg="white",
    fg="#0f172a",
    padx=12,
    pady=12,
    state="disabled",
)
chat_display.pack(fill="both", expand=True, padx=14, pady=14)

chat_display.tag_config("sent", foreground="#2563eb")
chat_display.tag_config("received", foreground="#0f172a")
chat_display.tag_config("system", foreground="#64748b")

# Input area
input_frame = tk.Frame(root, bg="#f1f5f9", padx=14, pady=(0, 14))
input_frame.pack(fill="x")

message_input = tk.Entry(
    input_frame,
    font=("Segoe UI", 11),
    relief="solid",
    bd=1,
)
message_input.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 8))
message_input.bind("<Return>", send_message)

send_button = tk.Button(
    input_frame,
    text="Send",
    command=send_message,
    font=("Segoe UI", 10, "bold"),
    bg="#2563eb",
    fg="white",
    activebackground="#1d4ed8",
    activeforeground="white",
    relief="flat",
    padx=18,
    pady=8,
)
send_button.pack(side="right")

# Start the connection in a background thread.
threading.Thread(target=connect_to_server, daemon=True).start()

# Process messages on the Tkinter UI thread.
root.after(100, process_queue)

root.protocol("WM_DELETE_WINDOW", close_app)
message_input.focus()

root.mainloop()
