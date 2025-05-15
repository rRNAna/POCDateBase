#!/usr/bin/env python3.12
#########################################################################################################
#
# Filename      : update_cpu2017_datenase.py
# Creation Date : Mar 15, 2025.
# Author: rRNA
# Description   :
#
#
#
###########################################################################################################
import os
import logging
import glob
import requests

import pandas as pd

from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, and_
from apscheduler.schedulers.blocking import BlockingScheduler
########################################################################
#                                                                      #
#                                                                      #
# Copyright New H3C Technologies Co., Ltd.                             #
#                                                                      #
# PURPOSE: See description above.                                      #
#                                                                      #
# VERSION: 1.1.0                                                       #
#                                                                      #
########################################################################

###########################################################################################################
###########################################################################################################
# —— 全局配置 ——
# 需要下载的全部 CPU 型号列表
CPU_MODEL_LIST = [
    "9754", "9734", "9654", "9634", "9554", "9534", "9454",
    "9354", "9334", "9254", "9224", "9124", "9474F", "9374F",
    "9274F", "9174F", "9684X", "9384X", "9184X", "9965",
    "9845", "9825", "9755", "9745", "9655", "9645", "9555",
    "9535", "9455", "9355", "9335", "9255", "9135", "9115",
    "9015", "9575F", "9475F", "9375F", "9275F", "9175F"
]
DOWNLOAD_DIR = './downloads'  # 下载地址
DATABASE_URL = 'sqlite:///../database.db'  # 数据库地址
TABLE_NAME = 'Turin_CPU2017_database'  # 数据表名

# —— 各阶段函数框架 ——

def download_spec_csv(download_dir: str):
    """
    从官网拉取 CSV，并保存到本地。
    返回保存的文件完整路径。
    """

    # 确保目录存在
    os.makedirs(download_dir, exist_ok=True)
    for cpu_model in CPU_MODEL_LIST:
        url = (
            f"https://www.spec.org/cgi-bin/osgresults"
            f"?conf=cpu2017&op=fetch&field=CPU&pattern={cpu_model}&format=csvdump"
        )
        logging.info(f"下载 CPU {cpu_model} 的 CSV：{url}")

        # 发起请求，使用流模式
        resp = requests.get(url, timeout=30, stream=True)
        resp.raise_for_status()

        # 构造文件名：型号+时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        cpu_model = url.split('pattern=')[-1].split('&')[0]
        filename  = f"spec_results_{cpu_model}_{timestamp}.csv"
        filepath  = os.path.join(download_dir, filename)

        # 写入二进制文件
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logging.info(f"Downloaded SPEC CSV for {cpu_model} to {filepath}")

    merge_and_cleanup(download_dir, os.path.join(DOWNLOAD_DIR, 'merged.csv'))
    output_csv_path = download_dir + '/merged.csv'

    return output_csv_path


