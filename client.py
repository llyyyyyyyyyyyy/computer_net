from abc import ABC, abstractmethod
import time
import os
import hashlib
import client_class

SERVER_IP = '47.251.161.108'
SERVER_PORT = 12000

def file_md5(file_path):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


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



def main():
    print("Simple FTP Client")
    print("Available commands: upload <file_path>, download <file_name>, quit")
    
    congestion_control = LossBasedControl()  # 可以根据需要切换不同的拥塞控制方式
    client = client_class.SRClient(SERVER_IP, SERVER_PORT, '',congestion_control)
    
    while True:
        command = input("Enter command: ").strip().lower()

        if command.startswith('upload'):
            # 上传文件
            _, file_path = command.split(maxsplit=1)
            if os.path.exists(file_path):
                client.file_path = file_path
                client.send_file()
            else:
                print(f"File '{file_path}' does not exist.")
        
        elif command.startswith('download'):
            # 下载文件
            _, file_name = command.split(maxsplit=1)
            client.download_file(file_name)

        elif command == 'quit':
            print("Exiting FTP client.")
            break
        
        else:
            print("Invalid command. Try 'upload <file_path>', 'download <file_name>', or 'quit'.")

if __name__ == "__main__":
    main()









