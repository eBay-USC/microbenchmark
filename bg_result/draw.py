import glob
import csv
import os
from datetime import datetime
import matplotlib.pyplot as plt
import re

# 你可以根据自己的指标名称，定义一个映射：图表标题 -> 对应子文件夹名
FOLDER_MAP = {
    "CPU Usage (%)": "CPU_plots",
    "Memory Usage (%)": "MEM_plots",
    "Total NETWORK Received and transmit (KB)": "NET_plots",
    "Fdb-network-thr threads Usage (%)": "Fdb_network_thr_plots",
    "FDB Space Used (%)": "FDB_Used_plots",
    "FDB Space Read (MB)": "FDB_Read_plots",
    "FDB Space Write (MB)": "FDB_Write_plots",
    "Hz": "Hz"
}


def parse_float_safe(val):
    """尝试把字符串转成float；如果不行则返回None。"""
    try:
        return float(val)
    except:
        return None


def parse_time(timestr):
    """
    解析形如 '2025-04-09 22:25:46' 的时间字符串为 datetime 对象。
    如果解析失败，则返回None。
    """
    try:
        return datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S")
    except:
        return None


def make_plot(x_values, y_values, title, base_name, dir):
    """
    用 matplotlib 绘制单独的折线图，并保存成 png 文件。
    - x_values, y_values: 数据
    - title: 图表标题 (如 "CPU Usage")
    - base_name: csv 文件名去掉后缀后的部分，用于拼接输出文件名

    不同指标要分别保存在对应的子目录下 (按 FOLDER_MAP).
    """
    if not x_values or not y_values or all(v is None for v in y_values):
        print(f"[WARN] No valid data to plot for {title} in {base_name}, skip.")
        return

    # 获取或默认子文件夹
    subfolder = dir + '/' + FOLDER_MAP.get(title, "Other_plots")
    os.makedirs(subfolder, exist_ok=True)

    # 生成输出文件名 (保存在子文件夹下)
    png_filename = os.path.join(subfolder, base_name + "_" + re.sub(r"\s+", "_", title) + ".png")

    plt.figure()  # 每一个图都单独生成 figure
    plt.plot(x_values, y_values, marker='o')
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel(title)

    # 旋转X轴刻度，避免重叠
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()

    plt.savefig(png_filename)
    plt.close()
    print(f"Saved plot: {png_filename}")


def process_csv(csv_file, dir):
    """
    读取单个 csv 文件，提取其中的 (Timestamp, CPU, MEM, Net, FDB_Used, FDB_Read, FDB_Write) 列。
    将这些列分别绘制时序图（以 Timestamp 为 x 轴），保存在不同子文件夹下。
    """
    timestamps = []
    cpu_vals = []
    mem_vals = []
    net_vals = []
    fdb_used_vals = []
    fdb_read_vals = []
    fdb_write_vals = []
    fdb_queried_vals = []

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader, None)  # 读表头

        # 确定列索引
        # 假设表头 = ["Timestamp", "CPU", "MEM", "Net", "FDB_Used", "FDB_Read", "FDB_Write"]
        ts_index = headers.index("Timestamp") if "Timestamp" in headers else None
        cpu_index = headers.index("CPU") if "CPU" in headers else None
        mem_index = headers.index("MEM") if "MEM" in headers else None
        net_index = headers.index("Net") if "Net" in headers else None
        fdbu_index = headers.index("FDB_Used") if "FDB_Used" in headers else None
        fdb_r_index = headers.index("FDB_Read") if "FDB_Read" in headers else None
        fdb_w_index = headers.index("FDB_Write") if "FDB_Write" in headers else None
        fdb_queried_index = headers.index("Hz") if "Hz" in headers else None

        for row in reader:
            if not row:
                continue

            t = parse_time(row[ts_index]) if ts_index is not None else None
            if t:
                timestamps.append(t)

                # CPU
                cpu_val = None
                if cpu_index is not None:
                    cpu_val = parse_float_safe(row[cpu_index])
                cpu_vals.append(cpu_val)

                # MEM
                mem_val = None
                if mem_index is not None:
                    mem_val = parse_float_safe(row[mem_index])
                mem_vals.append(mem_val)

                # Net (可能是 "22.5Kb" 这样的，需要做简单解析)
                net_val = None
                if net_index is not None:
                    net_str = row[net_index].strip()
                    m = re.match(r"([\d\.]+)([A-Za-z]+)", net_str)
                    if m:
                        net_val = parse_float_safe(m.group(1))
                        # 如果需要更精准换算可自行扩展
                net_vals.append(net_val)

                # FDB_Used
                fdb_used_val = None
                if fdbu_index is not None:
                    fdb_used_val = parse_float_safe(row[fdbu_index])
                fdb_used_vals.append(fdb_used_val)

                # FDB_Read
                fdb_read_val = None
                if fdb_r_index is not None:
                    fdb_read_val = parse_float_safe(row[fdb_r_index])
                fdb_read_vals.append(fdb_read_val)

                # FDB_Write
                fdb_write_val = None
                if fdb_w_index is not None:
                    fdb_write_val = parse_float_safe(row[fdb_w_index])
                fdb_write_vals.append(fdb_write_val)

                # queried keys
                fdb_queried_val = None
                if fdb_queried_index is not None:
                    fdb_queried_val = parse_float_safe(row[fdb_queried_index])
                fdb_queried_vals.append(fdb_queried_val)

    # 现在有了 timestamps + 各列数据。分别画图。
    base_name = os.path.splitext(os.path.basename(csv_file))[0]  # 去掉目录与.csv后缀

    make_plot(timestamps, cpu_vals, "CPU Usage (%)", base_name, dir)
    make_plot(timestamps, mem_vals, "Memory Usage (%)", base_name, dir)
    make_plot(timestamps, net_vals, "Total NETWORK Received and transmit (KB)", base_name, dir)
    make_plot(timestamps, fdb_used_vals, "FDB Space Used (%)", base_name, dir)
    make_plot(timestamps, fdb_read_vals, "FDB Space Read (MB)", base_name, dir)
    make_plot(timestamps, fdb_write_vals, "FDB Space Write (MB)", base_name, dir)
    make_plot(timestamps, fdb_queried_vals, "KeysQueriedCounter", base_name, dir)