def process_csv(input_csv_path: str):
    """
    读取并清洗 CSV 数据，返回处理后的 DataFrame。
    """
    # 原始提交厂商映射为简写 submitter 名称
    vendor_map = {
        'ASUSTeK Computer Inc.': 'ASUS',
        'Cisco Systems': 'Cisco',
        'Dell Inc.': 'Dell',
        'GIGA-BYTE TECHNOLOGY CO., LTD.': 'Gigabyte',
        'IEIT Systems Co., Ltd.': 'Inspur',
        'Inspur Electronic Information Industry Co., Ltd. (IEI)': 'Inspur',
        'Kaytus Systems Pte. Ltd.': 'Inspur',
        'Lenovo Global Technology': 'Lenovo',
        'Supermicro': 'Supermicro',
        'xFusion': 'xFusion',
        'New H3C Technologies Co., Ltd.': 'H3C',
        'Quanta Cloud Technology': 'Quanta',
        'Tyrone Systems': 'Tyron',
        'Epsylon Sp. z o.o. Sp. Komandytowa': 'Epsylon',
        'Fujitsu': 'Fujitsu',

    }

    # 对应基准名到数据库字段名
    benchmark_map = {
        "CINT2017": "SPECspeed(r)2017_int_base",
        "CFP2017": "SPECspeed(r)2017_fp_base",
        "CINT2017rate": "SPECrate(r)2017_int_base",
        "CFP2017rate": "SPECrate(r)2017_fp_base",
    }

    url_fields_map = {
        "CINT2017": "speed_int_url",
        "CFP2017": "speed_fp_url",
        "CINT2017rate": "rate_int_url",
        "CFP2017rate": "rate_fp_url",
    }

    # ========== 1. 读取CSV并清理 ==========
    df = pd.read_csv(input_csv_path)

    # 去掉列名里的空格、换行符
    df.columns = df.columns.str.strip()

    # 处理厂商简写
    df['submitter'] = df['Hardware Vendor'].map(lambda x: vendor_map.get(x.strip(), x.strip()))

    # 提取 CPU 数量
    df['cpu_count'] = df['# Chips']

    # 提取 CPU 型号
    df['cpu_model'] = df['Processor'].str.strip()

    # 提取 URL 末尾路径并补全为完整链接
    def extract_url(raw):
        if pd.isna(raw) or not isinstance(raw, str):
            return ""
        start = raw.find('HREF="')
        if start == -1:
            return ""
        end = raw.find('"', start + 6)
        return "https://www.spec.org" + raw[start + 6:end]

    df['full_url'] = df['Disclosures'].apply(extract_url)

    # ========== 2. 选出每类 benchmark 下，submitter+cpu_count 的最高 base result ==========
    results = {}

    for benchmark, result_col in benchmark_map.items():
        # 过滤该类 benchmark
        df_bench = df[df["Benchmark"] == benchmark].copy()

        # 按 cpu_model, submitter, cpu_count 选最大 Base Result
        df_bench["Base Result"] = pd.to_numeric(df_bench["Base Result"], errors="coerce")
        idx = df_bench.groupby(['cpu_model', 'submitter', 'cpu_count'])['Base Result'].idxmax()
        df_max = df_bench.loc[idx]

        for _, row in df_max.iterrows():
            key = (row['cpu_model'], row['submitter'], row['cpu_count'])

            if key not in results:
                results[key] = {
                    "cpu_model": row['cpu_model'],
                    "submitter": row['submitter'],
                    "cpu_count": row['cpu_count'],
                    "Machine Name": row['System'],
                    "Compiler": "N/A",
                    benchmark_map[benchmark]: row['Base Result'],
                    url_fields_map[benchmark]: row['full_url'],
                }
            else:
                results[key][benchmark_map[benchmark]] = row['Base Result']
                results[key][url_fields_map[benchmark]] = row['full_url']

    # ========== 3. 整理为表格格式 ==========
    final_df = pd.DataFrame(results.values())

    # 将 cpu_count 显示为 1P / 2P 形式
    final_df["cpu_count"] = final_df["cpu_count"].apply(lambda x: f"{int(x)}P" if pd.notna(x) else "")

    # 指定列的顺序
    column_order = [
        "cpu_model",
        "submitter",
        "SPECspeed(r)2017_int_base",
        "SPECspeed(r)2017_fp_base",
        "SPECrate(r)2017_int_base",
        "SPECrate(r)2017_fp_base",
        "speed_int_url",
        "speed_fp_url",
        "rate_int_url",
        "rate_fp_url",
        "Compiler",
        "cpu_count",
        "Machine Name"
    ]

    # 缺失字段填充为空
    for col in column_order:
        if col not in final_df.columns:
            final_df[col] = ""

    final_df = final_df[column_order]

    # ========== 4. 保存 ==========
    output_csv_path = './downloads/final_cleaned_results.csv'
    final_df.to_csv(output_csv_path, index=False)
    logging.info(f"[✔] Done. Saved to: {output_csv_path}")

    try:
        os.remove(input_csv_path)
    except Exception as e:
        logging.info(f"Error deleting {input_csv_path}: {e}")

    return output_csv_path


