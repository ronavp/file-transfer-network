import socket 
import json 
import time 
import sys
import os
from threading import Thread 

# Global Variables 
SERVER_IP = 'localhost'
keep_active = True

# Sends an authentication request to server
def send_auth_req(server_address, username, password, tcp_port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock: 
        data = json.dumps({'type': 'login', 'username': username, 'password': password, 'tcp_port': tcp_port})
        sock.sendto(data.encode(), server_address)
        response, _ = sock.recvfrom(1024)   
        return json.loads(response.decode())
    
# Sends hearbeats to server to indicate client is currently active
def send_heartbeat(server_address, username, udp_sock):
    global keep_active
    while keep_active:
        try:
            data = json.dumps({'type': 'heartbeat', 'username': username})
            udp_sock.sendto(data.encode(), server_address)
            time.sleep(2)
        except OSError:
            if not keep_active:
                break    

# Handles all the users command inputs with a dictionary
def client_commands(server_address, username):
    global keep_active
    keep_active = True
    
    commands = {
        "lap": list_active_peers,
        "lpf": list_published_files, 
        "pub": publish_file,
        "xit": exit_client, 
        "unp": unpublish_file,
        "sch": search_file,
        "get": get_file,
    }
    
    while keep_active: 
        command_input = input("> ")
        if not command_input: 
            continue
        
        command, *args = command_input.strip().split()
        # Checks for valid inputs for commands
        if command == "sch" and not args: 
            print("Please provide a substring to search")
            continue
        elif command == "pub" and not args: 
            print("Provide filename to publish")

        if command in commands: 
            try:
                commands[command](server_address, username, *args)
                if command == "xit":
                    break
            except TypeError:
                print(f"Invalid arguemnts were inputted '{command}'.")
            except Exception as e:
                print(f"Error with command selection {e}")

# Requests to list all the active peers in the server
def list_active_peers(server_address, username):
    data = json.dumps({'type': 'lap', 'username': username})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data.encode(), server_address)
    
    response, _ = sock.recvfrom(1024)
    response = json.loads(response.decode())
    
    if response['status'] == 'success':
        for user in response['users']:
            print(user)
    else: 
        print(response['message'])
    
# Sends a request to list all the published files by the current user 
def list_published_files(server_address, username):
    data = json.dumps({'type': 'lpf', 'username': username})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data.encode(), server_address)
    
    response, _ = sock.recvfrom(1024)
    response = json.loads(response.decode())
    
    if response['status'] == 'success':
        if response['files']:
            for file in response['files']:
                print(file)
        else: 
            print("No files published")
    else: 
        print(response['message'])

# Publishes a file to the server if it exists in cwd
def publish_file(server_address, username, filename):
    if not os.path.exists(filename):
        print(f"File does not exist in current working directory")
        return
    
    data = json.dumps({'type': 'pub', 'username': username, 'filename': filename})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data.encode(), server_address)
    
    response, _ = sock.recvfrom(1024)
    response = json.loads(response.decode())
    print(response['message'])
    
# Unpublishes the file from the server for the current user
def unpublish_file(server_address, username, filename):
    data = json.dumps({'type': 'unp', 'username': username, 'filename': filename})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data.encode(), server_address)
    response, _ = sock.recvfrom(1024)
    response = json.loads(response.decode())
    print(response['message'])
    
# Searches for files that are published with the substring
def search_file(server_address, username, substring):
    data = json.dumps({'type': 'sch', 'username': username, 'substring': substring})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data.encode(), server_address)
    response, _ = sock.recvfrom(1024)
    response = json.loads(response.decode())

    if response['status'] == 'success':
        for file in response['files']:
            print(file)
    else:
        print(response['message'])

# Requests and downloads a filet that is published by a user
def get_file(server_address, username, filename):
    data = json.dumps({'type': 'get', 'username': username, 'filename': filename})
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(data.encode(), server_address)
    response, _ = sock.recvfrom(1024)
    response = json.loads(response.decode())

    if response['status'] == 'success':
        download_file(response['peer_address'], response['peer_port'], filename)
    else:
        print(response['message'])      

# Downloads a file over TCP connection
def download_file(peer_address, peer_port, filename):
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        tcp_sock.connect((peer_address, peer_port))
        tcp_sock.sendall(f"GET {filename}".encode())
        
        with open(filename, 'wb') as file:
            while True:
                data = tcp_sock.recv(1024)
                if not data:
                    break
                file.write(data)
        print("File downloaded successfully.")
    except Exception as e:
        print(f"Failed to download the file: {e}")
    finally:
        tcp_sock.close()
    
# Exits to the client from the server
def exit_client(*args):
    global keep_active
    keep_active = False
    print("Goodbye!")  
    
# Runs the file server to handle any incoming file requests from active peers
def run_file_server(server_sock):
    while keep_active:
        try:
            client_sock, addr = server_sock.accept()
            handle_file_request(client_sock)
        except OSError: 
            if not keep_active:
                break
        except Exception as e:
            print("There was an error in the file server ", e)

# Runs the file requests between clients and sends file over
def handle_file_request(client_sock): 
    try:
        request = client_sock.recv(1024).decode()
        command , filename = request.split()
        if command == "GET":
            if os.path.exists(filename):
                with open(filename, 'rb') as file:
                    while True:
                        data = file.read(1024)
                        if not data:
                            break
                        client_sock.sendall(data)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_sock.close()
  
def main(server_ip, server_port):
    server_address = (server_ip, server_port) 
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while True:
        username = input("Enter your username: ")
        password = input("Enter your password: ")   
        
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(('', 0))  
        server_sock.listen(5)
        server_sock.settimeout(1)
        local_port = server_sock.getsockname()[1]
        
        auth_response = send_auth_req(server_address, username, password, local_port)
        print(auth_response['message'])
            
        if auth_response['status'] == 'success':
            break
    file_server_thread = Thread(target=run_file_server, args=(server_sock,))
    file_server_thread.start()
            
    print('Available commands are: get, lap, lpf, pub, sch, unp, xit')
    heartbeat_thread = Thread(target=send_heartbeat, args=(server_address, username, udp_sock))
    heartbeat_thread.start()
            
    try:
        client_commands(server_address, username)
    finally:
        keep_active = False
        # Close all threads before exiting
        server_sock.close()
        udp_sock.close()
        heartbeat_thread.join()
        file_server_thread.join()
        sys.exit(0)
    
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 client.py <port>")
        sys.exit(1)
        
    port = int(sys.argv[1])
    main(SERVER_IP, port)
