import re
import sys
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def parse_line(line):
    """
    从一行日志中提取信息：
      - datetime_str: "YYYY-MM-DD HH:MM:SS:mmm"
      - datetime: 对应的 datetime 对象（将最后一个冒号替换成小数点解析毫秒）
      - sec:          int, 日志中的秒数
      - operations:   int, 操作总数
      - current_ops:  float, 当前每秒操作数
      - avg_latency:  float, 平均延迟
    如果匹配失败则返回 None
    """
    # 如果包含 "CLEANUP"，则截断
    index = line.find("CLEANUP")
    if index != -1:
        line = line[:index]
    pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}:\d{3})\s+(\d+)\s+sec:\s+(\d+)\s+operations;\s+([\d\.]+)\s+current\s+ops/sec;.*Avg=([\d\.]+)'
    match = re.match(pattern, line.strip())
    if not match:
        return None

    datetime_str = match.group(1)   # 例如 "2025-01-28 12:15:22:029"
    sec_val      = int(match.group(2))
    operations   = int(match.group(3))
    current_ops  = float(match.group(4))
    avg_latency  = float(match.group(5))
    # 将最后一个冒号替换为点，方便解析毫秒
    datetime_mod = datetime_str[:-4] + "." + datetime_str[-3:]
    dt = datetime.strptime(datetime_mod, "%Y-%m-%d %H:%M:%S.%f")
    
    return {
        "datetime_str": datetime_str,
        "datetime": dt,
        "sec": sec_val,
        "operations": operations,
        "current_ops": current_ops,
        "avg_latency": avg_latency
    }

def parse_file(filepath):
    """
    读取文件并解析每一行，返回一个 DataFrame，包含以下列：
      - datetime_str, datetime, sec, current_ops, avg_latency
    """
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            parsed = parse_line(line)
            if parsed:
                data.append(parsed)
    df = pd.DataFrame(data)
    return df

def group_and_aggregate(df, group_interval):
    """
    按照 group_interval（单位秒）对 df 数据分组：
      - 'current_ops' 求和得到 ops_sec_sum
      - 'avg_latency' 求均值得到 latency_avg
    同时计算每个分组的起始 sec（group_index * group_interval）
    返回聚合后的 DataFrame
    """
    df['group_index'] = df['sec'] // group_interval
    grouped = df.groupby('group_index')
    result_df = pd.DataFrame()
    result_df['ops_sec_sum'] = grouped['current_ops'].sum()
    result_df['latency_avg'] = grouped['avg_latency'].mean()
    result_df.reset_index(inplace=True)
    result_df['sec'] = result_df['group_index'] * group_interval
    return result_df

def parse_syslog(filepath):
    """
    解析系统日志文件，提取每个区块的：
      - timestamp: 日志区块的时间戳（datetime 对象）
      - cpu_usage: 利用 avg-cpu 部分计算的 CPU 使用率（100 - idle）
      - disk_usage: 从 sda 行中提取的磁盘使用率（%util）
    返回一个 DataFrame，包含 timestamp, cpu_usage, disk_usage
    """
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 判断是否为区块起始行，形如 "===== Fri 31 Jan 2025 05:14:37 PM MST ====="
        if line.startswith("=====") and line.endswith("====="):
            # 提取区块头中的时间戳字符串
            timestamp_str = line.strip("= ").strip()
            try:
                ts = datetime.strptime(timestamp_str, "%a %d %b %Y %I:%M:%S %p %Z")
            except Exception as e:
                i += 1
                continue
            cpu_usage = None
            disk_usage = None

            # 寻找 "avg-cpu:" 行，并取其下一行数据
            while i < len(lines) and "avg-cpu:" not in lines[i]:
                i += 1
            if i < len(lines):
                i += 1  # 跳过 "avg-cpu:" 行
                while i < len(lines) and lines[i].strip() == "":
                    i += 1
                if i < len(lines):
                    cpu_line = lines[i].strip()
                    tokens = cpu_line.split()
                    if len(tokens) >= 6:
                        try:
                            idle = float(tokens[5])
                            cpu_usage = 100 - idle
                        except:
                            pass
            # 寻找 "Device" 行，跳过设备表头，取 sda 行
            while i < len(lines) and "Device" not in lines[i]:
                i += 1
            if i < len(lines):
                i += 1  # 跳过表头
                while i < len(lines):
                    disk_line = lines[i].strip()
                    if disk_line.startswith("sda"):
                        tokens = disk_line.split()
                        if tokens:
                            try:
                                # 假定最后一列为 %util（磁盘利用率）
                                disk_usage = float(tokens[-1])
                            except:
                                pass
                        break
                    i += 1
            if cpu_usage is not None and disk_usage is not None:
                records.append({
                    "timestamp": ts,
                    "cpu_usage": cpu_usage,
                    "disk_usage": disk_usage
                })
        else:
            i += 1
    return pd.DataFrame(records)

