import struct
from abc import ABC, abstractmethod
import time
import os
import hashlib
import socket
import packet


TIMEOUT = 0.2
BUFFER_SIZE = 1024

def file_md5(file_path):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

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
                    packet = packet.Packet(base_seq_num, file_size, local_ip, local_port, data)
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
                    packet = packet.Packet(self.next_seq_num, file_size, local_ip, local_port, data)
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