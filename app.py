#!/usr/bin/env python3.12
#########################################################################################################
#
# Filename      : app.py
# Creation Date : Mar 14, 2025.
# Author: rRNA
# Description   :
#
#
#
###########################################################################################################
import subprocess

from flask import Flask, render_template, request, redirect, render_template_string, url_for, abort, current_app
from flask_bootstrap import Bootstrap
import sqlite3

from sqlalchemy.orm.session import Session

########################################################################
#                                                                      #
#                                                                      #
# Copyright New H3C Technologies Co., Ltd.                             #
#                                                                      #
# PURPOSE: See description above.                                      #
#                                                                      #
# VERSION: 1.2.0                                                       #
#                                                                      #
########################################################################

###########################################################################################################
###########################################################################################################

app = Flask(__name__)


def get_db_connection():
    try:
        conn = sqlite3.connect('database.db')  # 连接到您的SQLite数据库
        conn.row_factory = sqlite3.Row  # 使得查询结果返回字典格式
        return conn

    except Exception as e:
        print(f"Database connection error: {e}")
        return None


@app.route('/')
def index():
    return render_template('base.html',
                           version='v1.3.0',
                           author='rRNA',
                           contact='rasdasto857@gmail.com',
                           description='这是 POC_DataBase 的信息页。'
                           )


# @app.route('/search', methods=['POST'])
# def search():
#     item_name = request.form['item_name']
#     conn = sqlite3.connect('database.db')
#     c = conn.cursor()
#     c.execute('SELECT * FROM items WHERE name LIKE ?', ('%' + item_name + '%',))
#     items = c.fetchall()
#     conn.close()
#     return render_template_string('''
#         <html>
#         <body>
#             <h1>Search Results</h1>
#             <ul>
#             {% for item in items %}
#                 <li>{{ item[1] }}</li>
#             {% endfor %}
#             </ul>
#             <a href="/">Back</a>
#         </body>
#         </html>
#     ''', items=items)

# SPEC CPU2017 数据显示路由
@app.route('/spec_cpu2017', methods=['GET'])
def spec_cpu2017():
    cpu_input = request.args.get('cpu_model', '') or ''
    cpu_input = cpu_input.strip()
    current_app.logger.info(f"User search input: '{cpu_input}'")

    cpu_model = request.args.get('cpu_model', '').strip()

    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()

    rows = []
    if cpu_input:
        # 调试：打印所有可选的 cpu_model 值
        cursor.execute("SELECT DISTINCT cpu_model FROM Turin_CPU2017_database")
        all_models = [r['cpu_model'].strip() for r in cursor.fetchall()]
        current_app.logger.info(f"Available cpu_model values: {all_models}")

        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM Turin_CPU2017_database
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC, submitter DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall()

    # if cpu_model:
    #     pattern = f'%{cpu_model}%'
    #     cursor.execute(
    #         'SELECT * FROM Turin_CPU2017_database WHERE cpu_model = ? ORDER BY cpu_model DESC, submitter DESC',
    #         (pattern,)
    #     )
    #     rows = cursor.fetchall()
    # else:
    #     rows = []
    conn.close()

    # 按照 CPU Model 、 CPU Count 和 Compiler 分组
    grouped_data = {}
    max_values = {}

    if cpu_model and rows:
        for row in rows:
            # 按照 CPU Model 、 CPU Count 和 Compiler 分组
            key = (row['cpu_model'], row['cpu_count'], row['compiler'])
            grouped_data.setdefault(key, []).append(row)
        for key, group in grouped_data.items():
            # 对每个分组的数据进行处理，找出最大值并标记
            max_values[key] = {
                'speed_int_base': max((r['speed_int_base'] or 0) for r in group),
                'speed_fp_base': max((r['speed_fp_base'] or 0) for r in group),
                'rate_int_base': max((r['rate_int_base'] or 0) for r in group),
                'rate_fp_base': max((r['rate_fp_base'] or 0) for r in group)
            }

    return render_template(
        'spec_cpu2017.html',
        cpu_model=cpu_model,
        grouped_data=grouped_data,
        max_values=max_values
    )


    # max_values = {}
    # for key, group in grouped_data.items():
    #     max_values[key] = {
    #         'speed_int_base': max([row['speed_int_base'] for row in group if row['speed_int_base'] is not None],
    #                               default=None),
    #         'speed_fp_base': max([row['speed_fp_base'] for row in group if row['speed_fp_base'] is not None],
    #                              default=None),
    #         'rate_int_base': max([row['rate_int_base'] for row in group if row['rate_int_base'] is not None],
    #                              default=None),
    #         'rate_fp_base': max([row['rate_fp_base'] for row in group if row['rate_fp_base'] is not None], default=None)
    #     }
    #
    # return render_template('spec_cpu2017.html', grouped_data=grouped_data, max_values=max_values)  # 渲染数据到HTML模板

