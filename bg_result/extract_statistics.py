import re
import pandas as pd


def parse_statistics_and_merge_retry(statistics_txt: str,
                                     # retry_csv: str,
                                     output_csv: str):
    """
    读取一个 'statistics' 文本文件 (如 'statistics_1000_low.txt') 并解析得到指标,
    再读取一个 'retry_summary' CSV (如 'retry_summary_1000_high.csv'),
    将 'avg_num_exceptions' 和 'has_failed_retries' 两列拼接到同一个 DataFrame,
    按 BGMainClass-(\\d+) 排序, 然后输出为 CSV.

    :param statistics_txt: 统计信息的文本文件路径 (如 "statistics_1000_low.txt")
    :param retry_csv: 重试信息的 CSV 文件路径 (如 "retry_summary_1000_high.csv")
    :param output_csv: 最终输出的 CSV 路径
    """
    # 1) 读取并解析 statistics_txt
    with open(statistics_txt, "r", encoding="utf-8") as f:
        content = f.read()

    # 按照 "=== File: ... ===" 分块
    # parts = [filename1, block1, filename2, block2, ...]
    parts = re.split(r"=== File: (.*?) ===", content)[1:]
    records = []

    for i in range(0, len(parts), 2):
        filename = parts[i].strip()
        block = parts[i + 1]

        # 提取 ThreadCount
        thread_match = re.search(r"ThreadCount:\s*(\d+)", block)
        thread_count = thread_match.group(1) if thread_match else ""

        # 提取 [OVERALL], RunTime(ms)
        runtime_match = re.search(r"\[OVERALL\],\s*RunTime\(ms\),\s*([\d\.]+)", block)
        runtime = runtime_match.group(1) if runtime_match else ""

        # 提取 [OVERALL], Throughput(sessions/sec)
        throughput_match = re.search(r"\[OVERALL\],\s*Throughput\(sessions/sec\),\s*([\d\.]+)", block)
        throughput = throughput_match.group(1) if throughput_match else ""

        # 提取 [OVERALL], opcount(sessions)
        opcount_match = re.search(r"\[OVERALL\],\s*opcount\(sessions\),\s*([\d\.]+)", block)
        opcount = opcount_match.group(1) if opcount_match else ""

        # 提取 [SatisfyingPerc]
        perc_match = re.search(r"\[SatisfyingPerc\]\s*([\d\.]+)", block)
        satisfying_perc = perc_match.group(1) if perc_match else ""

        avg_rt_match = re.search(r"AverageResponseTime\(us\)=([\d.]+)", block)
        avg_rt = float(avg_rt_match.group(1)) if perc_match else ""


        records.append({
            "filename": filename,
            "ThreadCount": thread_count,
            "[OVERALL], RunTime(ms)": runtime,
            "[OVERALL], Throughput(sessions/sec)": throughput,
            "[OVERALL], opcount(sessions)": opcount,
            "[SatisfyingPerc]": satisfying_perc,
            "AverageResponseTime": avg_rt
        })

    df = pd.DataFrame(records)

    # 提取 sort_key (BGMainClass-(\d+).log) 并转为 int
    df["sort_key"] = df["filename"].str.extract(r"BGMainClass-(\d+)\.log").astype(float)
    # 如果遇到非BGMainClass-xxx的文件, 可以填空/NaN. 也可做异常处理.
    # 先转 float 是因为extract()有时给的就是 float, 你也可以转 int: .astype("Int64")
    # 只要保持与后面merge的df2一致就行

    # 对 df 进行排序
    df = df.sort_values(by="sort_key", ignore_index=True)

    # # 2) 读取 retry_csv
    # df_retry = pd.read_csv(retry_csv)
    # # retry_csv 假设有列: filename, max_num_exceptions, avg_num_exceptions, total_retried_operations, has_failed_retries
    # # 同样提取 sort_key
    # df_retry["sort_key"] = df_retry["filename"].str.extract(r"BGMainClass-(\d+)\.log").astype(float)
    # df_retry = df_retry.sort_values(by="sort_key", ignore_index=True)
    #
    # # 3) 只保留我们关心的列: sort_key, avg_num_exceptions, has_failed_retries
    # df_retry_small = df_retry[["sort_key", "avg_num_exceptions", "has_failed_retries"]]
    #
    # # 4) 合并(拼接)到 df 上, 基于 sort_key
    # # how="left" 表示: 保留左边df全部行, 在df_retry_small中能对应上的就填, 否则NaN
    # df_merged = pd.merge(df, df_retry_small, on="sort_key", how="left")
    #
    # # 5) 不需要再留 sort_key 列的话, 可以删除
    # # df_merged = df_merged.drop(columns=["sort_key"])
    #
    # # 6) 输出到CSV
    # df_merged = df_merged.drop(columns=["sort_key"])
    # df_merged.drop(columns=['source'], inplace=True)
    # df_merged.to_csv(output_csv, index=False)
    df = df.drop(columns=["sort_key"])
    df.to_csv(output_csv, index=False)
    print(f"Done. Merged CSV written to {output_csv}")


