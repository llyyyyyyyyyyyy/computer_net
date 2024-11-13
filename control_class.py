from abc import ABC, abstractmethod
import time
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
        if rtt < 0.1:  
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