import re
import sys
import pandas as pd
import matplotlib.pyplot as plt

def parse_line(line):
    """
    从一行日志里提取需要的信息：
    1) datetime_str: "YYYY-MM-DD HH:MM:SS:mmm"
    2) sec_val:      int, 日志里 ... 880 sec: ...
    3) operations:   int, ... 340529 operations; ...
    4) current_ops:  float, ... 399.4 current ops/sec ...
    5) avg_latency:  float, ... [INSERT AverageLatency(us)=2470.72]
    
    返回字典，如果无法匹配则返回 None
    """
    # 这儿我们用一个正则表达式去匹配示例行的基本结构
    # 形如：
    # 2025-01-28 12:15:22:029 880 sec: 340529 operations; 399.4 current ops/sec; ...
    # [INSERT AverageLatency(us)=2470.72]
    # pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}:\d{3})\s+(\d+)\s+sec:\s+(\d+)\s+operations;\s+([\d\.]+)\s+current\s+ops/sec;.*AverageLatency\(us\)=([\d\.]+)\]'
    index = line.find("CLEANUP")
    if index != -1:
        # index + len("cleanup") 可以保证把 "cleanup" 自身也保留下来
        line = line[:index]
    pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}:\d{3})\s+(\d+)\s+sec:\s+(\d+)\s+operations;\s+([\d\.]+)\s+current\s+ops/sec;.*Avg=([\d\.]+)'

    match = re.match(pattern, line.strip())
    if not match:
        return None
    
    datetime_str = match.group(1)   # 字符串形式的时间
    sec_val      = int(match.group(2))
    operations   = int(match.group(3))
    current_ops  = float(match.group(4))
    avg_latency  = float(match.group(5))
    
    return {
        "datetime_str": datetime_str,
        "sec": sec_val,
        "operations": operations,
        "current_ops": current_ops,
        "avg_latency": avg_latency
    }

def parse_file(filepath):
    """
    读取文件并解析每一行，返回一个 DataFrame，包含以下列：
      - datetime_str
      - sec
      - current_ops
      - avg_latency
    """
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            # print(line)
            parsed = parse_line(line)
            if parsed:
                data.append(parsed)
                
    df = pd.DataFrame(data)
    return df

def group_and_aggregate(df, group_interval):
    """
    按照指定的 group_interval（单位秒）对 df 的数据分组：
    - 对 'current_ops' 做 sum
    - 对 'avg_latency' 做 mean
    
    注意我们这里用的是 sec // group_interval 来区分分组。
    返回一个新的 DataFrame，包含：
      - group_index  分组索引（sec // group_interval）
      - sec         分组起点（group_index * group_interval）
      - ops_sec_sum 分组内所有 current_ops 的求和
      - latency_avg 分组内 avg_latency 的均值
    """
    # 先根据 sec // group_interval 做分组
    df['group_index'] = df['sec'] // group_interval
    
    grouped = df.groupby('group_index')
    result_df = pd.DataFrame()
    result_df['ops_sec_sum'] = grouped['current_ops'].sum()
    result_df['latency_avg'] = grouped['avg_latency'].mean()
    
    
    # 把分组索引变成一列
    result_df.reset_index(inplace=True)
    # 让 sec = group_index * group_interval，表示这个分组起始的 sec 值
    result_df['sec'] = result_df['group_index'] * group_interval
    
    return result_df

def plot_data(dfs, group_interval, filenames, outfile):
    """
    传入多个文件（已经经过 parse_file -> group_and_aggregate）的结果 DataFrame，
    以及对应的文件名列表 filenames，用于在图中做图例区分。
    画两张图：
      1) sec vs. ops_sec_sum
      2) sec vs. latency_avg
    """
    
    fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(8, 8))
    ax1, ax2 = axes
    
    
    for df, fname in zip(dfs, filenames):
        # print(df['ops_sec_sum'].head())
        ax1.plot(df['sec'], df['ops_sec_sum'], label=fname)
        ax2.plot(df['sec'], df['latency_avg'], label=fname)
    
    # 第一张图
    ax1.set_title(f'Total Operations (grouped by {group_interval*10}s)')
    ax1.set_xlabel('Sec')
    ax1.set_ylabel(f'Total Operations per {group_interval*10}s')
    # ax1.set_ylim(min(df['ops_sec_sum']), max(df['ops_sec_sum']))
    ax1.legend()
    ax1.grid(True)
    
    # 第二张图
    ax2.set_title(f'Latency Average (grouped by {group_interval * 10}s)')
    ax2.set_xlabel('Sec')
    ax2.set_ylabel('Avg Latency (us)')
    ax2.legend()
    ax2.grid(True)
    if "scan" in outfile:
        fig.suptitle(f'{outfile}(1000keys per scan) Data(SQLite vs. Cache)', fontsize=14)
    else:
        fig.suptitle(f'{outfile} Data(SQLite vs. Cache)', fontsize=14)
    
    plt.tight_layout()
    plt.savefig(f"{outfile}.png")

def main(group_interval, datasize, operation):
    """
    主函数示例：
    用法: 
       python your_script.py 60 file1.log [file2.log ...]
    表示 group_interval=60，输入一个或多个文件
    """
    
    
    filepaths = [f"./result/{datasize}_cache/{operation}.txt", f"./result/{datasize}_sqlite/{operation}.txt"]
    # filepaths = [f"./result/{datasize}_sqlite/{operation}.txt"]

    
    
    # 依次解析每个文件，并做分组聚合
    dfs = []
    for fp in filepaths:
        df = parse_file(fp)
        if df.empty:
            print(f"警告：文件 {fp} 没有解析到任何有效行！")
            continue
        grouped_df = group_and_aggregate(df, group_interval)
        dfs.append(grouped_df)
    
    if not dfs:
        print("没有任何有效数据，退出。")
        return
    
    # 画图
    plot_data(dfs, group_interval, filepaths, f"{datasize}_{operation}")


if __name__ == "__main__":
    datasize = str(sys.argv[2])
    group_interval = int(sys.argv[1])
    
    main(group_interval, datasize, "insert")
    main(group_interval, datasize, "read_uniform")
    main(group_interval, datasize, "read_zipfian")
    main(group_interval, datasize, "scan_uniform")
    main(group_interval, datasize, "scan_zipfian")
    
    
