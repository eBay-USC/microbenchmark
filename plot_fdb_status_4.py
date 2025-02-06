import re
import sys
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def parse_line(line):
    """
    从一行操作日志中提取信息：
      - datetime_str: "YYYY-MM-DD HH:MM:SS:mmm"
      - datetime: 通过将最后一个冒号替换为小数点解析为 datetime 对象
      - sec:          操作日志中的秒数
      - operations:   操作总数
      - current_ops:  当前每秒操作数
      - avg_latency:  平均延迟
    如果匹配失败，则返回 None
    """
    # 如果包含 "CLEANUP"，则截断掉后面的部分
    index = line.find("CLEANUP")
    if index != -1:
        line = line[:index]
    pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}:\d{3})\s+(\d+)\s+sec:\s+(\d+)\s+operations;\s+([\d\.]+)\s+current\s+ops/sec;.*Avg=([\d\.]+)'
    match = re.match(pattern, line.strip())
    if not match:
        return None

    datetime_str = match.group(1)  # 例如 "2025-01-28 12:15:22:029"
    sec_val      = int(match.group(2))
    operations   = int(match.group(3))
    current_ops  = float(match.group(4))
    avg_latency  = float(match.group(5))
    # 将最后一个冒号替换为点，便于解析毫秒
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
    读取操作日志文件并解析每一行，返回 DataFrame，包含：
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
    按照 group_interval（单位秒）对操作日志数据分组：
      - 对 'current_ops' 求和，得到 ops_sec_sum
      - 对 'avg_latency' 求均值，得到 latency_avg
    同时增加列 sec = group_index * group_interval，表示该组的起始秒数
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