def compare_and_update(processed_csv: str):
    """
    将处理后的 DataFrame 与数据库中的现有表比对，执行插入和更新操作。
    """
    # ————————

    # 1) 读入 CSV
    df_official = pd.read_csv(processed_csv)

    # 2) 直接从数据库加载已有数据到 DataFrame
    engine = create_engine(DATABASE_URL)
    # 如果表名里有大写或者特殊字符，可以用 read_sql_query
    df_local = pd.read_sql_table(TABLE_NAME, con=engine)

    # 3) 重命名列，使之与数据库列名一致
    rename_map = {
        'CPU Model': 'cpu_model',
        'submitter': 'submitter',
        'SPECspeed(r)2017_int_base': 'speed_int_base',
        'SPECspeed(r)2017_fp_base': 'speed_fp_base',
        'SPECrate(r)2017_int_base': 'rate_int_base',
        'SPECrate(r)2017_fp_base': 'rate_fp_base',
        'cpu_count': 'cpu_count',
        'speed_int_url': 'speed_int_url',
        'speed_fp_url': 'speed_fp_url',
        'rate_int_url': 'rate_int_url',
        'rate_fp_url': 'rate_fp_url',
        'Compiler': 'compiler',
        'Machine Name': 'machine_name'
    }
    df_official.rename(columns=rename_map, inplace=True)
    # df_local   .rename(columns=rename_map, inplace=True)

    # 4) 定义业务主键（稳定不变的列）和度量列
    STABLE_KEYS = ['cpu_model', 'submitter', 'cpu_count']
    METRIC_COLUMNS = [
        'speed_int_base',
        'speed_fp_base',
        'rate_int_base',
        'rate_fp_base'
    ]

    # —— 新增：去重，确保每个业务主键只有一条记录 ——
    df_official = df_official.drop_duplicates(subset=STABLE_KEYS, keep='last')
    df_local = df_local.drop_duplicates(subset=STABLE_KEYS, keep='last')

    # 5) 计算新增与需更新的行
    # —— 计算主键集合 ——
    official_keys = set(map(tuple, df_official[STABLE_KEYS].values))
    local_keys = set(map(tuple, df_local[STABLE_KEYS].values))

    # —— 计算新增行 ——
    new_keys = official_keys - local_keys
    new_rows = df_official[
        df_official[STABLE_KEYS]
        .apply(lambda r: tuple(r), axis=1)
        .isin(new_keys)
    ]

    # —— 计算需更新行 ——
    off_idx = df_official.set_index(STABLE_KEYS)
    loc_idx = df_local.set_index(STABLE_KEYS)
    common_index = off_idx.index.intersection(loc_idx.index)

    arr_off = off_idx.loc[common_index, METRIC_COLUMNS].to_numpy()
    arr_loc = loc_idx.loc[common_index, METRIC_COLUMNS].to_numpy()
    diff_mask = (arr_off != arr_loc).any(axis=1)

    upd_rows = off_idx.loc[common_index[diff_mask]].reset_index()

    # 补充逻辑：new_rows 中 compiler 为空时填充 'unknown'
    new_rows['compiler'] = new_rows['compiler'].astype('string').fillna('unknown')
    logging.info(f'New records: {len(new_rows)} records; records to be updated: {len(upd_rows)} records.')

    # 6) 用 Core API 插入 & 更新
    metadata = MetaData()
    metadata.reflect(bind=engine)
    table = metadata.tables[TABLE_NAME]

    with engine.begin() as conn:
        # 批量插入
        if not new_rows.empty:
            conn.execute(
                table.insert(),
                new_rows.to_dict(orient='records')
            )
            logging.info(f'{len(new_rows)} new records inserted.')
        # 逐条更新
        if not upd_rows.empty:
            for _, row in upd_rows.iterrows():
                pk_cond = and_(
                    *[table.c[key] == row[key] for key in STABLE_KEYS]
                )
                update_values = {col: row[col] for col in METRIC_COLUMNS}
                conn.execute(
                    table.update().where(pk_cond).values(**update_values)
                )
            logging.info(f'{len(upd_rows)} records updated.')

    # 7) 删除 processed_csv
    try:
        os.remove(processed_csv)
    except Exception as e:
        logging.info(f"Error deleting {processed_csv}: {e}")


def merge_and_cleanup(download_dir: str, output_file: str):
    """
        将 download_dir 下所有 .csv 文件合并成一个 output_file，
        合并完成后删除原目录下的所有 .csv 文件。
        """
    # 1) 找到所有 CSV 文件（注意：这里是具体的文件路径）
    pattern = os.path.join(download_dir, '*.csv')
    files = glob.glob(pattern)
    if not files:
        logging.info("No CSV files were found in the directory.")
        return

    # 2) 读取并合并
    dfs = []
    for fp in files:
        try:
            # 正确打开文件 fp，而不是打开 download_dir
            df = pd.read_csv(fp)
            dfs.append(df)
        except Exception as e:
            logging.info(f"Error reading {fp}: {e}")
    merged = pd.concat(dfs, ignore_index=True)

    # 3) 写入合并文件
    # 确保父目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    merged.to_csv(output_file, index=False)
    logging.info(f"Merged {len(files)} files into {output_file}")

    # 4) 删除原始文件
    for fp in files:
        try:
            os.remove(fp)
        except Exception as e:
            logging.info(f"Error deleting {fp}: {e}")
    logging.info("All original files have been deleted.")

if __name__ == '__main__':
    # 日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s'
    )

    # 下载并整合官网所有数据
    merged_csv_path = download_spec_csv(DOWNLOAD_DIR)
    # 对整个数据处理
    # merged_csv_path = "./downloads/merged.csv"
    final_cleaned_csv_path = process_csv(merged_csv_path)
    # final_cleaned_csv_path = "./downloads/final_cleaned_results.csv"
    # 将处理后的数据更新到数据库
    compare_and_update(final_cleaned_csv_path)

    # 定时调度，每两周执行一次
    # scheduler = BlockingScheduler(timezone="Asia/Tokyo")
    # scheduler.add_job(
    #     sync_all,
    #     trigger='interval',
    #     weeks=2,
    #     next_run_time=datetime.now()
    # )
    # scheduler.start()
