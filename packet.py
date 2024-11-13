import struct
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
