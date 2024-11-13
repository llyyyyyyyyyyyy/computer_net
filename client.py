import time
import os
import hashlib
import client_class
import control_class

SERVER_IP = '192.168.188.1'
SERVER_PORT = 12000

def file_md5(file_path):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def main():
    print("Simple FTP Client")
    print("Available commands: upload <file_path>, download <file_name>, quit")
    
    congestion_control = control_class.LossBasedControl()  # 可以根据需要切换不同的拥塞控制方式
    
    while True:
        client = client_class.GBNClient(SERVER_IP, SERVER_PORT, '',congestion_control)
        command = input("Enter command: ").strip().lower()

        if command.startswith('upload'):
            # 上传文件
            _, file_path = command.split(maxsplit=1)
            if os.path.exists(file_path):
                client.file_path = file_path
                client.send_file(file_path)
            else:
                print(f"File '{file_path}' does not exist.")
        
        elif command.startswith('download'):
            # 下载文件
            _, file_name = command.split(maxsplit=1)
            client.receive_file(file_name)

        elif command == 'quit':
            print("Exiting FTP client.")
            break
        
        else:
            print("Invalid command. Try 'upload <file_path>', 'download <file_name>', or 'quit'.")

if __name__ == "__main__":
    main()