def read_system_json_files_for_interval(exp_start, exp_end, data_dir="/mydata"):
    """
    扫描 data_dir 目录下所有 JSON 文件，筛选出文件名所代表的时间在
    [exp_start, exp_end] 之间的文件，并从中提取系统监控数据。

    对于每个 JSON 文件：
      - 从文件名（格式：YYYYMMDDHHMMSS.json）解析出时间戳
      - 从 JSON 中读取 'cluster/processes' 数组，
          * 找到 "class_type"=="storage" 的进程，作为 server1，
            读取 "cpu/usage_cores" 和 "disk/busy"
          * 找到 "class_type"=="transaction" 的进程，作为 server2，
            同样读取 "cpu/usage_cores" 和 "disk/busy"
    返回一个 DataFrame，包含列：
      - timestamp (datetime 对象)
      - role ("server1" 或 "server2")
      - cpu_usage (0–1的 double 乘以 100 得到百分比)
      - disk_usage (0–1的 double 乘以 100 得到百分比)
    """
    records = []
    for filename in os.listdir(data_dir):
        if not filename.endswith(".json"):
            continue
        # 文件名形如 "20250201010920.json"
        basename = filename[:-5]
        try:
            ts = datetime.strptime(basename, "%Y%m%d%H%M%S")
        except Exception as e:
            continue
        # 筛选出时间在 [exp_start, exp_end] 内的文件
        if ts < exp_start or ts > exp_end:
            continue
        fullpath = os.path.join(data_dir, filename)
        try:
            with open(fullpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            continue
        processes = data.get("cluster", {}).get("processes", [])
        for proc_name in processes:
            
            # print(proc)
            proc = processes.get(proc_name)
            class_type = proc.get("class_type", "")
            # if class_type != "storage" and class_type != "transaction" and class_type != "stateless":
                # print(class_type)
            if class_type == "unset" and proc.get("cache_type") == "Cache":
                cpu_usage = proc.get("cpu", None).get("usage_cores", None)
                disk_busy = proc.get("disk", None).get("busy",None)
                if cpu_usage is not None and disk_busy is not None:
                    records.append({
                        "timestamp": ts,
                        "role": "SS",
                        "cpu_usage": cpu_usage * 100,   # 转换为百分比
                        "disk_usage": disk_busy * 100
                    })
            elif class_type == "storage":  # 作为 server1
                cpu_usage = proc.get("cpu", None).get("usage_cores", None)
                disk_busy = proc.get("disk", None).get("busy",None)
                if cpu_usage is not None and disk_busy is not None:
                    records.append({
                        "timestamp": ts,
                        "role": "SS",
                        "cpu_usage": cpu_usage * 100,   # 转换为百分比
                        "disk_usage": disk_busy * 100
                    })
            elif class_type == "transaction":  # 作为 server2
                cpu_usage = proc.get("cpu", None).get("usage_cores", None)
                disk_busy = proc.get("disk", None).get("busy",None)
                if cpu_usage is not None and disk_busy is not None:
                    records.append({
                        "timestamp": ts,
                        "role": "Log",
                        "cpu_usage": cpu_usage * 100,
                        "disk_usage": disk_busy * 100
                    })
                log_mem_used = proc.get("memory", None).get("used_bytes", None)
                log_queue_used = None
                for cur_role in proc.get("roles", None):
                    if cur_role["role"] == "log":
                        log_queue_used = cur_role["queue_disk_used_bytes"]
                if log_queue_used is not None and log_mem_used is not None:     
                    records.append({
                        "timestamp": ts,
                        "role": "Log_queue",
                        "cpu_usage": log_mem_used,
                        "disk_usage": log_queue_used
                    })
    df = pd.DataFrame(records)
    if not df.empty:
        df.sort_values("timestamp", inplace=True)
    return df

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

def plot_data(dfs, group_interval, filenames, outfile,
              sys_df_cache, sys_df_sqlite, exp_window_cache, exp_window_sqlite):
    """
    绘图，共 4 个子图：
      1) 操作日志：sec vs. ops_sec_sum（比较 cache 与 sqlite 的吞吐量）
      2) 操作日志：sec vs. latency_avg（比较 cache 与 sqlite 的延迟）
      3) 系统监控：CPU 使用率
      4) 系统监控：Disk 使用率

    系统监控部分要求每个子图显示四条曲线：
      - Cache 实验时：server1 和 server2 的数据
      - SQLite 实验时：server1 和 server2 的数据

    横轴均为“从实验开始经过的秒数”
    """
    # 分别取得 cache 和 sqlite 实验的起止时间
    exp_start_cache, exp_end_cache = exp_window_cache
    exp_start_sqlite, exp_end_sqlite = exp_window_sqlite
    

    # 对系统数据 DataFrame 添加相对于各自实验开始的秒数
    if not sys_df_cache.empty:
        sys_df_cache = sys_df_cache.copy()
        sys_df_cache['sec'] = sys_df_cache['timestamp'].apply(lambda x: (x - exp_start_cache).total_seconds())
    if not sys_df_sqlite.empty:
        sys_df_sqlite = sys_df_sqlite.copy()
        sys_df_sqlite['sec'] = sys_df_sqlite['timestamp'].apply(lambda x: (x - exp_start_sqlite).total_seconds())
    
    # 分别按 role 分离数据
    # print(sys_df_cache)
    sys_cache_server1 = sys_df_cache[sys_df_cache['role'] == "SS"]
    sys_cache_server2 = sys_df_cache[sys_df_cache['role'] == "Log"]
    sys_sqlite_server1 = sys_df_sqlite[sys_df_sqlite['role'] == "SS"]
    sys_sqlite_server2 = sys_df_sqlite[sys_df_sqlite['role'] == "Log"]
    
    # 创建 4 个子图
    fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(10, 16))
    ax1, ax2, ax3, ax4 = axes

    # 子图1：操作日志的吞吐量（current_ops 的总和）
    for df, fname in zip(dfs, filenames):
        ax1.plot(df['sec'], df['ops_sec_sum'], label=fname)
    ax1.set_title(f'Total Operations (grouped by {group_interval}s)')
    ax1.set_ylabel(f'Total Ops per {group_interval}s')
    ax1.legend()
    ax1.grid(True)

    # 子图2：操作日志的延迟平均值
    for df, fname in zip(dfs, filenames):
        ax2.plot(df['sec'], df['latency_avg'], label=fname)
    ax2.set_title(f'Latency Average (grouped by {group_interval}s)')
    ax2.set_ylabel('Avg Latency (us)')
    ax2.legend()
    ax2.grid(True)
    
    # 子图3：CPU 使用率 —— 绘制 4 条曲线
    ax3.plot(sys_cache_server1['sec'], sys_cache_server1['cpu_usage'], label="Cache SS CPU")
    ax3.plot(sys_cache_server2['sec'], sys_cache_server2['cpu_usage'], label="Cache Log CPU")
    ax3.plot(sys_sqlite_server1['sec'], sys_sqlite_server1['cpu_usage'], label="SQLite SS CPU")
    ax3.plot(sys_sqlite_server2['sec'], sys_sqlite_server2['cpu_usage'], label="SQLite Log CPU")
    ax3.set_title("CPU Usage (%)")
    ax3.set_ylabel("CPU Usage (%)")
    ax3.legend()
    ax3.grid(True)
    
    # 子图4：Disk 使用率 —— 绘制 4 条曲线
    ax4.plot(sys_cache_server1['sec'], sys_cache_server1['disk_usage'], label="Cache SS Disk")
    ax4.plot(sys_cache_server2['sec'], sys_cache_server2['disk_usage'], label="Cache Log Disk")
    ax4.plot(sys_sqlite_server1['sec'], sys_sqlite_server1['disk_usage'], label="SQLite SS Disk")
    ax4.plot(sys_sqlite_server2['sec'], sys_sqlite_server2['disk_usage'], label="SQLite Log Disk")
    ax4.set_title("Disk Usage (%)")
    ax4.set_ylabel("Disk Usage (%)")
    ax4.set_xlabel("Seconds from Experiment Start")
    ax4.legend()
    ax4.grid(True)
    
    if "scan" in outfile:
        fig.suptitle(f'{outfile} (1000keys per scan) Data(SQLite vs. Cache)', fontsize=14)
    else:
        fig.suptitle(f'{outfile} Data(SQLite vs. Cache)', fontsize=14)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(f"{outfile}.png")


