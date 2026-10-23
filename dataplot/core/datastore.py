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
            df_str = pd.read_csv(path, dtype=str)
        elif path.endswith((".xlsx", ".xls")):
            df_str = pd.read_excel(path, dtype=str)
        else:
            raise ValueError(f"不支持的文件格式: {path}")

        # 智能转换：保留前导 0 的字符串，其余尝试转为数值或日期
        df = pd.DataFrame()
        for col in df_str.columns:
            s = df_str[col]
            has_leading_zero = s.str.match(r'^0\d+$', na=False).any()
            
            if not has_leading_zero:
                # 尝试转换为数值
                s_num = pd.to_numeric(s, errors='coerce')
                if not s_num.isna().all() and s_num.isna().sum() < len(s) * 0.5:
                    df[col] = s_num
                    continue
                    
                # 尝试转换为日期
                try:
                    s_date = pd.to_datetime(s, errors='coerce', format="mixed")
                    if not s_date.isna().all() and s_date.isna().sum() < len(s) * 0.5:
                        df[col] = s_date
                        continue
                except Exception:
                    pass
            
            df[col] = s
            
        self.df = df
        self._refresh_columns()
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