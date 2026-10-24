# 已自动注入: pd (pandas), np (numpy), MySQLHelper
# 请在下方编写代码，处理后的结果赋值给 df

db = MySQLHelper(db='jhd')

# 示例：执行 SQL 获取数据
# sql = "SELECT * FROM your_table LIMIT 10000"
# df = db.qry2df(sql)

# 示例：Pandas 加工
# df = df[df['amount'] > 0]
# print("数据清洗完成，共", len(df), "行")