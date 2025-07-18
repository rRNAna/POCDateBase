#!/usr/bin/env python3.12
#########################################################################################################
#
# Filename      : app.py
# Creation Date : Jul 14, 2025.
# Author: rRNA
# Description   :
#
###########################################################################################################
from dotenv import load_dotenv
import os
import subprocess
import functools
import sqlite3

from flask import Flask, render_template, request, redirect, render_template_string, url_for, abort, \
    current_app, session, flash
from flask_bootstrap import Bootstrap
from functools import wraps
from sqlalchemy.orm.session import Session

########################################################################
#                                                                      #
#                                                                      #
# Copyright New H3C Technologies Co., Ltd.                             #
#                                                                      #
# PURPOSE: See description above.                                      #
#                                                                      #
# VERSION: 2.0.0                                                       #
#                                                                      #
########################################################################

###########################################################################################################
###########################################################################################################

# 加载 .env 中的环境变量
load_dotenv()

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

if not ADMIN_USERNAME or not ADMIN_PASSWORD or not SECRET_KEY:
    raise ValueError('Please set ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY in the .env file')

app = Flask(__name__)
app.secret_key = SECRET_KEY  # 用于 session 签名

# 检查是否登陆
def requires_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return wrapper

@app.route('/admin/login', methods=['GET', 'POST'])
@requires_auth
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('index'))
    error = None
    if  request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Login Successful')
            nxt = request.args.get('next') or url_for('index')
            return redirect(url_for('nxt'))
        else:
            error = 'Incorrect username or password'
    return render_template("admin_login.html", error=error)


@app.route('/admin/logout')
@requires_auth
def admin_logout():
    session.pop('is_admin', None)
    flash('Logout Successful')
    return redirect(url_for('index'))

def get_db_connection():
    try:
        conn = sqlite3.connect('database.db')  # 连接到SQLite数据库
        conn.row_factory = sqlite3.Row  # 使得查询结果返回字典格式
        return conn

    except Exception as e:
        print(f"Database connection error: {e}")
        return None


@app.route('/')
def index():
    return render_template('base.html',
                           version='v1.9.0',
                           author='rRNA',
                           contact='rasdasto857@gmail.com',
                           description='这是 POC_DataBase 的信息页。'
                           )


# SPEC CPU2017 数据显示路由
@app.route('/spec_cpu2017', methods=['GET'])
def spec_cpu2017():
    cpu_input = (request.args.get('cpu_model') or '').strip()
    current_app.logger.info(f"User search input: '{cpu_input}'")

    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()

    rows = []
    if cpu_input:
        # 调试：打印所有可选的 cpu_model 值
        # cursor.execute("SELECT DISTINCT cpu_model FROM CPU2017_database")
        # all_models = [r['cpu_model'].strip() for r in cursor.fetchall()]
        # current_app.logger.info(f"Available cpu_model values: {all_models}")

        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM CPU2017_database
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC, submitter DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall()

    conn.close()

    # 按照 CPU Model 、 CPU Count 和 Compiler 分组
    grouped_data = {}
    max_values = {}

    if cpu_input and rows:
        for row in rows:
            # 按照 CPU Model 、 CPU Count 和 Compiler_family 分组

            compiler_full = row['compiler'] or ""
            # 取空格前的第一个词作为“家族”，如 “AOCC” 或 “GCC”
            compiler_family = compiler_full.split()[0] if compiler_full else ""

            key = (row['cpu_model'], row['cpu_count'], compiler_family)
            grouped_data.setdefault(key, []).append(row)
        for key, group in grouped_data.items():
            # 对每个分组的数据进行处理，找出最大值并标记
            max_values[key] = {
                'speed_int_base': max((r['speed_int_base'] or 0) for r in group),
                'speed_int_peak': max((r['speed_int_peak'] or 0) for r in group),
                'speed_fp_base': max((r['speed_fp_base'] or 0) for r in group),
                'speed_fp_peak': max((r['speed_fp_peak'] or 0) for r in group),
                'rate_int_base': max((r['rate_int_base'] or 0) for r in group),
                'rate_int_peak': max((r['rate_int_peak'] or 0) for r in group),
                'rate_fp_base': max((r['rate_fp_base'] or 0) for r in group),
                'rate_fp_peak': max((r['rate_fp_peak'] or 0) for r in group)
            }

    return render_template(
        'spec_cpu2017.html',
        cpu_model=cpu_input,
        grouped_data=grouped_data,
        max_values=max_values
    )


# Stream 数据显示路由
@app.route('/stream', methods=['GET'])
def stream():

    cpu_input = (request.args.get('cpu_model') or '').strip()
    current_app.logger.info(f"User search input: '{cpu_input}'")

    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()

    rows = []
    if cpu_input:
        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM Stream_database
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC, cpu_count DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall() # 获取所有记录

    conn.close()

    # 一次遍历：计算 + 分组
    grouped = {}
    for row in rows:
        # 把原 row 转成 dict（方便后面解包）
        base = dict(row)

        # 从 row 里取出 cpu_model、cpu_count、compiler 作为分组键
        cpu = base['cpu_model']
        count = base['cpu_count']
        comp = base['compiler']
        key = (cpu, count, comp)

        # 计算 theo/pct
        if cpu.upper().startswith("AMD"):
            triad = base['stream_triad']
            theo = 64 * base['memory_speed'] / 8 * base['memory_count']
            pct = (triad / theo * 100) if theo else None
        else:
            theo = None
            pct = None

        # 把新字段直接合并到 base dict
        item = {
            **base,  # 解包所有原始列
            'theoretical_bw': theo,  # 新增字段
            'bw_pct': pct  # 新增字段
        }

        # 按 key 放到 grouped
        grouped.setdefault(key, []).append(item)

    # 渲染模板，把分组后的字典传进去
    return render_template(
        'stream.html',
        cpu_model=cpu_input,
        grouped_data=grouped
    )


