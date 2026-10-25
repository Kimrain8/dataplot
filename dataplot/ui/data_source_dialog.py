import os
import sys
import re
import json
import traceback
import pandas as pd
import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QComboBox, QPushButton,
    QTableView, QTextEdit, QWidget, QLabel, QMessageBox, QHeaderView
)

from dataplot.ui.code_editor import CodeEditor
from dataplot.ui.pandas_model import PandasModel

# ============ 核心：适配 PyInstaller 打包后的路径 ============
def get_base_path():
    """获取资源路径（打包后指向临时解压目录）"""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_exe_dir():
    """获取可执行文件所在目录（用于存放可写的缓存文件）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_PATH = get_base_path()
EXE_DIR = get_exe_dir()

# 缓存文件放在 exe 同级目录，模板放在打包的内部资源目录
CACHE_FILE = os.path.join(EXE_DIR, ".dataplot_cache.json")

class ExecuteWorker(QThread):
    finished = Signal(pd.DataFrame, str)
    output = Signal(str)
    mode_detected = Signal(str)

    def __init__(self, code, mode, db_name, db_helper_class, namespace):
        super().__init__()
        self.code = code
        self.mode = mode
        self.db_name = db_name
        self.db_helper_class = db_helper_class
        self.namespace = namespace

    def run(self):
        print("\n========== 进入 ExecuteWorker.run ==========")
        print(f"DEBUG: 执行模式: {self.mode}, 数据库: {self.db_name}")
        class StdoutRedirector:
            def __init__(self, signal):
                self.signal = signal
            def write(self, text):
                if text.strip():
                    self.signal.emit(text)
            def flush(self): pass

        old_stdout = sys.stdout
        sys.stdout = StdoutRedirector(self.output)

        try:
            clean_code = re.sub(r'#[^\n]*', '', self.code)
            clean_code = re.sub(r'--[^\n]*', '', clean_code)
            clean_code = clean_code.strip().lower()

            actual_mode = self.mode
            if clean_code.startswith(("select ", "with ", "update ", "insert ", "delete ", "show ", "desc ")):
                actual_mode = "sql"
            elif clean_code.startswith(("import ", "from ", "def ", "class ", "pd.", "df ")):
                actual_mode = "python"
                
            if actual_mode != self.mode:
                self.output.emit(f"💡 自动识别为 {actual_mode.upper()} 模式。")
                self.mode_detected.emit(actual_mode)

            current_db = self.namespace.get('db')
            if current_db is None or getattr(current_db, 'db', None) != self.db_name:
                default_path = r'D:\pyprj\cv2\utils\config.json'
                config_path = default_path
                
                # 如果默认路径不存在，尝试在当前目录（打包后的 exe 目录或运行目录）找
                if not os.path.exists(config_path):
                    if getattr(sys, 'frozen', False):
                        exe_dir = os.path.dirname(sys.executable)
                    else:
                        exe_dir = os.getcwd()
                    fallback_path = os.path.join(exe_dir, 'config.json')
                    if os.path.exists(fallback_path):
                        config_path = fallback_path
                        print(f"⚠️ 默认配置未找到，已自动回退到当前目录: {config_path}")

                # 尝试实例化连接
                try:
                    print(f"DEBUG: 准备实例化 MySQLHelper，config_path={config_path}")
                    self.namespace['db'] = self.db_helper_class(config_path=config_path, db=self.db_name)
                    print("DEBUG: MySQLHelper 实例化成功！")
                    print(f"✅ 数据库环境已切换至: {self.db_name}")
                except Exception as e:
                    print(f"❌ 数据库连接失败，配置路径: {config_path}")
                    print(f"错误详情: {e}")
                    # 清理单例池中的脏实例，以便下次重试
                    if hasattr(self.db_helper_class, '_instance_pool') and self.db_name in self.db_helper_class._instance_pool:
                        del self.db_helper_class._instance_pool[self.db_name]
                    raise e

            if actual_mode == "python":
                exec(self.code, self.namespace)
            else:
                self.namespace['df'] = self.namespace['db'].qry2df(self.code)
                print(f"DEBUG: SQL 执行成功，获取数据形状: {self.namespace['df'].shape}")
                print("✅ SQL 执行成功，结果已保存至变量 `df`。")

            df = self.namespace.get('df', pd.DataFrame())
            if not isinstance(df, pd.DataFrame):
                raise TypeError("代码执行成功，但环境变量 'df' 不是 pandas DataFrame。")
            self.finished.emit(df, "")

        except Exception as e:
            err_msg = traceback.format_exc()
            self.output.emit(err_msg)
            self.finished.emit(pd.DataFrame(), err_msg)
        finally:
            sys.stdout = old_stdout


class DataSourceDialog(QDialog):
    data_applied = Signal(pd.DataFrame)

    def __init__(self, db_helper_class, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据源处理 (SQL / Python)")
        self.resize(1200, 800)
        self.db_helper_class = db_helper_class
        
        # 新增：用于自动加载项目时自动推送数据
        self.auto_apply = False
        
        self._current_mode = "Python"
        self.saved_py_code = ""
        self.saved_sql_code = ""
        self.saved_db_list = ["jhd", "ginger2"]
        
        self.global_namespace = {
            'pd': pd,
            'np': np,
            'MySQLHelper': self.db_helper_class,
            '__builtins__': __builtins__
        }
        
        self._build_ui()
        self._init_from_cache()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("执行模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Python", "SQL"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        top_bar.addWidget(self.mode_combo)
        
        top_bar.addSpacing(10)
        top_bar.addWidget(QLabel("数据库:"))
        self.db_combo = QComboBox()
        self.db_combo.setEditable(True)
        self.db_combo.setFixedWidth(120)
        top_bar.addWidget(self.db_combo)
        
        self.btn_template = QPushButton("恢复当前模式默认模板")
        self.btn_template.clicked.connect(self._restore_template)
        top_bar.addSpacing(10)
        top_bar.addWidget(self.btn_template)
        
        top_bar.addStretch()
        
        self.btn_run = QPushButton("运行选中/全部 (Ctrl+Enter)")
        self.btn_run.setStyleSheet("background: #3b82f6; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_run.clicked.connect(self._execute)
        top_bar.addWidget(self.btn_run)
        
        self.btn_apply = QPushButton("应用到画布")
        self.btn_apply.setStyleSheet("background: #10b981; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_apply.clicked.connect(self._apply_data)
        top_bar.addWidget(self.btn_apply)
        
        layout.addLayout(top_bar)

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        upper_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.editor = CodeEditor()
        self.editor.set_namespace(self.global_namespace)
        self.editor.execRequested.connect(self._execute)
        self.editor.textChanged.connect(self._auto_save_cache)
        upper_splitter.addWidget(self.editor)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table_info = QLabel("尚未加载数据。运行代码获取数据后，可双击单元格编辑前 1000 行。")
        self.table_info.setStyleSheet("color: #666;")
        right_layout.addWidget(self.table_info)
        
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        right_layout.addWidget(self.table_view)
        
        upper_splitter.addWidget(right_widget)
        upper_splitter.setSizes([500, 700])
        
        self.main_splitter.addWidget(upper_splitter)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        self.main_splitter.addWidget(self.console)
        
        self.main_splitter.setSizes([600, 200])
        layout.addWidget(self.main_splitter)

    def _init_from_cache(self):
        py_code = self._read_template("python")
        sql_code = self._read_template("sql")
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    self.saved_py_code = cache.get("py_code", py_code)
                    self.saved_sql_code = cache.get("sql_code", sql_code)
                    self.saved_db_list = cache.get("db_list", self.saved_db_list)
            except Exception:
                self.saved_py_code = py_code
                self.saved_sql_code = sql_code
        else:
            self.saved_py_code = py_code
            self.saved_sql_code = sql_code
            
        self.db_combo.clear()
        self.db_combo.addItems(self.saved_db_list)
        self.editor.set_mode("python")
        self.editor.setPlainText(self.saved_py_code)

    def _auto_save_cache(self):
        if self._current_mode == "Python":
            self.saved_py_code = self.editor.toPlainText()
        else:
            self.saved_sql_code = self.editor.toPlainText()
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"py_code": self.saved_py_code, "sql_code": self.saved_sql_code, "db_list": self.saved_db_list}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _read_template(self, mode):
        template_path = os.path.join(BASE_PATH, "templates", f"{mode}_template.{'py' if mode == 'python' else 'sql'}")
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        return f"-- 未找到模板文件: {template_path}" if mode == "sql" else f"# 未找到模板文件: {template_path}"

    def _on_mode_changed(self, new_mode):
        if new_mode == self._current_mode: return
        if self._current_mode == "Python":
            self.saved_py_code = self.editor.toPlainText()
        else:
            self.saved_sql_code = self.editor.toPlainText()
        self._current_mode = new_mode
        self.editor.blockSignals(True)
        if new_mode == "Python":
            self.editor.set_mode("python")
            self.editor.setPlainText(self.saved_py_code)
        else:
            self.editor.set_mode("sql")
            self.editor.setPlainText(self.saved_sql_code)
        self.editor.blockSignals(False)

    def _sync_mode_ui(self, detected_mode):
        target_text = "SQL" if detected_mode == "sql" else "Python"
        if self.mode_combo.currentText() != target_text:
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentText(target_text)
            self.mode_combo.blockSignals(False)

    def _restore_template(self):
        self.editor.blockSignals(True)
        if self._current_mode == "Python":
            self.saved_py_code = self._read_template("python")
            self.editor.setPlainText(self.saved_py_code)
        else:
            self.saved_sql_code = self._read_template("sql")
            self.editor.setPlainText(self.saved_sql_code)
        self.editor.blockSignals(False)
        self._auto_save_cache()

    def _execute(self):
        print("\n========== 进入 DataSourceDialog._execute ==========")
        print(f"DEBUG: 当前模式: {self._current_mode}, 当前 DB: {self.db_combo.currentText()}")
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            code = cursor.selectedText().replace('\u2029', '\n')
            self.console.append(">>> 正在执行 选中代码...\n")
        else:
            code = self.editor.toPlainText()
            self.console.append(">>> 正在执行 全部代码...\n")
            
        if not code.strip():
            return

        self.btn_run.setEnabled(False)
        db_name = self.db_combo.currentText().strip()
        if not db_name: db_name = "jhd"
        if db_name not in self.saved_db_list:
            self.saved_db_list.append(db_name)
            self.db_combo.addItem(db_name)
            self._auto_save_cache()
        
        self.worker = ExecuteWorker(code, self._current_mode.lower(), db_name, self.db_helper_class, self.global_namespace)
        self.worker.output.connect(self.console.append)
        self.worker.mode_detected.connect(self._sync_mode_ui)
        self.worker.finished.connect(self._on_exec_finished)
        self.worker.start()

    def _on_exec_finished(self, df, err):
        print("\n========== 进入 _on_exec_finished ==========")
        print(f"DEBUG: 收到数据形状: {df.shape}, 是否有错误: {bool(err)}")
        print(f"DEBUG: 当前 auto_apply 状态: {self.auto_apply}")
        self.btn_run.setEnabled(True)
        self.editor.set_namespace(self.global_namespace)
        
        if err:
            self.console.append("\n❌ 执行失败。\n")
            err_lines = err.strip().split("\n")
            self.console.append("\n".join(err_lines[-3:]))
            return
            
        self.console.append(f"\n✅ 执行成功，当前 df 包含 {len(df)} 行 × {len(df.columns)} 列。")
        
        self.current_df = df
        self.model = PandasModel(df, max_rows=1000)
        self.table_view.setModel(self.model)
        
        if len(df) > 1000:
            self.table_info.setText(f"总计 {len(df)} 行。仅展示并允许编辑前 1000 行。")
        else:
            self.table_info.setText(f"总计 {len(df)} 行。可在此直接双击编辑。")

        # 核心修复：如果是自动加载项目触发的执行，跑完立刻推送到主画布
        if self.auto_apply:
            self.auto_apply = False
            self._apply_data()

    def _apply_data(self):
        print("\n========== 进入 DataSourceDialog._apply_data ==========")
        if not hasattr(self, 'current_df') or self.current_df is None:
            print("DEBUG: 错误 - current_df 为空")
            QMessageBox.warning(self, "提示", "请先执行代码获取数据。")
            return
            
        try:
            if hasattr(self, 'model'):
                modified_df = self.model.get_dataframe()
                if len(self.current_df) > 1000:
                    final_df = pd.concat([modified_df, self.current_df.iloc[1000:]]).reset_index(drop=True)
                else:
                    final_df = modified_df
            else:
                final_df = self.current_df
                
            print(f"DEBUG: 准备通过 emit 发送数据，形状: {final_df.shape}")
            self.global_namespace['df'] = final_df
            self.data_applied.emit(final_df)
            print("DEBUG: emit 信号发送完毕")
            self.hide()
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(f"❌ _apply_data 发生异常:\n{err}")