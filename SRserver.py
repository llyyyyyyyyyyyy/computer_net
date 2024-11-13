
from abc import ABC, abstractmethod
import time
import control_class
import struct
import socket
import hashlib
import os
import PACKET
import time
BUFFER_SIZE = 1024 

class SRServer:
    
    BUFFER_SIZE = 1024
    def __init__(self, host, port, file_path_template,congestion_control):
        self.host = host
        self.port = port
        self.file_path_template = file_path_template
        self.congestion_control = congestion_control
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.window_size = 16  # 窗口大小设置为5，可以根据需要调整
        self.file_path = ''
        self.client_ip = ''
        self.client_port = 0
        self.total_data_sent = 0

    def receive_file(self):
        file_count = 0
        file_data = b''
        expected_seq_num = 0
        seq_num = 0
        print(f"Ready to receive file {file_count + 1}")

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
        file_path = self.file_path_template.format(file_count + 1)
        with open(file_path, 'wb') as f:
            f.write(file_data)

        # 计算文件的MD5并打印
        file_md5 = hashlib.md5(file_data).hexdigest()
        print(f"File {file_count + 1} received successfully. MD5: {file_md5}")
        file_count += 1
    
    def file_md5(self):
        hash_md5 = hashlib.md5()
        with open(self.file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def send_file(self,file_name):
        self.file_path = file_name
        file_size = os.path.getsize(self.file_path)
        start_time = time.time()
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
                    self.sock.sendto(packet.to_bytes(), (self.client_ip, self.client_port))
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
                        self.sock.sendto(packet.to_bytes(), (self.client_ip, self.client_port)) 
                        self.Retransmitted_data += len(packet.to_bytes())
                        print(f"Retransmitted packet with seq_num {packet.seq_num}")

        print(f"File uploaded successfully. MD5: {md5}")
        end_time = time.time()
        total_time = end_time - start_time
        self.log_results(file_size, total_time, md5)
        self.sock.close()

    def handle_client_request(self):
        """处理客户端请求包，判断操作类型并调用相应的操作"""
        while True:
            try:
                # 接收请求包，读取客户端的操作类型和文件名
                request, addr = self.sock.recvfrom(BUFFER_SIZE)
                self.client_ip,self.client_port =addr
                request = request.decode()
                print(f"Received request from {addr}: {request}")

                # 解析请求
                action, file_name = request.split(maxsplit=1)

                if action == "UPLOAD":
                    print(f"Starting to receive file: {file_name}")
                    self.sock.sendto(b"ACK", addr)
                    self.receive_file()


                elif action == "DOWNLOAD":
                    print(f"Starting to send file: {file_name}")
                    self.sock.sendto(b"ACK", addr)
                    self.send_file(file_name)

                else:
                    print(f"Invalid action: {action}")

            except Exception as e:
                print(f"Error handling client request: {e}")

    def log_results(self, file_size, total_time, file_md5):
        # 记录日志文件
        with open('log.txt', 'a') as log_file:
            log_file.write(f"File Size: {file_size} bytes\n")
            log_file.write(f"Total Data Sent: {self.total_data_sent} bytes\n")
            log_file.write(f"Retransmitted Data: {self.Retransmitted_data} bytes\n")
            log_file.write(f"Total Time: {total_time:.2f} seconds\n")
            log_file.write(f"MD5 Checksum: {file_md5}\n")
            log_file.write("\n")

if __name__ == "__main__":
    SERVER_IP = '192.168.188.1'
    SERVER_PORT = 12000
    FILE_PATH_TEMPLATE = 'file/received_file_{}.tar'
    congestion_control = control_class.LossBasedControl()
    server = SRServer(SERVER_IP, SERVER_PORT, FILE_PATH_TEMPLATE,congestion_control)
    server.handle_client_request()