def main(dir, file):
    # 查找当前目录下形如: monitor_high_1000_node*.csv
    pattern = f"{dir}/{file}*.csv"
    csv_files = glob.glob(pattern)

    if not csv_files:
        print(f"No CSV files found matching pattern: {pattern}")
        return

    csv_files.sort()
    for csvf in csv_files:
        print(f"Processing: {csvf}")
        process_csv(csvf, dir)


if __name__ == "__main__":
    # main('exp3-16cores/low_1000_nodefdb')
    # main('exp3-8cores/withoutcache_1000_10_nodebg', "bgClient_exp3_")
    # main('exp3-8cores/withoutcache_1000_100_nodebg', "bgClient_exp3_")
    # main('exp3-8cores/withoutcache_10000_10_nodebg', "bgClient_exp3_")
    # main('exp3-8cores/withoutcache_10000_100_nodebg', "bgClient_exp3_")
    # main('exp3-8cores/cache_10000_100_nodebg', "bgClient_exp3_")
    main('exp3-8cores/withoutcache_1000_10_nodeFdbCache', "fdbCache_exp3_")
    main('exp3-8cores/withoutcache_1000_10_nodeFdbStorage', "fdbStorage_exp3_")
    main('exp3-8cores/withoutcache_1000_100_nodeFdbCache', "fdbCache_exp3_")
    main('exp3-8cores/withoutcache_1000_100_nodeFdbStorage', "fdbStorage_exp3_")
    main('exp3-8cores/withoutcache_10000_10_nodeFdbCache', "fdbCache_exp3_")
    main('exp3-8cores/withoutcache_10000_10_nodeFdbStorage', "fdbStorage_exp3_")
    main('exp3-8cores/withoutcache_10000_100_nodeFdbCache', "fdbCache_exp3_")
    main('exp3-8cores/withoutcache_10000_100_nodeFdbStorage', "fdbStorage_exp3_")
    main('exp3-8cores/withoutcache_1000_10_nodejanus', "janusGraph_exp3_")
    main('exp3-8cores/withoutcache_1000_100_nodejanus', "janusGraph_exp3_")
    main('exp3-8cores/withoutcache_10000_10_nodejanus', "janusGraph_exp3_")
    main('exp3-8cores/withoutcache_10000_100_nodejanus', "janusGraph_exp3_")
    # main('exp3-16cores/low_1000_nodebg')