# Stream 数据显示路由
@app.route('/stream')
def stream():
    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Stream_database ORDER BY cpu_model DESC, cpu_count DESC')  # 获取所有数据
    rows = cursor.fetchall()  # 获取所有记录

    # 先把每条记录加工一下，计算理论带宽和百分比
    processed = []
    for row in rows:
        cpu = row['cpu_model']
        # 只有 AMD CPU 才计算理论值
        if cpu .startswith("AMD"):
            # triad 实测值
            triad = row['stream_triad']
            # 理论带宽：64 字节 * memory_speed(MT/s) / 8 (转换到字节) * memory_count
            theo = 64 * row['memory_speed'] / 8 * row['memory_count']
            pct = (triad / theo * 100) if theo else None
        else:
            # 非 AMD，跳过计算
            theo = None
            pct = None

        # 把所有字段打平到字典里，再加上这两个新值
        data = dict(row)
        data['theoretical_bw'] = theo
        data['bw_pct'] = pct
        processed.append(data)

    # 按 cpu_model, cpu_count, compiler 分组
    grouped = {}
    for item in processed:
        key = (item['cpu_model'], item['cpu_count'], item['compiler'])
        grouped.setdefault(key, []).append(item)

    # 渲染模板，把分组后的字典传进去
    return render_template('stream.html', grouped_data=grouped)


# UnixBench 数据显示路由
@app.route('/unixbench')
def unixbench():
    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Unixbench_database ORDER BY cpu_model DESC, submitter DESC')  # 获取所有数据
    rows = cursor.fetchall()  # 获取所有记录

    if not rows:
        print("No data returned from database")
        return "No data available", 404

    conn.close()

    # 按 cpu_model, cpu_count, compiler 分组
    grouped = {}
    for item in rows:
        key = (item['cpu_model'], item['cpu_count'], item['compiler'])
        grouped.setdefault(key, []).append(item)
    # 渲染网页模版，传入分组数据
    return render_template('unixbench.html', grouped_data=grouped)

# HPL 数据显示路由
@app.route('/hpl')
def hpl():
    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()
    cursor.execute('SELECT * FROM HPL_database ORDER BY cpu_model DESC, submitter DESC')  # 获取所有数据
    rows = cursor.fetchall()  # 获取所有记录

    if not rows:
        print("No data returned from database")
        return "No data available", 404

    conn.close()

    # 按 cpu_model 分组
    grouped = {}
    for item in rows:
        cpu = item['cpu_model']
        grouped.setdefault(cpu, []).append(item)

    # 渲染网页模版，传入分组数据
    return render_template('hpl.html', grouped_data=grouped)


@app.route('/cvt_mlc')
def cvt_mlc():
    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()
    cursor.execute('SELECT * FROM CVT_MLC_meta_Information ORDER BY cpu_model DESC')  # 获取所有数据
    rows = cursor.fetchall()  # 获取所有记录

    if not rows:
        print("No data returned from database")
        return "No data available", 404

    conn.close()


    # 按 cpu_model 分组
    # grouped = {}
    # for item in rows:
    #     cpu = item['cpu_model']
    #     grouped.setdefault(cpu, []).append(item)

    # 渲染网页模版，传入分组数据
    return render_template('cvt_mlc.html', runs=rows)
    # return render_template('cvt_mlc.html', grouped_data=grouped)

@app.route('/cvt_mlc/<int:run_id>')
def show_cvt_mlc_run(run_id):
    conn = get_db_connection()
    if conn is None:
        abort(500, "Database connection error")
    cur = conn.cursor()

    # 1）查元信息
    cur.execute(
        'SELECT * FROM CVT_MLC_meta_information WHERE id = ?',
        (run_id,)
    )
    meta = cur.fetchone()
    if meta is None:
        conn.close()
        abort(404, "Run not found")

    # 2）查节点延迟
    cur.execute(
        'SELECT source, target, latency_ns '
        'FROM NodeLatency WHERE meta_id = ? '
        'ORDER BY source, target',
        (run_id,)
    )
    latencies = cur.fetchall()  # List[sqlite3.Row]

    # 3）查注入延迟 & 带宽
    cur.execute(
        'SELECT delay_ns, loaded_latency, bandwidth_mb_s '
        'FROM InjectionMetrics WHERE meta_id = ? '
        'ORDER BY delay_ns',
        (run_id,)
    )
    injections = cur.fetchall()

    # 4）查节点带宽
    cur.execute(
        'SELECT source, target, bandwidth_mb_s '
        'FROM NodeBandwidth WHERE meta_id = ? '
        'ORDER BY source, target',
        (run_id,)
    )
    bandwidths = cur.fetchall()

    conn.close()

    # 5）组织矩阵数据
    nodes = sorted({row['source'] for row in latencies} |
                   {row['target'] for row in latencies})
    latency_matrix = {
        (r['source'], r['target']): r['latency_ns']
        for r in latencies
    }
    bandwidth_matrix = {
        (r['source'], r['target']): r['bandwidth_mb_s']
        for r in bandwidths
    }

    # 6）渲染模板，Row 对象直接能用 row['col'] 取值
    return render_template(
        'run_cvt_mlc_detail.html',
        meta=meta,
        nodes=nodes,
        latency_matrix=latency_matrix,
        injections=injections,
        bandwidth_matrix=bandwidth_matrix
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)





