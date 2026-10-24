import re
from PySide6.QtCore import Qt, QStringListModel, Signal
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QCompleter


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#0000FF"))
        kw_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "exec", "finally", "for", "from", "global",
            "if", "import", "in", "is", "lambda", "not", "or", "pass", "print",
            "raise", "return", "try", "while", "with", "yield", "None", "True", "False"
        ]
        for word in keywords:
            self.rules.append((re.compile(r'\b' + word + r'\b'), kw_format))
            
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#A31515"))
        self.rules.append((re.compile(r'".*?"'), str_format))
        self.rules.append((re.compile(r"'.*?'"), str_format))
        
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#008000"))
        self.rules.append((re.compile(r'#[^\n]*'), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class SQLHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#0000FF"))
        kw_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "SELECT", "FROM", "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER",
            "ON", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET", "INSERT",
            "UPDATE", "DELETE", "CREATE", "TABLE", "DROP", "ALTER", "AND", "OR", "AS"
        ]
        for word in keywords:
            self.rules.append((re.compile(r'\b' + word + r'\b', re.IGNORECASE), kw_format))
            
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#008000"))
        self.rules.append((re.compile(r'--[^\n]*'), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class CodeEditor(QPlainTextEdit):
    execRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 11))
        self.setTabStopDistance(40)
        
        self.py_highlighter = PythonHighlighter(self.document())
        self.sql_highlighter = SQLHighlighter(self.document())
        self.sql_highlighter.setDocument(None)
        
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)
        
        self.py_words = ["df", "pd.", "np.", "db.", "MySQLHelper", "print(", "qry2df(", "query(", "read_sql(", "groupby(", "agg(", "merge("]
        self.sql_words = ["SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "JOIN", "ON", "AND", "OR", "LIMIT"]
        
        self.mode = "python"
        self.namespace = {}

    def set_mode(self, mode: str):
        self.mode = mode
        if mode == "python":
            self.sql_highlighter.setDocument(None)
            self.py_highlighter.setDocument(self.document())
            self.completer.setModel(QStringListModel(self.py_words, self))
        else:
            self.py_highlighter.setDocument(None)
            self.sql_highlighter.setDocument(self.document())
            self.completer.setModel(QStringListModel(self.sql_words, self))

    def set_namespace(self, namespace: dict):
        """注入全局命名空间以支持对象属性推断"""
        self.namespace = namespace

    def insert_completion(self, completion):
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.MoveOperation.Left)
        tc.movePosition(QTextCursor.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def _get_completions(self, text_before: str):
        if self.mode != "python":
            return self.sql_words, ""
            
        # 1. 检查是否包含点号属性调用 (例如 df.co)
        match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z0-9_]*)$', text_before)
        if match:
            obj_name = match.group(1)
            attr_prefix = match.group(2)
            
            # 去全局命名空间里找这个对象
            obj = self.namespace.get(obj_name)
            if obj is not None:
                try:
                    # 获取对象的属性与方法，过滤下划线开头
                    attrs = [a for a in dir(obj) if not a.startswith('_')]
                    # 过滤前缀
                    completions = [a for a in attrs if a.lower().startswith(attr_prefix.lower())]
                    return completions, attr_prefix
                except Exception:
                    pass
            return [], ""
            
        # 2. 普通变量名或关键字
        word_match = re.search(r'([a-zA-Z_][a-zA-Z0-9_]*)$', text_before)
        prefix = word_match.group(1) if word_match else ""
        
        # 提取命名空间中的变量 (过滤掉 __builtins__ 等)
        vars_in_ns = [k for k in self.namespace.keys() if not k.startswith('__')]
        all_words = list(set(self.py_words + vars_in_ns))
        completions = [w for w in all_words if w.lower().startswith(prefix.lower())]
        return completions, prefix

    def keyPressEvent(self, e):
        if (e.key() == Qt.Key.Key_Return or e.key() == Qt.Key.Key_Enter) and (e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.execRequested.emit()
            e.accept()
            return

        if self.completer.popup().isVisible():
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                e.ignore()
                return

        # 先让编辑器接收字符
        super().keyPressEvent(e)

        # 只有输入字母、数字、下划线或点号时才触发补全
        text = e.text()
        if not text or (not text.isalnum() and text not in "_. "):
            self.completer.popup().hide()
            return

        cursor = self.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()
        text_before = block_text[:pos_in_block]
        
        completions, prefix = self._get_completions(text_before)
        
        if not completions:
            self.completer.popup().hide()
            return
            
        model = QStringListModel(completions, self)
        self.completer.setModel(model)
        self.completer.setCompletionPrefix(prefix)
        
        if self.completer.completionCount() > 0:
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))
            rect = self.cursorRect()
            rect.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(rect)
        else:
            self.completer.popup().hide()