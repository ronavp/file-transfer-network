import socket 
import json
import sys
from datetime import datetime 

# Global Variables 
TIMEOUT_INTERVAL = 3 

# Outputs events that occurs in server terminal using a timestamp
def log_event(event):
    time = datetime.now()
    time_format = time.strftime("%H:%M:%S.%f")[:-3]
    print(f"{time_format}: {event}")

# Stores users details into dictionary
def load_credentials():
    credentials = {}
    with open('credentials.txt', 'r') as file: 
        for line in file: 
            username, password = line.strip().split()
            credentials[username] = password
    return credentials

# Removes inactive users usings the heartbeats sent
def load_inactive(active_users):         
    current_time = datetime.now()
    inactive_user = [user for user, details in active_users.items() 
                        if (current_time - details['last_seen']).total_seconds() > TIMEOUT_INTERVAL]
    for user in inactive_user:
        del active_users[user]
    
# Updates the timestamp to check if the user is active or not
def update_last_seen(active_users, username):
    if username in active_users:
        active_users[username]['last_seen'] = datetime.now()
        
# Check if user is valid in credentials dictionary ands stores its tcp port
def auth_user(data, credentials, active_users, client_ip):
    username = data.get('username')
    password = data.get('password')
    tcp_port = data.get('tcp_port')
    log_event(f"Received AUTH from {username}")

    if username in credentials and password == credentials[username]:
        if username not in active_users: 
            active_users[username] = {
                    'last_seen': datetime.now(), 
                    'tcp_port': tcp_port,
                    'address': client_ip,
                }
            log_event(f"Sent OK to {username}")
            return {'status': 'success', 'message': 'Welcome to BitTrickle!'}
        else: 
            update_last_seen(active_users, username)
            return {'status': 'fail', 'message': 'Authentication failed. You are already logged in.'}
    else:
        log_event(f"Sent ERR to {username}")
        return {'status': 'fail', 'message': 'Authentication failed. Please try again.'}
            
# Handles all requests for each command on a specified port
def server_main(port): 
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('localhost', port))
    credentials = load_credentials()
    published_files = {}
    active_users = {}
    
    print(f"Server is listening on port {port}...")
    
    while True: 
        load_inactive(active_users)
        data, address = server_socket.recvfrom(1024)
        data = json.loads(data.decode('utf-8'))
        username = data.get('username')
        tcp_port = data.get('tcp_port', None)
        
        client_ip, client_src_port = address
        # Authenticates user if it is a login
        if data['type'] == 'login':
            response = auth_user(data, credentials, active_users, client_ip)
        # Listing Published Files
        elif data['type'] == 'lpf':
            log_event(f"Received LPF from {username}")
            if published_files:
                user_files = [filename for filename, owner in published_files.items() if owner == username]
                update_last_seen(active_users, username)
                response = {'status': 'success', 'message': 'Files Listed.', 'files': user_files}
            else: 
                response = {'status': 'fail', 'message': 'No files published'}
        # Listing Active peers
        elif data['type'] == 'lap':
            log_event(f"Received LAP from {username}")
            active_peers = []
            for user in active_users:
                if user != data['username']:
                    active_peers.append(user)

            if active_peers:
                update_last_seen(active_users, username)
                response = {'status': 'success', 'message': 'Active users listed.', 'users': active_peers}
            else:
                response = {'status': 'fail', 'message': 'No active peers'}
        # Publishes file to the server
        elif data['type'] == 'pub':
            username = data.get('username')
            filename = data.get('filename', None)
            if filename: 
                published_files[filename] = username
                response = {'status': 'success', 'message': 'File published successfully'}
                update_last_seen(active_users, username)
                log_event(f"Received PUB from {username}")
            else: 
                response = {'status': 'success', 'message': 'File publish was unsuccessful'}
        # Unpublishes a file from the server
        elif data['type'] == 'unp':
            filename = data.get('filename', None)
            if filename and filename in published_files:
                if published_files[filename] == username:
                    del published_files[filename]
                    update_last_seen(active_users, username)
                    response = {'status': 'success', 'message': 'File unpublished successfully'}
                    log_event(f"Received UNP from {username}")
                else: 
                    response = {'status': 'fail', 'message': 'File cannot be unpublished as you are not the publisher of the file.'}
            else: 
                response = {'status': 'fail', 'message': 'No files published with that filename'}
        # Searches published files with provided substring
        elif data['type'] == 'sch':
            substr = data.get('substring')
            username = data.get('username')
            log_event(f"Received SCH from {username}")
            matching_files = [file for file,owner in published_files.items() if substr in file and owner != username]
            
            if matching_files:
                update_last_seen(active_users, username)
                response = {'status': 'success', 'message': 'Matching files found.', 'files': matching_files}
            else:
                response = {'status': 'fail', 'message': 'No matching files found.'}
        # Gets and downloads the file inputted
        elif data['type'] == 'get':
            filename = data.get('filename')
            username = data.get('username')
            
            # Check filename is published and the owner is active
            if filename in published_files:
                owner = published_files[filename]
                if owner in active_users and 'tcp_port' in active_users[owner]:
                    log_event(f"Received GET from {username}")
                    update_last_seen(active_users, username)
                    owner_data = active_users[owner]
                    response = {
                        'status': 'success', 
                        'peer_address': owner_data['address'], 
                        'peer_port': owner_data['tcp_port'],
                    }
                else:
                    response = {'status': 'fail', 'message': 'File owner is not active'}
            else:
                response = {'status': 'fail', 'message': 'File not found'}
    
        # Sends heartbearts to server
        elif data['type'] =='heartbeat':
            log_event(f"Received HBT from {username}")
            if username in active_users:
                update_last_seen(active_users, username)
                response = {'status': 'success', 'message': 'Hearbeat received'}
            else:
                log_event(f"Sent ERR to {username}")
                print(f"Heartbeat received from unknown user {username}")
                response = {'status': 'fail', 'message': 'Unknown user'}
            
        server_socket.sendto(json.dumps(response).encode('utf-8'), address)
        
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 server.py <port>")
        sys.exit(1)
    port = int(sys.argv[1])
    server_main(port)