def plot_data(dfs, group_interval, filenames, outfile, sys_df_server1, sys_df_server2,
              exp_window_cache, exp_window_sqlite):
    """
    绘图，共4个子图：
      1) 操作日志：sec vs. ops_sec_sum（比较 cache 和 sqlite）
      2) 操作日志：sec vs. latency_avg（比较 cache 和 sqlite）
      3) 系统日志：CPU 使用率
      4) 系统日志：Disk 使用率

    系统日志部分要求每个图显示 4 条曲线：
      - cache 实验时 server1 和 server2 的使用率
      - sqlite 实验时 server1 和 server2 的使用率

    横轴均为“从各自实验开始经过的秒数”
    """
    # 分别取出 cache 和 sqlite 实验的时间窗口
    exp_start_cache, exp_end_cache = exp_window_cache
    exp_start_sqlite, exp_end_sqlite = exp_window_sqlite
    
    print(exp_start_sqlite)

    # 对系统日志数据按各自窗口过滤，并转换为相对于该实验开始的秒数
    sys_cache_s1 = sys_df_server1[(sys_df_server1['timestamp'] >= exp_start_cache) &
                                  (sys_df_server1['timestamp'] <= exp_end_cache)].copy()
    sys_cache_s2 = sys_df_server2[(sys_df_server2['timestamp'] >= exp_start_cache) &
                                  (sys_df_server2['timestamp'] <= exp_end_cache)].copy()
    sys_cache_s1['sec'] = sys_cache_s1['timestamp'].apply(lambda x: (x - exp_start_cache).total_seconds())
    sys_cache_s2['sec'] = sys_cache_s2['timestamp'].apply(lambda x: (x - exp_start_cache).total_seconds())

    sys_sqlite_s1 = sys_df_server1[(sys_df_server1['timestamp'] >= exp_start_sqlite) &
                                   (sys_df_server1['timestamp'] <= exp_end_sqlite)].copy()
    sys_sqlite_s2 = sys_df_server2[(sys_df_server2['timestamp'] >= exp_start_sqlite) &
                                   (sys_df_server2['timestamp'] <= exp_end_sqlite)].copy()
    sys_sqlite_s1['sec'] = sys_sqlite_s1['timestamp'].apply(lambda x: (x - exp_start_sqlite).total_seconds())
    sys_sqlite_s2['sec'] = sys_sqlite_s2['timestamp'].apply(lambda x: (x - exp_start_sqlite).total_seconds())

    # 创建 4 个子图（共用横轴，但注意各子图横轴的时域不一定重合）
    fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(10, 14))
    ax1, ax2, ax3, ax4 = axes

    # 子图1：操作日志中 aggregated throughput（current_ops 的总和）
    for df, fname in zip(dfs, filenames):
        ax1.plot(df['sec'], df['ops_sec_sum'], label=fname)
    ax1.set_title(f'Total Operations (grouped by {group_interval}s)')
    ax1.set_ylabel(f'Total Ops per {group_interval}s')
    ax1.legend()
    ax1.grid(True)

    # 子图2：操作日志中延迟的平均值
    for df, fname in zip(dfs, filenames):
        ax2.plot(df['sec'], df['latency_avg'], label=fname)
    ax2.set_title(f'Latency Average (grouped by {group_interval}s)')
    ax2.set_ylabel('Avg Latency (us)')
    ax2.legend()
    ax2.grid(True)

    # 子图3：CPU 使用率
    # 绘制四条曲线：cache-server1, cache-server2, sqlite-server1, sqlite-server2
    ax3.plot(sys_cache_s1['sec'], sys_cache_s1['cpu_usage'], label="Cache Storage Server CPU")
    ax3.plot(sys_cache_s2['sec'], sys_cache_s2['cpu_usage'], label="Cache Log Server CPU")
    ax3.plot(sys_sqlite_s1['sec'], sys_sqlite_s1['cpu_usage'], label="SQLite Storage Server CPU")
    ax3.plot(sys_sqlite_s2['sec'], sys_sqlite_s2['cpu_usage'], label="SQLite Log Server CPU")
    ax3.set_title("CPU Usage (%)")
    ax3.set_ylabel("CPU Usage (%)")
    ax3.legend()
    ax3.grid(True)

    # 子图4：Disk 使用率
    # 同样绘制四条曲线
    ax4.plot(sys_cache_s1['sec'], sys_cache_s1['disk_usage'], label="Cache Storage Server Disk")
    ax4.plot(sys_cache_s2['sec'], sys_cache_s2['disk_usage'], label="Cache Log Server Disk")
    ax4.plot(sys_sqlite_s1['sec'], sys_sqlite_s1['disk_usage'], label="SQLite Storage Server Disk")
    ax4.plot(sys_sqlite_s2['sec'], sys_sqlite_s2['disk_usage'], label="SQLite Log Server Disk")
    ax4.set_title("Disk Usage (%)")
    ax4.set_ylabel("Disk Usage (%)")
    ax4.set_xlabel("Seconds from Experiment Start")
    ax4.legend()
    ax4.grid(True)

    # 设置总标题
    if "scan" in outfile:
        fig.suptitle(f'{outfile} (1000keys per scan) Data(SQLite vs. Cache)', fontsize=14)
    else:
        fig.suptitle(f'{outfile} Data(SQLite vs. Cache)', fontsize=14)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(f"{outfile}.png")

