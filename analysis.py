import matplotlib.pyplot as plt
import re

# 读取log.txt并解析数据
def parse_log(file_path):
    data = {'delay': [], 'loss': []}  # 两组测试数据
    with open(file_path, 'r') as f:
        log_content = f.read()
        entries = re.findall(r"File Size: (\d+) bytes.*?Total Data Sent: (\d+) bytes.*?Retransmitted Data: (\d+) bytes.*?Total Time: ([\d.]+) seconds", log_content, re.DOTALL)
        
        for idx, entry in enumerate(entries):
            file_size, total_data_sent, retransmitted_data, total_time = map(float, entry)
            throughput = file_size / total_time
            efficiency = file_size / (total_data_sent+retransmitted_data)
            if idx < 6:  # 前4条记录为延迟测试
                data['delay'].append((throughput, efficiency))
            else:  # 后4条记录为丢包测试
                data['loss'].append((throughput, efficiency))
                
    return data

# 绘制图表
def plot_results(data):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    # 绘制有效吞吐量随测试编号变化的图
    ax1.plot([10, 20, 30, 40, 50, 60], [t[0] for t in data['delay']], 'o-', label='LOSS')
    ax1.plot([10, 20, 30, 40, 50, 60], [t[0] for t in data['loss']], 's-', label='DELAY')
    ax1.set_xlabel('Loss rate')
    ax1.set_ylabel('Throughput (bytes/second)')
    ax1.set_title('Throughput vs. Test Number')
    ax1.legend()

    # 绘制流量利用率随测试编号变化的图
    ax2.plot([10, 20, 30, 40, 50, 60], [t[1] for t in data['delay']], 'o-', label='LOSS')
    ax2.plot([10, 20, 30, 40, 50, 60], [t[1] for t in data['loss']], 's-', label='DELAY')
    ax2.set_xlabel('Loss rate')
    ax2.set_ylabel('Traffic Efficiency')
    ax2.set_title('Traffic Efficiency vs. Test Number')
    ax2.legend()

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    log_data = parse_log('log.txt')
    plot_results(log_data)
