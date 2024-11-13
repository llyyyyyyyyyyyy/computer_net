import struct
import socket
import hashlib

class Packet:
    HEADER_FORMAT = 'II16sH'

    def __init__(self, seq_num, file_size, src_ip, src_port, data):
        self.seq_num = seq_num
        self.file_size = file_size
        self.src_ip = src_ip.encode('utf-8')[:16]
        self.src_port = src_port
        self.data = data

    def to_bytes(self):
        header = struct.pack(self.HEADER_FORMAT, self.seq_num, self.file_size, self.src_ip, self.src_port)
        return header + self.data

    @classmethod
    def from_bytes(cls, bytes_data):
        header_size = struct.calcsize(cls.HEADER_FORMAT)
        seq_num, file_size, src_ip, src_port = struct.unpack(cls.HEADER_FORMAT, bytes_data[:header_size])
        data = bytes_data[header_size:]
        return cls(seq_num, file_size, src_ip.decode('utf-8').strip('\x00'), src_port, data)


class GBNServer:
    BUFFER_SIZE = 1024

    def __init__(self, host, port, file_path_template):
        self.host = host
        self.port = port
        self.file_path_template = file_path_template
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))

    def receive_file(self):
        file_count = 0
        while True:
            file_data = b''
            expected_seq_num = 0
            seq_num = 0
            print(f"Ready to receive file {file_count + 1}")
            
            while True:
                packet, addr = self.sock.recvfrom(self.BUFFER_SIZE)
                if not packet:
                    break

                data_packet = Packet.from_bytes(packet)
                seq_num = data_packet.seq_num
                file_size = data_packet.file_size

                if seq_num == expected_seq_num:
                    file_data += data_packet.data
                    self.sock.sendto(struct.pack('I', seq_num), addr)
                    expected_seq_num += len(data_packet.data)
                elif seq_num > expected_seq_num:
                    self.sock.sendto(struct.pack('I', expected_seq_num - 1), addr)

                if len(file_data) >= file_size:
                    break

            file_path = self.file_path_template.format(file_count + 1)
            with open(file_path, 'wb') as f:
                f.write(file_data)

            file_md5 = hashlib.md5(file_data).hexdigest()
            print(f"File {file_count + 1} received successfully. MD5: {file_md5}")
            file_count += 1


if __name__ == "__main__":
    SERVER_IP = '192.168.11.1'
    SERVER_PORT = 12000
    FILE_PATH_TEMPLATE = 'file/received_file_{}.tar'

    server = GBNServer(SERVER_IP, SERVER_PORT, FILE_PATH_TEMPLATE)
    server.receive_file()