if __name__ == "__main__":
    """
    使用示例:
    parse_statistics_and_merge_retry(
        statistics_txt="statistics_1000_low.txt",
        retry_csv="retry_summary_1000_high.csv",
        output_csv="exp_socialites_high_1000.csv"
    )
    """
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_cache_1000_10_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_cache_1000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp3_soar_withoutcache_1000_100_statistics.txt",
    #     output_csv="exp4-8cores/exp3_soar_withoutcache_1000_100_statistics.csv"
    # )
    #
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_cache_1000_10_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_cache_1000_10_statistics.csv"
    # )
    #
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_cache_1000_100_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_cache_1000_100_statistics.csv"
    # )
    #
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_cache_10000_100_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_cache_10000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_cache_10000_10_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_cache_10000_10_statistics.csv"
    # )
    #
    #
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_withoutcache_1000_10_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_withoutcache_1000_10_statistics.csv"
    # )

    parse_statistics_and_merge_retry(
        statistics_txt="exp4-8cores/exp4_soar_withoutcache_1000_100_statistics.txt",
        output_csv="exp4-8cores/exp4_soar_withoutcache_1000_100_statistics.csv"
    )
    parse_statistics_and_merge_retry(
        statistics_txt="exp4-8cores/exp4_soar_withoutcache_10000_100_statistics.txt",
        output_csv="exp4-8cores/exp4_soar_withoutcache_10000_100_statistics.csv"
    )
    parse_statistics_and_merge_retry(
        statistics_txt="exp4-8cores/exp4_soar_withoutcache_100000_100_statistics.txt",
        output_csv="exp4-8cores/exp4_soar_withoutcache_100000_100_statistics.csv"
    )

    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_withoutcache_10000_100_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_withoutcache_10000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_withoutcache_10000_10_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_withoutcache_10000_10_statistics.csv"
    # )

    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp4-8cores/exp4_soar_withoutcache_1000_10_statistics.txt",
    #     output_csv="exp4-8cores/exp4_soar_withoutcache_1000_10_statistics.csv"
    # )

    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp3_soar_cache_10000_100_statistics.txt",
    #     output_csv="exp3_soar_cache_10000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp3_soar_cache_10000_10_statistics.txt",
    #     output_csv="exp3_soar_cache_10000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_withoutcache_1000_10_statistics.txt",
    #     output_csv="exp_soar_withoutcache_1000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_withoutcache_1000_100_statistics.txt",
    #     output_csv="exp_soar_withoutcache_1000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_withoutcache_10000_10_statistics.txt",
    #     output_csv="exp_soar_withoutcache_10000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_withoutcache_10000_100_statistics.txt",
    #     output_csv="exp_soar_withoutcache_10000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_cache_1000_10_statistics.txt",
    #     output_csv="exp_soar_cache_1000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_cache_1000_100_statistics.txt",
    #     output_csv="exp_soar_cache_1000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_cache_10000_10_statistics.txt",
    #     output_csv="exp_soar_cache_10000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp_soar_cache_10000_100_statistics.txt",
    #     output_csv="exp_soar_cache_10000_100_statistics.csv"
    # )
    #
    #
    #
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_withoutcache_1000_10_statistics.txt",
    #     output_csv="exp2_soar_withoutcache_1000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_withoutcache_1000_100_statistics.txt",
    #     output_csv="exp2_soar_withoutcache_1000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_withoutcache_10000_10_statistics.txt",
    #     output_csv="exp2_soar_withoutcache_10000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_withoutcache_10000_100_statistics.txt",
    #     output_csv="exp2_soar_withoutcache_10000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_cache_1000_10_statistics.txt",
    #     output_csv="exp2_soar_cache_1000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_cache_1000_100_statistics.txt",
    #     output_csv="exp2_soar_cache_1000_100_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_cache_10000_10_statistics.txt",
    #     output_csv="exp2_soar_cache_10000_10_statistics.csv"
    # )
    # parse_statistics_and_merge_retry(
    #     statistics_txt="exp2_soar_cache_10000_100_statistics.txt",
    #     output_csv="exp2_soar_cache_10000_100_statistics.csv"
    # )
