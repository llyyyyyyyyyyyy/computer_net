import struct
import socket
import hashlib
import os
import packet

class SRServer:
    BUFFER_SIZE = 1024  # 每个数据包的总大小

    def __init__(self, host, port, file_path_template):
        self.host = host
        self.port = port
        self.file_path_template = file_path_template
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        self.window_size = 5  # 窗口大小设置为5，可以根据需要调整

    def receive_file(self):
        file_count = 0
        while True:
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

                data_packet = packet.Packet.from_bytes(packet)
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