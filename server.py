import struct
import socket
import hashlib

class Packet:
    HEADER_FORMAT = 'II16sH'  # 序号、文件大小、源IP（16 字节）、源端口（2 字节）

    def __init__(self, seq_num, file_size, src_ip, src_port, data):
        self.seq_num = seq_num
        self.file_size = file_size
        self.src_ip = src_ip.encode('utf-8')[:16]  # 限制源IP地址的长度为16个字节
        self.src_port = src_port
        self.data = data

    def to_bytes(self):
        """将数据包转换为字节格式，以便通过 socket 发送"""
        header = struct.pack(self.HEADER_FORMAT, self.seq_num, self.file_size, self.src_ip, self.src_port)
        return header + self.data

    @classmethod
    def from_bytes(cls, bytes_data):
        """从字节格式解析数据包"""
        header_size = struct.calcsize(cls.HEADER_FORMAT)
        seq_num, file_size, src_ip, src_port = struct.unpack(cls.HEADER_FORMAT, bytes_data[:header_size])
        data = bytes_data[header_size:]
        return cls(seq_num, file_size, src_ip.decode('utf-8').strip('\x00'), src_port, data)


class GBNServer:
    BUFFER_SIZE = 1024

    def __init__(self, host, port, file_path):
        self.host = host
        self.port = port
        self.file_path = file_path
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.client_connections = {}

    def receive_file(self):
        expected_seq_num = 0
        file_data = b''

        while True:
            print("start wait")
            packet, addr = self.sock.recvfrom(self.BUFFER_SIZE)
            if not packet:
                break

            data_packet = Packet.from_bytes(packet)
            seq_num = data_packet.seq_num
            src_ip = data_packet.src_ip
            src_port = data_packet.src_port
            file_size = data_packet.file_size  # 获取文件的总大小

            print(f"Received packet from {src_ip}:{src_port}, seq_num: {seq_num}")

            if seq_num == expected_seq_num:
                file_data += data_packet.data
                self.sock.sendto(struct.pack('I', seq_num), addr)  # 发送 ACK
                expected_seq_num += len(data_packet.data)

            elif seq_num > expected_seq_num:
                self.sock.sendto(struct.pack('I', expected_seq_num - 1), addr)  # 回应上一个包的 ACK

            # 判断文件是否接收完毕
            print(f"Received {len(file_data)} bytes")
            print(f"total data: {file_size}")

            if len(file_data) >= file_size:  # 判断已接收的数据大小是否大于等于文件总大小
                print("Received all data, stopping.")
                break

        # 保存文件并验证 MD5 校验
        with open(self.file_path, 'wb') as f:
            f.write(file_data)

        file_md5 = hashlib.md5(file_data).hexdigest()
        print(f"File received successfully. MD5: {file_md5}")
        self.sock.close()


# 服务器端主函数
if __name__ == "__main__":
    SERVER_IP = '10.117.40.1' 
    SERVER_PORT = 12000
    FILE_PATH = 'received_file.tar'

    server = GBNServer(SERVER_IP, SERVER_PORT, FILE_PATH)
    server.receive_file()
