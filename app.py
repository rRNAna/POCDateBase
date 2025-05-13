#!/usr/bin/env python3.12
#########################################################################################################
#
# Filename      : app.py
# Creation Date : Feb 14, 2025.
# Author: rRNA
# Description   :
#
#
#
###########################################################################################################
from flask import Flask, render_template, request, redirect, render_template_string, url_for
from flask_bootstrap import Bootstrap
import sqlite3
########################################################################
#                                                                      #
#                                                                      #
# Copyright New H3C Technologies Co., Ltd.                             #
#                                                                      #
# PURPOSE: See description above.                                      #
#                                                                      #
# VERSION: 1.0.0                                                       #
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
    return render_template('base.html')


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
@app.route('/spec_cpu2017')
def spec_cpu2017():
    conn = get_db_connection()

    if conn is None:
        return "Database connection error", 500

    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Turin_CPU2017_database ORDER BY cpu_model DESC, submitter DESC')  # 获取所有数据
    rows = cursor.fetchall()  # 获取所有记录

    if not rows:
        print("No data returned from database")
        return "No data available", 404

    conn.close()

    # 按照 CPU Model 、 CPU Count 和 Compiler 分组
    grouped_data = {}
    for row in rows:
        cpu_key = (row['cpu_model'], row['cpu_count'], row['compiler'])
        if cpu_key not in grouped_data:
            grouped_data[cpu_key] = []
        grouped_data[cpu_key].append(row)

    # 对每个分组的数据进行处理，找出最大值并标记
    max_values = {}
    for key, group in grouped_data.items():
        max_values[key] = {
            'speed_int_base': max([row['speed_int_base'] for row in group if row['speed_int_base'] is not None],
                                  default=None),
            'speed_fp_base': max([row['speed_fp_base'] for row in group if row['speed_fp_base'] is not None],
                                 default=None),
            'rate_int_base': max([row['rate_int_base'] for row in group if row['rate_int_base'] is not None],
                                 default=None),
            'rate_fp_base': max([row['rate_fp_base'] for row in group if row['rate_fp_base'] is not None], default=None)
        }

    return render_template('spec_cpu2017.html', grouped_data=grouped_data, max_values=max_values)  # 渲染数据到HTML模板



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)