def main(group_interval, datasize, operation, data_dir="/mydata"):
    """
    对于指定的操作类型：
      1. 构造两个操作日志文件路径（cache 与 sqlite）
      2. 分别解析并聚合操作日志，同时记录各自的实验起始和结束时间
      3. 根据各自的时间窗口，从 data_dir 目录下筛选 JSON 文件，提取系统监控数据
      4. 调用 plot_data 绘制 4 个子图：
           - 操作日志的吞吐量与延迟对比
           - 系统监控（CPU 与 Disk 使用率），每个子图显示四条曲线
    """
    # 构造操作日志文件路径（假设 cache 文件在前，sqlite 文件在后）
    filepaths = [
        f"./result/{datasize}_cache/{operation}.txt",
        f"./result/{datasize}_sqlite/{operation}.txt"
    ]
    
    raw_dfs = []
    grouped_dfs = []
    exp_windows = []  # 存储每个实验的 (start, end)
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

    # 假定第一个文件为 cache，第二个为 sqlite
    exp_window_cache = exp_windows[0]
    exp_window_sqlite = exp_windows[1]
    
    # 根据各自实验的时间窗口，从 JSON 文件中读取系统监控数据
    sys_df_cache = read_system_json_files_for_interval(exp_window_cache[0], exp_window_cache[1], data_dir=data_dir)
    sys_df_sqlite = read_system_json_files_for_interval(exp_window_sqlite[0], exp_window_sqlite[1], data_dir=data_dir)
    
    plot_data(grouped_dfs, group_interval, filepaths, f"{datasize}_{operation}",
              sys_df_cache, sys_df_sqlite, exp_window_cache, exp_window_sqlite)

if __name__ == "__main__":
    """
    用法示例：
      python your_script.py <group_interval> <datasize>
      
    其中：
      - group_interval: 分组间隔（秒）
      - datasize: 用于构造操作日志文件路径的标识
      - 系统监控数据默认从目录 /mydata 中读取（文件名格式如 20250201010920.json）
    """
    if len(sys.argv) < 3:
        print("用法: python your_script.py <group_interval> <datasize>")
        sys.exit(1)
    group_interval = int(sys.argv[1])
    datasize = sys.argv[2]
    # 系统监控数据所在目录（如有需要，可修改或通过参数传入）
    data_dir = "/mydata"
    
    # 针对多种操作类型分别生成图
    for op in ["insert", "read_uniform", "read_zipfian", "scan_uniform", "scan_zipfian"]:
        main(group_interval, datasize, op, data_dir=data_dir)
