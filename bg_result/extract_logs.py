import re
import csv


def parse_iteration_blocks(log_path):
    """
    读取log文件，按 "=== START TEST ..." 到 "=== END TEST ..." 拆分出多段（iteration 块）。
    返回一个列表，每个元素是字典：
      {
        'iteration': <int>,
        'threadCount': <int>,
        'lines': [所有内容行, ...]
      }
    """
    with open(log_path, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()

    blocks = []
    current_block = None

    start_pattern = re.compile(r'^=== START TEST iteration=(\d+), threadCount=(\d+) ===')
    end_pattern = re.compile(r'^=== END TEST iteration=(\d+), threadCount=(\d+) ===')

    for line in all_lines:
        line_stripped = line.strip()

        # 检查是不是 start 标记
        start_match = start_pattern.match(line_stripped)
        if start_match:
            iteration = int(start_match.group(1))
            threads = int(start_match.group(2))
            current_block = {
                'iteration': iteration,
                'threadCount': threads,
                'lines': []
            }
            continue

        # 检查是不是 end 标记
        end_match = end_pattern.match(line_stripped)
        if end_match and current_block is not None:
            end_iter = int(end_match.group(1))
            end_threads = int(end_match.group(2))
            if end_iter == current_block['iteration'] and end_threads == current_block['threadCount']:
                blocks.append(current_block)
                current_block = None
            continue

        # 如果在块里，就把行加入
        if current_block is not None:
            current_block['lines'].append(line)

    return blocks


def parse_monitor_block(lines):
    """
    给定多行文本，解析 CPU, MEM, NET, FDB, memory_used_bytes, keys_queried_counter, hz 等信息。
    返回一个 list，元素是：
      [timestamp, cpu, mem, net, fdb_network_thr, fdb_used, fdb_read, fdb_write,
       memory_used_bytes, keys_queried_counter, hz]
    """
    content = "".join(lines)
    # 拆分 timestamp 块
    splitted = re.split(r'====\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*====', content)
    result_rows = []

    for i in range(1, len(splitted), 2):
        timestamp = splitted[i].strip()
        block_text = splitted[i + 1]
        block_lines = block_text.splitlines()

        cpu_val = mem_val = net_val = ""
        fdb_used_val = fdb_read_val = fdb_write_val = ""
        memory_used_bytes_val = ""
        keys_queried_counter_val = ""
        hz_val = ""

        for j, line in enumerate(block_lines):
            ls = line.strip()

            # Top 1 CPU
            if "Top 1 process by CPU usage" in ls or "Top CPU" in ls:
                for k in range(j + 1, len(block_lines)):
                    c2 = block_lines[k].strip()
                    if c2:
                        parts = c2.split()
                        if len(parts) >= 9:
                            cpu_val = parts[8]
                        break

            # Top 1 MEM
            if "Top 1 process by memory usage" in ls or "Top MEM" in ls:
                for k in range(j + 1, len(block_lines)):
                    c2 = block_lines[k].strip()
                    if c2:
                        parts = c2.split()
                        if len(parts) >= 10:
                            mem_val = parts[9]
                        break

            # 网络流量
            if "Total send and receive rate:" in ls:
                m = re.search(r"rate:\s*([\d\.]+)([A-Za-z]+)", ls)
                if m:
                    net_val = m.group(1) + m.group(2)

            if "Cluster max disk busy" in ls:
                if j + 1 < len(block_lines):
                    m = re.match(r'([\d\.]+)', block_lines[j + 1].strip())
                    if m:
                        fdb_used_val = m.group(1)

            if "Cluster write MBps" in ls:
                if j + 1 < len(block_lines):
                    m = re.match(r'([\d\.]+)', block_lines[j + 1].strip())
                    if m:
                        fdb_write_val = m.group(1)

            if "Cluster read MBps" in ls:
                if j + 1 < len(block_lines):
                    m = re.match(r'([\d\.]+)', block_lines[j + 1].strip())
                    if m:
                        fdb_read_val = m.group(1)


            # 新增：memory_used_bytes
            if "memory_used_bytes=" in ls:
                m = re.search(r"memory_used_bytes=(\d+)", ls)
                if m:
                    memory_used_bytes_val = m.group(1)

            # 新增：keys_queried_counter 和 hz
            if "keys_queried_counter=" in ls:
                m_keys = re.search(r"keys_queried_counter=(\d+)", ls)
                if m_keys:
                    keys_queried_counter_val = m_keys.group(1)
                m_hz = re.search(r"hz=([\d\.]+)", ls)
                if m_hz:
                    hz_val = m_hz.group(1)

        result_rows.append([
            timestamp,
            cpu_val,
            mem_val,
            net_val,
            fdb_used_val,
            fdb_read_val,
            fdb_write_val,
            memory_used_bytes_val,
            keys_queried_counter_val,
            hz_val
        ])

    return result_rows


def parse_log_by_iteration(dir, log_path, output_prefix="iteration_"):
    """
    1) 先以 "START TEST" / "END TEST" 分块
    2) 对每块进行解析
    3) 输出 CSV => "iteration_{iter}_threads_{thread}.csv"
    """
    blocks = parse_iteration_blocks(f"{dir}/{log_path}")

    for block in blocks:
        iteration = block['iteration']
        threads = block['threadCount']
        lines = block['lines']

        rows = parse_monitor_block(lines)
        csv_filename = f"{dir}/{log_path}_{output_prefix}{iteration}_threads_{threads}.csv"

        with open(csv_filename, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # 在 header 中加入新的三列
            writer.writerow([
                "Timestamp", "CPU", "MEM", "Net",
                "FDB_Used", "FDB_Read", "FDB_Write",
                "MemoryUsedBytes", "KeysQueriedCounter", "Hz"
            ])
            writer.writerows(rows)

        print(f"Generated CSV for iteration={iteration}, threads={threads} -> {csv_filename}")

def parse_log_raw(dir, log_path, output_name=None):
    """
    原始模式：不检查 START/END，直接对整个文件做 monitor 解析
    """
    raw_file = f"{dir}/{log_path}"
    with open(raw_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    rows = parse_monitor_block(lines)
    name = output_name or log_path.replace('.', '_') + '_raw.csv'
    out = f"{dir}/{name}"
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["Timestamp","CPU","MEM","Net","FDB_Used","FDB_Read","FDB_Write","MemoryUsedBytes","KeysQueriedCounter","Hz"])
        w.writerows(rows)
    print(f"Generated raw CSV: {out}")


if __name__ == "__main__":
    pass
    # parse_log_raw('exp3-8cores/cache_10000_100_nodebg', 'bgClient_exp3_soar_cache_10000_100_monitor.log',
    #               'bgClient_exp3_soar_cache_10000_100_monitor.csv')
    # parse_log_raw('exp3-8cores/withoutcache_10000_100_nodebg', 'bgClient_exp3_soar_withoutcache_10000_100_monitor.log',
    #               'bgClient_exp3_soar_withoutcache_10000_100_monitor.csv')
    # parse_log_raw('exp3-8cores/withoutcache_10000_10_nodebg', 'bgClient_exp3_soar_withoutcache_10000_10_monitor.log',
    #               'bgClient_exp3_soar_withoutcache_10000_10_monitor.csv')
    # parse_log_raw('exp3-8cores/withoutcache_1000_100_nodebg', 'bgClient_exp3_soar_withoutcache_1000_100_monitor.log',
    #               'bgClient_exp3_soar_withoutcache_1000_100_monitor.csv')
    # parse_log_raw('exp3-8cores/withoutcache_1000_10_nodebg', 'bgClient_exp3_soar_withoutcache_1000_10_monitor.log',
    #               'bgClient_exp3_soar_withoutcache_1000_10_monitor.csv')
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_10_nodebg',
    #     'bgClient_exp3_soar_cache_1000_10_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_10_nodebg',
    #     'bgClient_exp3_soar_cache_1000_10_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_10_nodejanus',
    #     'janusGraph_exp3_soar_cache_1000_10_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_10_nodeFdbCache',
    #     'fdbCache_exp3_soar_cache_1000_10_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_10_nodeFdbStorage',
    #     'fdbStorage_exp3_soar_cache_1000_10_monitor.log'
    # )


    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_100_nodebg',
    #     'bgClient_exp3_soar_cache_1000_100_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_100_nodejanus',
    #     'janusGraph_exp3_soar_cache_1000_100_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_100_nodeFdbCache',
    #     'fdbCache_exp3_soar_cache_1000_100_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_1000_100_nodeFdbStorage',
    #     'fdbStorage_exp3_soar_cache_1000_100_monitor.log'
    # )


    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_10_nodebg',
    #     'bgClient_exp3_soar_cache_10000_10_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_10_nodejanus',
    #     'janusGraph_exp3_soar_cache_10000_10_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_10_nodeFdbCache',
    #     'fdbCache_exp3_soar_cache_10000_10_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_10_nodeFdbStorage',
    #     'fdbStorage_exp3_soar_cache_10000_10_monitor.log'
    # )


    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_100_nodebg',
    #     'bgClient_exp3_soar_cache_10000_100_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_100_nodejanus',
    #     'janusGraph_exp3_soar_cache_10000_100_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_100_nodeFdbCache',
    #     'fdbCache_exp3_soar_cache_10000_100_monitor.log'
    # )
    # parse_log_by_iteration(
    #     'exp3-8cores/cache_10000_100_nodeFdbStorage',
    #     'fdbStorage_exp3_soar_cache_10000_100_monitor.log'
    # )