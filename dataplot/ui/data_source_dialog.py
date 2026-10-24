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


CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".dataplot_cache.json")

class ExecuteWorker(QThread):
    # ... (保持不变) ...
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
                self.namespace['db'] = self.db_helper_class(db=self.db_name)
                print(f"✅ 数据库环境已切换至: {self.db_name}")

            if actual_mode == "python":
                exec(self.code, self.namespace)
            else:
                self.namespace['df'] = self.namespace['db'].qry2df(self.code)
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
        
        self._current_mode = "Python"
        self.saved_py_code = ""
        self.saved_sql_code = ""
        self.saved_db_list = ["jhd","ginger2" ]
        
        self.global_namespace = {
            'pd': pd,
            'np': np,
            'MySQLHelper': self.db_helper_class,
            '__builtins__': __builtins__
        }
        
        self._build_ui()
        self._init_from_cache()

    def _build_ui(self):
        # ... (顶部工具栏代码保持不变) ...
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
        # 关键：把命名空间引用传递给编辑器
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

    # ... (其余函数：_init_from_cache, _auto_save_cache, _on_mode_changed, _sync_mode_ui, _restore_template 保持不变) ...
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
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(base_dir, "templates", f"{mode}_template.{'py' if mode == 'python' else 'sql'}")
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
        self.btn_run.setEnabled(True)
        
        # 核心：执行完毕后，通知编辑器命名空间已更新（可能有了新的 df 变量）
        # 因为引用传递，编辑器里的 namespace 是最新的。但重新设置一次可以刷新补全状态
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

    def _apply_data(self):
        # ... 保持不变 ...
        if not hasattr(self, 'current_df') or self.current_df is None:
            QMessageBox.warning(self, "提示", "请先执行代码获取数据。")
            return
        if hasattr(self, 'model'):
            modified_df = self.model.get_dataframe()
            if len(self.current_df) > 1000:
                final_df = pd.concat([modified_df, self.current_df.iloc[1000:]]).reset_index(drop=True)
            else:
                final_df = modified_df
        else:
            final_df = self.current_df
        self.global_namespace['df'] = final_df
        self.data_applied.emit(final_df)
        self.hide()