# UnixBench 数据显示路由
@app.route('/unixbench', methods=['GET'])
def unixbench():
    cpu_input = (request.args.get('cpu_model') or '').strip()
    current_app.logger.info(f"User search input: '{cpu_input}'")

    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()

    rows = []
    if cpu_input:
        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM Unixbench_database
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC, submitter DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall()

    conn.close()

    # 按 cpu_model, cpu_count, compiler 分组
    grouped = {}
    for item in rows:
        key = (item['cpu_model'], item['cpu_count'], item['compiler'])
        grouped.setdefault(key, []).append(item)

    # 渲染网页模版，传入分组数据
    return render_template(
        'unixbench.html',
        cpu_model=cpu_input,
        grouped_data=grouped
    )


# HPL 数据显示路由
@app.route('/hpl', methods=['GET'])
def hpl():
    cpu_input = (request.args.get('cpu_model') or '').strip()
    current_app.logger.info(f"User search input: '{cpu_input}'")

    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()

    rows = []
    if cpu_input:
        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM HPL_database
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC, submitter DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall()

    conn.close()

    # 按 cpu_model 分组
    grouped = {}
    for item in rows:
        cpu = item['cpu_model']
        grouped.setdefault(cpu, []).append(item)

    # 渲染网页模版，传入分组数据
    return render_template(
        'hpl.html',
        cpu_model=cpu_input,
        grouped_data=grouped
    )


# sysbench 数据路由
@app.route('/sysbench', methods=['GET'])
def sysbench():
    cpu_input = (request.args.get('cpu_model') or '').strip()
    current_app.logger.info(f"User search input: '{cpu_input}'")

    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()

    rows = []
    if cpu_input:
        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM SysBench_database
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall()

    conn.close()

    # 按 cpu_model 分组
    grouped = {}
    for item in rows:
        cpu = item['cpu_model']
        grouped.setdefault(cpu, []).append(item)

    # 渲染网页模版，传入分组数据
    return render_template(
        'sysbench.html',
        cpu_model=cpu_input,
        grouped_data=grouped
    )

# lmbench 查询路由
@app.route('/lmbench', methods=['GET'])
def lmbench():
    cpu_input = (request.args.get('cpu_model') or '').strip()
    current_app.logger.info(f"User search input: '{cpu_input}'")

    conn = get_db_connection()

    if conn is None:
        abort(500, "Database connection error")

    cursor = conn.cursor()

    rows = []
    if cpu_input:
        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM Lmbench_meta_information
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall()

    conn.close()

    return render_template(
        'lmbench.html',
        runs=rows,
        cpu_model=cpu_input
    )

# Lmbench 数据显示路由
@app.route('/lmbench/<int:run_id>')
def show_lmbench_run(run_id):
    conn = get_db_connection()
    if conn is None:
        abort(500, "Database connection error")

    try:
        cur = conn.cursor()
        # 1）查元信息
        cur.execute(
            'SELECT * FROM Lmbench_meta_information WHERE id = ?',
            (run_id,)
        )
        meta = cur.fetchone()
        if meta is None:
            abort(404, "Run not found")

        # 2）查询跨 Node 延迟
        # 一次性取出所有 lam_mem_rd 记录
        cur.execute(
            'SELECT target, lam_mem_rd '
            'FROM Lmbench_lam_mem_rd_database WHERE meta_id = ? '
            'ORDER BY target',
            (run_id,)
        )
        records = cur.fetchall()

        # nodes 只是取 distinct target，用作渲染时的表头或索引
        nodes = sorted({r['target'] for r in records})

        # lam_mem_rd 保留为完整的记录列表，传给模板
        lam_mem_rd = records

    finally:
        conn.close()

    # 3）渲染模板
    return render_template(
        'run_lmbench_detail.html',
        meta=meta,
        nodes=nodes,
        lam_mem_rd=lam_mem_rd
    )


# AMD CVT & Intel MLC 查询路由
@app.route('/cvt_mlc', methods=['GET'])
def cvt_mlc():

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
        # 构造模糊匹配模式，两边都用 %，并去掉字段前后空格后再比对
        pattern = f"%{cpu_input}%"
        current_app.logger.info(f"Querying with pattern: '{pattern}'")

        cursor.execute(
            """
            SELECT *
            FROM CVT_MLC_meta_Information
            WHERE TRIM(cpu_model) LIKE ? COLLATE NOCASE
            ORDER BY cpu_model DESC
            """,
            (pattern,)
        )
        rows = cursor.fetchall()

    conn.close()

    return render_template(
        'cvt_mlc.html',
        runs=rows,  # 原来的 rows
        cpu_model=cpu_input  # 新增，把用户的搜索关键词传进去
    )


# AMD CVT & Intel MLC 显示路由
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