def main(group_interval, datasize, operation, sys_df_server1, sys_df_server2):
    """
    对于给定的操作类型：
      1. 构造两个操作日志文件路径（cache 和 sqlite）
      2. 分别解析并聚合操作日志，同时记录各自的实验起始和结束时间
      3. 调用 plot_data 绘制 4 个子图：
           - 操作统计（吞吐量与延迟对比）
           - 系统日志（CPU 与 Disk 使用率，各包含 cache 和 sqlite 两个实验下 server1/server2 的数据）
    """
    # 构造操作日志文件路径（假定 cache 文件在前，sqlite 文件在后）
    filepaths = [
        f"./result/{datasize}_cache/{operation}.txt",
        f"./result/{datasize}_sqlite/{operation}.txt"
    ]
    
    raw_dfs = []
    grouped_dfs = []
    exp_windows = []  # 用于存储每个实验的 (start, end)
    for fp in filepaths:
        df = parse_file(fp)
        if df.empty:
            print(f"警告：文件 {fp} 没有解析到任何有效行！")
            continue
        raw_dfs.append(df)
        grouped_df = group_and_aggregate(df, group_interval)
        grouped_dfs.append(grouped_df)
        exp_start = df['datetime'].min()
        exp_end = df['datetime'].max()
        exp_windows.append((exp_start, exp_end))
    
    if len(grouped_dfs) < 2:
        print("缺少足够的有效数据，退出。")
        return

    # 假定第一个为 cache，第二个为 sqlite
    exp_window_cache = exp_windows[0]
    exp_window_sqlite = exp_windows[1]

    # 绘图：传入操作日志聚合数据、文件名、系统日志数据以及各实验的时间窗口
    plot_data(grouped_dfs, group_interval, filepaths, f"{datasize}_{operation}",
              sys_df_server1, sys_df_server2, exp_window_cache, exp_window_sqlite)

if __name__ == "__main__":
    """
    用法示例：
      python your_script.py <group_interval> <datasize> <syslog_server1.txt> <syslog_server2.txt>
      
    其中：
      - group_interval: 分组间隔（秒）
      - datasize: 数据集标识，用于构造操作日志文件路径
      - syslog_server1.txt, syslog_server2.txt: 两台服务器的系统日志
    """
    if len(sys.argv) < 5:
        print("用法: python your_script.py <group_interval> <datasize> <syslog_ss.txt> <syslog_log.txt>")
        sys.exit(1)
    group_interval = int(sys.argv[1])
    datasize = str(sys.argv[2])
    syslog_path_server1 = sys.argv[3]
    syslog_path_server2 = sys.argv[4]

    # 解析两台服务器的系统日志
    sys_df_server1 = parse_syslog(syslog_path_server1)
    sys_df_server2 = parse_syslog(syslog_path_server2)

    # 针对多种操作类型分别处理
    for op in ["insert", "read_uniform", "read_zipfian", "scan_uniform", "scan_zipfian"]:
        main(group_interval, datasize, op, sys_df_server1, sys_df_server2)
