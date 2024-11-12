import re

def parse_log(file_path):
    results = []
    with open(file_path, 'r') as file:
        current_result = {}
        for line in file:
            if "File Size" in line:
                current_result["file_size"] = int(re.search(r'\d+', line).group())
            elif "Total Data Sent" in line:
                current_result["total_data_sent"] = int(re.search(r'\d+', line).group())
            elif "Retransmitted Data" in line:
                current_result["retransmitted_data"] = int(re.search(r'\d+', line).group())
            elif "Total Time" in line:
                current_result["total_time"] = float(re.search(r'[\d.]+', line).group())
            elif "MD5 Checksum" in line:
                # 当所有数据已收集完，保存当前结果并开始新的记录
                results.append(current_result)
                current_result = {}
    return results

def calculate_metrics(results):
    metrics = []
    for result in results:
        file_size = result["file_size"]
        total_time = result["total_time"]
        total_data_sent = result["total_data_sent"]
        retransmitted_data = result["retransmitted_data"]

        throughput = file_size / total_time
        utilization = file_size / (total_data_sent + retransmitted_data)
        
        metrics.append({
            "throughput": throughput,
            "utilization": utilization,
            "total_time": total_time
        })
    return metrics

def display_metrics(metrics):
    for i, metric in enumerate(metrics, 1):
        print(f"Test {i}:")
        print(f"  Throughput: {metric['throughput']:.2f} bytes/second")
        print(f"  Utilization: {metric['utilization']:.2%}")
        print(f"  Total Time: {metric['total_time']:.2f} seconds\n")

if __name__ == "__main__":
    log_file_path = 'log.txt'
    results = parse_log(log_file_path)
    metrics = calculate_metrics(results)
    display_metrics(metrics)
