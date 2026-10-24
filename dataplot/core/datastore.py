import numpy as np
import pandas as pd


class DataStore:
    def __init__(self):
        self.df: pd.DataFrame | None = None
        self.numeric_cols: list[str] = []
        self.categorical_cols: list[str] = []

    def load(self, path: str) -> pd.DataFrame:
        if path.endswith(".pkl"):
            try:
                self.df = pd.read_pickle(path)
            except ImportError as e:
                if "pyarrow" in str(e).lower():
                    raise ImportError("缺少 pyarrow 模块，请运行 `pip install pyarrow` 后重试。") from e
                raise
            self._refresh_columns()
            return self.df
            
        if path.endswith(".csv"):
            df = pd.read_csv(path, dtype=str)
        elif path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(path, dtype=str)
        else:
            raise ValueError(f"不支持的文件格式: {path}")

        self.df = self.infer_types(df)
        self._refresh_columns()
        return self.df

    @staticmethod
    def infer_types(df: pd.DataFrame) -> pd.DataFrame:
        """按规则推断：前导0保护、严格日期、包含小数转float、变长整数转float"""
        df = df.copy()
        for col in df.columns:
            if df[col].dtype != 'object':
                continue
                
            valid_series = df[col].dropna()
            if len(valid_series) == 0:
                continue
                
            valid_strs = valid_series.astype(str).str.strip()
            valid_strs = valid_strs[valid_strs != ""]
            if len(valid_strs) == 0:
                continue

            # 规则 1：前导 0 保护（只针对纯整数，如 003068）
            if valid_strs.str.match(r'^0\d+$').any():
                continue

            # 规则 2：严格日期/时间格式
            # 必须包含两个 - 或 /，或者两个 :，并且全部是数字和合法分隔符
            # 涵盖：yyyy-mm-dd, yy/mm/dd, yyyy-mm-dd hh:mm:ss 等
            date_pattern = r'^\d{2,4}[-/]\d{1,2}[-/]\d{1,2}([ T]\d{1,2}:\d{1,2}(:\d{1,2})?)?$|^\d{1,2}:\d{1,2}(:\d{1,2})?$'
            
            # 如果所有非空字符串都完美符合该模式，才尝试转日期
            if valid_strs.str.match(date_pattern).all():
                try:
                    converted_dt = pd.to_datetime(valid_strs, errors='coerce')
                    if converted_dt.notna().sum() == len(valid_strs):
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                        continue
                except Exception:
                    pass

            # 规则 3.1：包含小数点，直接判定为浮点数
            if valid_strs.str.contains('.', regex=False).any():
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').astype(float)
                continue

            # 规则 3.2：纯整数判定
            is_all_int = valid_strs.str.match(r'^-?\d+$').all()
            if is_all_int:
                lengths = set(len(s.lstrip('-')) for s in valid_strs)
                if len(lengths) > 1:
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
                else:
                    continue

        return df

    def _refresh_columns(self):
        if self.df is None:
            return
        self.numeric_cols = self.df.select_dtypes(include=np.number).columns.tolist()
        self.categorical_cols = [c for c in self.df.columns if c not in self.numeric_cols]

    def convert_type(self, col: str, dtype: str) -> tuple[bool, str]:
        if self.df is None: return False, "无数据"
        try:
            if dtype == "float":
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
            elif dtype == "str":
                self.df[col] = self.df[col].astype(str).replace("nan", "")
            elif dtype == "datetime":
                self.df[col] = pd.to_datetime(self.df[col], errors="coerce", format="mixed")
            self._refresh_columns()
            return True, ""
        except Exception as e:
            return False, str(e)

    @property
    def is_loaded(self) -> bool:
        return self.df is not None