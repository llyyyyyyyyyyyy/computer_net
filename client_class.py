import struct
from abc import ABC, abstractmethod
import time
import os
import hashlib
import socket
import PACKET

TIMEOUT = 0.2
BUFFER_SIZE = 1024
LOCAL_IP = '192.168.188.1'

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
        self.sock.bind((LOCAL_IP, 10000))
        self.sock.settimeout(TIMEOUT)  # 设置超时
        self.total_data_sent = 0
        self.Retransmitted_data = 0
        self.file_path_template = '/file'


    def file_md5(self):
        hash_md5 = hashlib.md5()
        with open(self.file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def send_file(self,file_name):
        file_size = os.path.getsize(self.file_path)
        start_time = time.time()
        ack = self.send_request(self.sock, "UPLOAD", file_name)
        if ack != b'ACK':
            print("Failed to get server acknowledgment. Exiting.")
            return
        print("file_size")
        print(file_size)
        md5 = self.file_md5()
        local_ip, local_port = self.sock.getsockname()
        with open(self.file_path, 'rb') as f:
            base_seq_num = 0
            unack_packets = {}  # 未确认的包
            while True: 
                # 窗口内发送数据
                while len(unack_packets) < self.congestion_control.window_size and base_seq_num < file_size:
                    data = f.read(self.BUFFER_SIZE - 28)
                    packet = PACKET.Packet(base_seq_num, file_size, local_ip, local_port, data)
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

    def receive_file(self,file_name):
        file_data = b''
        expected_seq_num = 0
        seq_num = 0
        ack = self.send_request(self.sock, "DOWNLOAD", file_name)
        if ack != b'ACK':
            print("Failed to get server acknowledgment. Exiting.")
            return
        print(f"Ready to receive file")

        # 用来存储接收到的包和未确认的包
        received_packets = {}  # key: seq_num, value: Packet对象
        acked_seq_nums = set()

        while True:
            packet, addr = self.sock.recvfrom(self.BUFFER_SIZE)
            if not packet:
                break

            data_packet = PACKET.Packet.from_bytes(packet)
            seq_num = data_packet.seq_num
            file_size = data_packet.file_size

            if seq_num not in acked_seq_nums:
                # 如果包是期望的序列号或者处于窗口内，接受包
                if seq_num == expected_seq_num:
                    # 顺序到达，立即写入数据并发送ACK
                    file_data += data_packet.data
                    acked_seq_nums.add(seq_num)
                    self.sock.sendto(struct.pack('I', seq_num), addr)
                    print(f"Received packet with seq_num {seq_num}")
                    expected_seq_num += len(data_packet.data)
                elif seq_num > expected_seq_num:
                    # 出现乱序包，记录在 received_packets 中
                    received_packets[seq_num] = data_packet
                    self.sock.sendto(struct.pack('I', seq_num), addr)
                    print(f"Out of order packet with seq_num {seq_num}")
                elif seq_num < expected_seq_num:
                    # 重复的包，直接发送ACK
                    self.sock.sendto(struct.pack('I', seq_num), addr)
                    print(f"Duplicate packet with seq_num {seq_num}, already received")

            # 窗口内处理已接收到的包
            while expected_seq_num in received_packets:
                data_packet = received_packets[expected_seq_num]
                file_data += data_packet.data
                acked_seq_nums.add(expected_seq_num)
                del received_packets[expected_seq_num]
                self.sock.sendto(struct.pack('I', expected_seq_num), addr)
                print(f"Received in-order packet with seq_num {expected_seq_num}")
                expected_seq_num += len(data_packet.data)

            # 当接收到完整文件时，跳出循环
            if len(file_data) >= file_size:
                break

        # 将接收到的文件保存到磁盘
        file_path = self.file_path_template.format(1)
        with open(file_path, 'wb') as f:
            f.write(file_data)

        # 计算文件的MD5并打印
        file_md5 = hashlib.md5(file_data).hexdigest()
        print(f"File received successfully. MD5: {file_md5}")
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

    def send_request(self,sock, action, file_name):
            """发送请求包给服务器，告诉服务器操作类型和文件名"""
            request = f"{action} {file_name}".encode()
            retries = 0

            while retries < 10:
                sock.sendto(request,(self.server_ip, self.server_port))
                try:
                    # 等待服务器的ACK确认
                    sock.settimeout(TIMEOUT)  
                    ack, _ = sock.recvfrom(BUFFER_SIZE)
                    return ack
                except socket.timeout:
                    print(f"Timeout occurred. Retrying... ({retries + 1})")
                    retries += 1
            
            # 如果超出了重试次数，返回 None 表示失败
            print("Max retries reached. Server did not respond.")
            return None

    

class SRClient:
    BUFFER_SIZE = 1024  # 每个数据包的总大小
    WINDOW_SIZE = 5  # 设置选择重传的窗口大小

    def __init__(self, server_ip, server_port, file_path, congestion_control):
        self.server_ip = server_ip
        self.server_port = server_port
        self.file_path = file_path
        self.congestion_control = congestion_control
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((LOCAL_IP, 10000))
        self.sock.settimeout(TIMEOUT)  # 设置超时
        self.total_data_sent = 0
        self.Retransmitted_data = 0
        self.base = 0
        self.next_seq_num = 0
        self.window = {}  # 存储窗口内的包
        self.acked_packets = set()  # 已确认的包序号
        self.file_path_template = '/file'

    def send_file(self,file_name):
        file_size = os.path.getsize(self.file_path)
        start_time = time.time()
        ack = self.send_request(self.sock, "UPLOAD", file_name)
        if ack != b'ACK':
            print("Failed to get server acknowledgment. Exiting.")
            return
        print("file_size")
        print(file_size)
        md5 = file_md5(self.file_path)
        
        local_ip, local_port = self.sock.getsockname()
        
        with open(self.file_path, 'rb') as f:
            while self.base < file_size:
                # 窗口内发送数据包
                while (self.next_seq_num < self.base + self.congestion_control.window_size * self.BUFFER_SIZE
                       and self.next_seq_num < file_size):
                    data = f.read(self.BUFFER_SIZE - 28)
                    packet = PACKET.Packet(self.next_seq_num, file_size, local_ip, local_port, data)
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

    def receive_file(self,file_name):
        file_data = b''
        expected_seq_num = 0
        seq_num = 0
        ack = self.send_request(self.sock, "DOWNLOAD", file_name)
        if ack != b'ACK':
            print("Failed to get server acknowledgment. Exiting.")
            return
        print(f"Ready to receive file")
        # 用来存储接收到的包和未确认的包
        received_packets = {}  # key: seq_num, value: Packet对象
        acked_seq_nums = set()

        while True:
            packet, addr = self.sock.recvfrom(self.BUFFER_SIZE)
            if not packet:
                break

            data_packet = PACKET.Packet.from_bytes(packet)
            seq_num = data_packet.seq_num
            file_size = data_packet.file_size

            if seq_num not in acked_seq_nums:
                # 如果包是期望的序列号或者处于窗口内，接受包
                if seq_num == expected_seq_num:
                    # 顺序到达，立即写入数据并发送ACK
                    file_data += data_packet.data
                    acked_seq_nums.add(seq_num)
                    self.sock.sendto(struct.pack('I', seq_num), addr)
                    print(f"Received packet with seq_num {seq_num}")
                    expected_seq_num += len(data_packet.data)
                elif seq_num > expected_seq_num:
                    # 出现乱序包，记录在 received_packets 中
                    received_packets[seq_num] = data_packet
                    self.sock.sendto(struct.pack('I', seq_num), addr)
                    print(f"Out of order packet with seq_num {seq_num}")
                elif seq_num < expected_seq_num:
                    # 重复的包，直接发送ACK
                    self.sock.sendto(struct.pack('I', seq_num), addr)
                    print(f"Duplicate packet with seq_num {seq_num}, already received")

            # 窗口内处理已接收到的包
            while expected_seq_num in received_packets:
                data_packet = received_packets[expected_seq_num]
                file_data += data_packet.data
                acked_seq_nums.add(expected_seq_num)
                del received_packets[expected_seq_num]
                self.sock.sendto(struct.pack('I', expected_seq_num), addr)
                print(f"Received in-order packet with seq_num {expected_seq_num}")
                expected_seq_num += len(data_packet.data)

            # 当接收到完整文件时，跳出循环
            if len(file_data) >= file_size:
                break

        # 将接收到的文件保存到磁盘
        file_path = self.file_path_template.format(1)
        with open(file_path, 'wb') as f:
            f.write(file_data)

        # 计算文件的MD5并打印
        file_md5 = hashlib.md5(file_data).hexdigest()
        print(f"File received successfully. MD5: {file_md5}")
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


    def send_request(self,sock, action, file_name):
            """发送请求包给服务器，告诉服务器操作类型和文件名"""
            request = f"{action} {file_name}".encode()
            retries = 0

            while retries < 10:
                sock.sendto(request,(self.server_ip, self.server_port))
                try:
                    # 等待服务器的ACK确认
                    sock.settimeout(TIMEOUT)  # 设置超时
                    ack, _ = sock.recvfrom(BUFFER_SIZE)
                    return ack  # 如果收到ACK则返回
                except socket.timeout:
                    print(f"Timeout occurred. Retrying... ({retries + 1})")
                    retries += 1
            
            # 如果超出了重试次数，返回 None 表示失败
            print("Max retries reached. Server did not respond.")
            return None