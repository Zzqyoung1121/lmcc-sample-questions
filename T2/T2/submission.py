"""T2 括号序列判定 —— 数据处理函数（作答文件）。

限制（题面第四、六条）：
    * 函数代码最多 16KiB。
    * 只使用纯函数定义、文档字符串，以及 json / re / collections 标准库。
    * 常量写在函数内；不调用模型、网络或外部服务，不读取文件或评测数据。
"""


def process_data(records):
    """清洗并规范化原始记录，按原始顺序返回标准记录列表。

    参数:
        records: 原始记录列表，元素形如 {"sequence": str, "valid": str}
                 其中 valid 已由你标注为 YES 或 NO。

    返回:
        list[dict]：形如 [{"input": "序列：()", "output": "[Valid]: YES"}, ...]

    规则（题面"四 数据清洗的完整规则"）：
        1. records 不是列表 -> ValueError；非字典 / 缺字段 / 字段类型不符 -> 跳过。
        2. sequence 删除全部空白字符，长度须为 2..12 且只含半角 ( 和 )，否则跳过。
        3. valid 去首尾空白并大写，只接受 YES / NO，否则跳过。
        4. 按 input 稳定去重；同一 input 不同 output -> ValueError。
        5. 只清洗格式，不判断括号是否合法、不补写标签。
    """
    # TODO: 在这里实现
    raise NotImplementedError
