
import server_class
if __name__ == "__main__":
    SERVER_IP = '192.168.11.1'
    SERVER_PORT = 12000
    FILE_PATH_TEMPLATE = 'file/received_file_{}.tar'

    server = server_class.SRServer(SERVER_IP, SERVER_PORT, FILE_PATH_TEMPLATE)
    server.receive_file()
