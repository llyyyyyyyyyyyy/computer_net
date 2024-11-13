import struct
from abc import ABC, abstractmethod
import time
import socket
import os
import hashlib

SERVER_IP = '192.168.11.1'
SERVER_PORT = 12000
FILE_PATH = 'bomb2.tar'
TIMEOUT = 0.2
BUFFER_SIZE = 1024

def file_md5(file_path):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

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

class CongestionControl(ABC):
    def __init__(self):
        self.window_size = 1

    @abstractmethod
    def on_ack(self):
        pass

    @abstractmethod
    def on_timeout(self):
        pass

class DelayBasedControl(CongestionControl):
    def __init__(self):
        super().__init__()
        self.last_ack_time = time.time()

    def on_ack(self):
        current_time = time.time()
        rtt = current_time - self.last_ack_time
        self.last_ack_time = current_time
        if rtt < 0.1:  # 假设 0.1 秒以下表示网络稳定，增大窗口
            self.window_size = min(self.window_size + 1, 16)
        else:
            self.window_size = max(1, self.window_size // 2)

    def on_timeout(self):
        self.window_size = max(1, self.window_size // 2)

class GBNClient:
    BUFFER_SIZE = 1024  # 每个数据包的总大小

    def __init__(self, server_ip, server_port, file_path, congestion_control):
        self.server_ip = server_ip
        self.server_port = server_port
        self.file_path = file_path
        self.congestion_control = congestion_control
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(TIMEOUT)  # 设置超时
        self.total_data_sent = 0
        self.Retransmitted_data = 0


    def file_md5(self):
        hash_md5 = hashlib.md5()
        with open(self.file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def send_file(self):
        file_size = os.path.getsize(self.file_path)
        start_time = time.time()
        print("file_size")
        print(file_size)
        md5 = self.file_md5()
        self.sock.bind(('', 0)) 
        local_ip, local_port = self.sock.getsockname()
        with open(self.file_path, 'rb') as f:
            base_seq_num = 0
            unack_packets = {}  # 未确认的包
            while True: 
                # 窗口内发送数据
                while len(unack_packets) < self.congestion_control.window_size and base_seq_num < file_size:
                    data = f.read(self.BUFFER_SIZE - 28)
                    packet = Packet(base_seq_num, file_size, local_ip, local_port, data)
                    self.sock.sendto(packet.to_bytes(), (self.server_ip, self.server_port))
                    unack_packets[base_seq_num] = packet
                    base_seq_num += len(data)
                    self.total_data_sent += len(packet.to_bytes())
                    print(f"Sent packet with seq_num {packet.seq_num}")

                # 等待 ACK
                try:
                    ack, _ = self.sock.recvfrom(4)
                    ack_num = struct.unpack('I', ack)[0]
                    print(f"Received ACK for seq_num {ack_num}")
                    if(ack_num+BUFFER_SIZE>=file_size):break
                    if ack_num in unack_packets:
                        del unack_packets[ack_num]
                        self.congestion_control.on_ack()
                except socket.timeout: 
                    print("Timeout occurred, retransmitting all unacknowledged packets") 
                    self.congestion_control.on_timeout() # 重传所有未确认的包 
                    for seq in sorted(unack_packets.keys()): 
                        packet = unack_packets[seq] 
                        self.sock.sendto(packet.to_bytes(), (self.server_ip, self.server_port)) 
                        self.Retransmitted_data += len(packet.to_bytes())
                        print(f"Retransmitted packet with seq_num {packet.seq_num}")

        print(f"File uploaded successfully. MD5: {md5}")
        end_time = time.time()
        total_time = end_time - start_time
        self.log_results(file_size, total_time, md5)
        self.sock.close()

    def log_results(self, file_size, total_time, file_md5):
        # 记录日志文件
        with open('log.txt', 'a') as log_file:
            log_file.write(f"File Size: {file_size} bytes\n")
            log_file.write(f"Total Data Sent: {self.total_data_sent} bytes\n")
            log_file.write(f"Retransmitted Data: {self.Retransmitted_data} bytes\n")
            log_file.write(f"Total Time: {total_time:.2f} seconds\n")
            log_file.write(f"MD5 Checksum: {file_md5}\n")
            log_file.write("\n")
        print(f"File sent successfully. MD5: {file_md5}")
        self.sock.close()

class LossBasedControl(CongestionControl):
    def __init__(self):
        super().__init__()
        self.loss_threshold = 0.1  # 假设丢包率的阈值为10%
        self.loss_count = 0
        self.packet_count = 0

    def on_ack(self):
        self.packet_count += 1
        current_loss_rate = self.loss_count / max(1, self.packet_count)  # 避免除以零
        if current_loss_rate < self.loss_threshold:  # 丢包率低，增大窗口
            self.window_size = min(self.window_size + 1, 16)
        else:
            self.window_size = max(1, self.window_size // 2)
            self.loss_count = 0  # 重置丢包计数

    def on_timeout(self):
        self.loss_count += 1
        self.window_size = max(1, self.window_size // 2)

class SRClient:
    BUFFER_SIZE = 1024  # 每个数据包的总大小
    WINDOW_SIZE = 5  # 设置选择重传的窗口大小

    def __init__(self, server_ip, server_port, file_path, congestion_control):
        self.server_ip = server_ip
        self.server_port = server_port
        self.file_path = file_path
        self.congestion_control = congestion_control
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(TIMEOUT)  # 设置超时
        self.total_data_sent = 0
        self.Retransmitted_data = 0
        self.base = 0
        self.next_seq_num = 0
        self.window = {}  # 存储窗口内的包
        self.acked_packets = set()  # 已确认的包序号

    def send_file(self):
        file_size = os.path.getsize(self.file_path)
        start_time = time.time()
        print("file_size")
        print(file_size)
        md5 = file_md5(self.file_path)
        self.sock.bind(('', 0))
        local_ip, local_port = self.sock.getsockname()
        
        with open(self.file_path, 'rb') as f:
            while self.base < file_size:
                # 窗口内发送数据包
                while (self.next_seq_num < self.base + self.congestion_control.window_size * self.BUFFER_SIZE
                       and self.next_seq_num < file_size):
                    data = f.read(self.BUFFER_SIZE - 28)
                    packet = Packet(self.next_seq_num, file_size, local_ip, local_port, data)
                    self.sock.sendto(packet.to_bytes(), (self.server_ip, self.server_port))
                    self.window[self.next_seq_num] = packet
                    self.next_seq_num += len(data)
                    self.total_data_sent += len(packet.to_bytes())
                    print(f"Sent packet with seq_num {packet.seq_num}")

                try:
                    ack, _ = self.sock.recvfrom(4)
                    ack_num = struct.unpack('I', ack)[0]
                    print(f"Received ACK for seq_num {ack_num}")
                    self.base = ack_num + self.congestion_control.window_size*self.BUFFER_SIZE
                    for num in self.window:
                        if num < self.base and num != ack_num:
                            self.base = num
                    print(f"nwe self.base:{self.base}")
                    if ack_num in self.window:
                        self.acked_packets.add(ack_num)
                        self.congestion_control.on_ack()
                        del(self.window[ack_num])

                except socket.timeout:
                    print("Timeout occurred, selectively retransmitting packets")
                    self.congestion_control.on_timeout()
                    # 仅重传窗口内未确认的包
                    print(f"self.base:{self.base}")
                    for seq, packet in sorted(self.window.items()):
                        if seq not in self.acked_packets:
                            self.sock.sendto(packet.to_bytes(), (self.server_ip, self.server_port))
                            self.Retransmitted_data += len(packet.to_bytes())
                            print(f"Retransmitted packet with seq_num {packet.seq_num}")

        print(f"File uploaded successfully. MD5: {md5}")
        end_time = time.time()
        total_time = end_time - start_time
        self.log_results(file_size, total_time, md5)
        self.sock.close()

    def log_results(self, file_size, total_time, file_md5):
        # 记录日志文件
        with open('log.txt', 'a') as log_file:
            log_file.write(f"File Size: {file_size} bytes\n")
            log_file.write(f"Total Data Sent: {self.total_data_sent} bytes\n")
            log_file.write(f"Retransmitted Data: {self.Retransmitted_data} bytes\n")
            log_file.write(f"Total Time: {total_time:.2f} seconds\n")
            log_file.write(f"MD5 Checksum: {file_md5}\n")
            log_file.write("\n")
        print(f"File sent successfully. MD5: {file_md5}")

if __name__ == "__main__":

    # 使用延迟控制策略
    # congestion_control = DelayBasedControl()
    congestion_control = DelayBasedControl()
    client = SRClient(SERVER_IP, SERVER_PORT, FILE_PATH, congestion_control)
    client.send_file()
