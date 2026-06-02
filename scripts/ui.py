import json
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(f"  {title}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet(
            "QPushButton { text-align: left; border: none; "
            "font-weight: bold; padding: 4px; }"
        )
        self.toggle_button.clicked.connect(self._toggle)
        self.content_area = QWidget()
        self.content_area_layout = QVBoxLayout(self.content_area)
        self.content_area_layout.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)

    def add_widget(self, widget):
        self.content_area_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_area_layout.addLayout(layout)

    def _toggle(self, checked):
        self.content_area.setVisible(checked)


class GenerateWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int, str)
    finished = Signal(str)

    def __init__(self, client, gen_para, prompts, process_mgr, seed_mode,
                 seed_value):
        super().__init__()
        self.client = client
        self.gen_para = gen_para
        self.prompts = prompts
        self.process_mgr = process_mgr
        self.seed_mode = seed_mode
        self.seed_value = seed_value
        self._paused = False
        self._cancelled = False
        self._interrupted = False

    def pause(self):
        self._paused = True

    def cancel(self):
        self._cancelled = True
        self._paused = False
        self.client.interrupt()

    def interrupt(self):
        self._interrupted = True
        self._paused = False
        self.client.interrupt()

    def run(self):
        total = len(self.prompts)
        process_data = self.process_mgr.load()
        start_idx = process_data.get("current_index", 0)
        if start_idx >= total:
            start_idx = 0

        self.process_mgr.update_index(
            start_idx, total, status=ProcessManager.GENERATING
        )

        total_start_time = time.time()
        total_elapsed = 0.0

        for i in range(start_idx, total):
            if self._cancelled:
                self.log.emit("已取消")
                self.process_mgr.update_index(
                    i, total, status=ProcessManager.CANCELLED
                )
                self.finished.emit("cancelled")
                return

            if self._interrupted:
                self.log.emit("已中断")
                self.process_mgr.update_index(
                    i, total, status=ProcessManager.PAUSED
                )
                self.finished.emit("interrupted")
                return

            if self._paused:
                self.log.emit(f"已暂停于第 {i + 1}/{total} 张")
                self.process_mgr.update_index(
                    i, total, status=ProcessManager.PAUSED
                )
                self.finished.emit("paused")
                return

            prompt_item = self.prompts[i]
            prompt_text = prompt_item["prompt"]
            neg_text = prompt_item["negative_prompt"]

            self.log.emit(
                f"[{i + 1}/{total}] 正在生成: {prompt_text[:60]}..."
            )
            self.progress.emit(i, total, "generating")

            try:
                result = self.client.txt2img(
                    prompt_text, neg_text, self.gen_para,
                    seed_mode=self.seed_mode,
                    seed_value=self.seed_value,
                    base_seed=self.seed_value,
                    image_index=i,
                )

                # 如果 API 调用期间收到了中断/取消，不推进进度
                if self._interrupted:
                    self.log.emit("已中断，跳过当前进度")
                    self.process_mgr.update_index(
                        i, total, status=ProcessManager.PAUSED
                    )
                    self.finished.emit("interrupted")
                    return

                if self._cancelled:
                    self.log.emit("已取消，跳过当前进度")
                    self.process_mgr.update_index(
                        i, total, status=ProcessManager.CANCELLED
                    )
                    self.finished.emit("cancelled")
                    return

                images = result.get("images", [])
                info = result.get("info", {})
                seed = info.get("seed", "") if isinstance(info, dict) else ""
                elapsed = result.get("elapsed", 0)
                total_elapsed += elapsed

                elapsed_str = self._format_time(elapsed)
                self.log.emit(f"  seed: {seed} ({elapsed_str})")

                # 生成成功才推进进度
                self.process_mgr.update_index(
                    i + 1,
                    total,
                    status=ProcessManager.GENERATING,
                    result={
                        "index": i,
                        "seed": seed,
                        "state": "completed",
                    },
                )

            except Exception as e:
                # 如果异常是由中断/取消引起的，不推进进度
                if self._interrupted:
                    self.log.emit("已中断")
                    self.process_mgr.update_index(
                        i, total, status=ProcessManager.PAUSED
                    )
                    self.finished.emit("interrupted")
                    return

                if self._cancelled:
                    self.log.emit("已取消")
                    self.process_mgr.update_index(
                        i, total, status=ProcessManager.CANCELLED
                    )
                    self.finished.emit("cancelled")
                    return

                self.log.emit(f"  错误: {e}")
                self.process_mgr.update_index(
                    i + 1,
                    total,
                    status=ProcessManager.GENERATING,
                    result={
                        "index": i,
                        "seed": "",
                        "state": "failed",
                        "error": str(e),
                    },
                )

        self.process_mgr.update_index(
            total, total, status=ProcessManager.COMPLETED
        )
        total_real_elapsed = time.time() - total_start_time
        self.log.emit(
            f"全部完成，共 {total} 张，"
            f"生成耗时 {self._format_time(total_elapsed)}，"
            f"实际耗时 {self._format_time(total_real_elapsed)}"
        )
        self.finished.emit("completed")

    @staticmethod
    def _format_time(seconds):
        if seconds < 60:
            return f"{seconds:.1f}秒"
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}分{secs:.1f}秒"


from scripts.core import ProcessManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        from scripts.config import Config
        from scripts.core import PromptManager, ProcessManager
        from scripts.api_client import WebUIClient

        self.config = Config()
        self.prompt_mgr = PromptManager(self.config)
        self.process_mgr = ProcessManager(self.config)
        self.client = WebUIClient(self.config)
        self.worker = None
        self._current_status = "idle"

        self.setWindowTitle("动态提示词生图工具")
        self.setMinimumSize(750, 780)
        self._init_ui()
        self._load_config_to_ui()
        self._restore_progress()
        self._update_button_states()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        tab_prompts = QWidget()
        tabs.addTab(tab_prompts, "提示词")
        self._build_prompts_tab(tab_prompts)

        tab_params = QWidget()
        tabs.addTab(tab_params, "参数")
        self._build_params_tab(tab_params)

        tab_process = QWidget()
        tabs.addTab(tab_process, "生图")
        self._build_process_tab(tab_process)

        tab_settings = QWidget()
        tabs.addTab(tab_settings, "设置")
        self._build_settings_tab(tab_settings)

    def _build_prompts_tab(self, parent):
        layout = QVBoxLayout(parent)

        grp_template = CollapsibleBox("正向提示词模板")
        self.txt_prompt_template = QPlainTextEdit()
        self.txt_prompt_template.setMaximumHeight(100)
        self.txt_prompt_template.setReadOnly(True)
        grp_template.add_widget(self.txt_prompt_template)
        layout.addWidget(grp_template)

        grp_neg = CollapsibleBox("负向提示词模板")
        self.txt_negative_template = QPlainTextEdit()
        self.txt_negative_template.setMaximumHeight(80)
        self.txt_negative_template.setReadOnly(True)
        grp_neg.add_widget(self.txt_negative_template)
        layout.addWidget(grp_neg)

        grp_gen = QGroupBox("提示词生成")
        gen_layout = QHBoxLayout(grp_gen)
        self.btn_gen_prompts = QPushButton("生成提示词")
        self.btn_gen_prompts.setMinimumWidth(100)
        self.btn_gen_prompts.clicked.connect(self._on_generate_prompts)
        gen_layout.addWidget(self.btn_gen_prompts)

        self.btn_load_prompts = QPushButton("加载已有")
        self.btn_load_prompts.setMinimumWidth(80)
        self.btn_load_prompts.clicked.connect(self._on_load_prompts)
        gen_layout.addWidget(self.btn_load_prompts)

        self.lbl_prompt_count = QLabel("已加载: 0 条")
        gen_layout.addWidget(self.lbl_prompt_count)
        gen_layout.addStretch()
        layout.addWidget(grp_gen)

        grp_list = CollapsibleBox("提示词列表")
        self.txt_prompt_list = QPlainTextEdit()
        self.txt_prompt_list.setReadOnly(True)
        self.txt_prompt_list.setMaximumHeight(200)
        self.txt_prompt_list.setStyleSheet(
            "QPlainTextEdit { font-size: 10px; }"
        )
        grp_list.add_widget(self.txt_prompt_list)
        layout.addWidget(grp_list)

        layout.addStretch()

    def _build_params_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(4, 4, 4, 4)

        self.params_display = QPlainTextEdit()
        self.params_display.setReadOnly(True)
        self.params_display.setStyleSheet(
            "QPlainTextEdit { font-family: Consolas, monospace; font-size: 11px; }"
        )
        layout.addWidget(self.params_display)

    def _build_settings_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── 读取 config.json ──
        grp_config = QGroupBox("配置文件")
        cfg_layout = QVBoxLayout(grp_config)
        cfg_row = QHBoxLayout()
        self.btn_read_config = QPushButton("读取 config.json")
        self.btn_read_config.clicked.connect(self._on_read_config)
        cfg_row.addWidget(self.btn_read_config)
        cfg_row.addStretch()
        cfg_layout.addLayout(cfg_row)
        self.lbl_config_path = QLabel("未选择文件")
        cfg_layout.addWidget(self.lbl_config_path)
        self.txt_config_preview = QPlainTextEdit()
        self.txt_config_preview.setReadOnly(True)
        self.txt_config_preview.setMaximumHeight(150)
        self.txt_config_preview.setStyleSheet(
            "QPlainTextEdit { font-family: Consolas, monospace; font-size: 10px; }"
        )
        cfg_layout.addWidget(self.txt_config_preview)
        layout.addWidget(grp_config)

        # ── 调试区 ──
        grp_debug = QGroupBox("调试")
        debug_layout = QVBoxLayout(grp_debug)
        debug_row = QHBoxLayout()
        self.btn_dump_options = QPushButton("输出当前 WebUI 设置到 debug-opt.json")
        self.btn_dump_options.clicked.connect(self._on_dump_options)
        debug_row.addWidget(self.btn_dump_options)
        debug_row.addStretch()
        debug_layout.addLayout(debug_row)
        self.lbl_debug_result = QLabel("")
        debug_layout.addWidget(self.lbl_debug_result)
        layout.addWidget(grp_debug)

        layout.addStretch()

    def _build_process_tab(self, parent):
        layout = QVBoxLayout(parent)

        grp_seed = QGroupBox("种子控制")
        seed_layout = QVBoxLayout(grp_seed)

        seed_row1 = QHBoxLayout()
        seed_row1.addWidget(QLabel("起始种子:"))
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(-1, 2147483647)
        self.spin_seed.setValue(0)
        self.spin_seed.setMinimumWidth(150)
        seed_row1.addWidget(self.spin_seed)

        self.btn_random_seed = QPushButton("随机")
        self.btn_random_seed.setMinimumWidth(50)
        self.btn_random_seed.clicked.connect(self._on_random_seed)
        seed_row1.addWidget(self.btn_random_seed)

        self.btn_preset_seed = QPushButton("使用预设")
        self.btn_preset_seed.setMinimumWidth(70)
        self.btn_preset_seed.clicked.connect(self._on_preset_seed)
        seed_row1.addWidget(self.btn_preset_seed)

        seed_row1.addStretch()
        seed_layout.addLayout(seed_row1)

        seed_row2 = QHBoxLayout()
        seed_row2.addWidget(QLabel("种子模式:"))
        self.radio_fixed = QRadioButton("固定")
        self.radio_increment = QRadioButton("递增")
        self.radio_fixed.setChecked(True)
        seed_row2.addWidget(self.radio_fixed)
        seed_row2.addWidget(self.radio_increment)
        seed_row2.addStretch()
        seed_layout.addLayout(seed_row2)

        layout.addWidget(grp_seed)

        grp_control = QGroupBox("控制面板")
        ctrl_layout = QHBoxLayout(grp_control)

        self.btn_start = QPushButton("开始生图")
        self.btn_start.setMinimumWidth(90)
        self.btn_start.clicked.connect(self._on_start)
        ctrl_layout.addWidget(self.btn_start)

        self.btn_pause = QPushButton("暂停")
        self.btn_pause.setMinimumWidth(70)
        self.btn_pause.clicked.connect(self._on_pause)
        ctrl_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setMinimumWidth(70)
        self.btn_cancel.clicked.connect(self._on_cancel)
        ctrl_layout.addWidget(self.btn_cancel)

        self.btn_interrupt = QPushButton("中断")
        self.btn_interrupt.setMinimumWidth(70)
        self.btn_interrupt.clicked.connect(self._on_interrupt)
        ctrl_layout.addWidget(self.btn_interrupt)

        self.btn_terminate = QPushButton("终止")
        self.btn_terminate.setMinimumWidth(70)
        self.btn_terminate.clicked.connect(self._on_terminate)
        ctrl_layout.addWidget(self.btn_terminate)

        self.btn_restart = QPushButton("重置进度")
        self.btn_restart.setMinimumWidth(80)
        self.btn_restart.clicked.connect(self._on_restart)
        ctrl_layout.addWidget(self.btn_restart)

        ctrl_layout.addStretch()
        layout.addWidget(grp_control)

        grp_progress = QGroupBox("进度")
        prog_layout = QVBoxLayout(grp_progress)
        self.lbl_status = QLabel("状态: 空闲")
        prog_layout.addWidget(self.lbl_status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)
        prog_index_row = QHBoxLayout()
        self.lbl_progress_index = QLabel("序号: 0 / 0")
        prog_index_row.addWidget(self.lbl_progress_index)
        prog_index_row.addStretch()
        prog_layout.addLayout(prog_index_row)
        layout.addWidget(grp_progress)

        grp_log = QGroupBox("日志")
        log_layout = QVBoxLayout(grp_log)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        log_layout.addWidget(self.txt_log)
        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.clicked.connect(self.txt_log.clear)
        log_layout.addWidget(btn_clear_log)
        layout.addWidget(grp_log)

    def _load_config_to_ui(self):
        template_data = self.prompt_mgr.load_gen_prompt()
        if template_data:
            self.txt_prompt_template.setPlainText(
                template_data.get("prompt", "")
            )
            self.txt_negative_template.setPlainText(
                template_data.get("negative_prompt", "")
            )

        gen_para = self.prompt_mgr.load_gen_para()
        if gen_para:
            self.params_display.setPlainText(json.dumps(gen_para, ensure_ascii=False, indent=2))
            seed = gen_para.get("seed", -1)
            self.spin_seed.setValue(seed)

        self._refresh_prompt_count()
        self._refresh_prompt_list()

    def _refresh_prompt_count(self):
        prompts = self.prompt_mgr.load_prompts()
        count = len(prompts)
        self.lbl_prompt_count.setText(f"已加载: {count} 条")
        return count

    def _refresh_prompt_list(self):
        prompts = self.prompt_mgr.load_prompts()
        if not prompts:
            self.txt_prompt_list.setPlainText("(无)")
            return
        lines = []
        for i, p in enumerate(prompts):
            text = p.get("prompt", "")
            short = text[:80] + "..." if len(text) > 80 else text
            lines.append(f"[{i + 1}] {short}")
        self.txt_prompt_list.setPlainText("\n".join(lines))

    def _restore_progress(self):
        if self.process_mgr.can_resume():
            data = self.process_mgr.load()
            idx = data["current_index"]
            total = data["total_count"]
            status = data["status"]
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(idx)
            self.lbl_progress_index.setText(f"序号: {idx} / {total}")
            self._log(f"检测到未完成进度: {idx}/{total} (状态: {status})")
            self._log("点击\"开始生图\"可继续")

    def _log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.appendPlainText(f"[{timestamp}] {msg}")

    def _set_status(self, text):
        self._current_status = text
        self.lbl_status.setText(f"状态: {text}")
        self._update_button_states()

    def _update_button_states(self):
        s = self._current_status
        self.btn_start.setEnabled(s in ("idle", "paused"))
        self.btn_pause.setEnabled(s == "generating")
        self.btn_cancel.setEnabled(s in ("generating", "paused"))
        self.btn_interrupt.setEnabled(s == "generating")
        self.btn_terminate.setEnabled(s in ("generating", "paused"))
        self.btn_restart.setEnabled(s not in ("generating",))
        self.btn_gen_prompts.setEnabled(s in ("idle", "completed"))

    @Slot()
    def _on_read_config(self):
        """选择并读取 config.json 文件，并应用到当前配置。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 config.json",
            str(self.config.proj_dir),
            "JSON 文件 (*.json);;所有文件 (*)",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 应用配置
            self.config.load_from_path(file_path)
            # 刷新 UI
            self._load_config_to_ui()
            self._restore_progress()
            self._update_button_states()
            self.lbl_config_path.setText(f"已应用: {file_path}")
            self.txt_config_preview.setPlainText(
                json.dumps(data, ensure_ascii=False, indent=2)
            )
            self._log(f"已读取并应用配置文件: {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"无法读取配置文件:\n{e}")

    @Slot()
    def _on_dump_options(self):
        """将 WebUI 当前设置导出到脚本所在目录的 debug-opt.json。"""
        try:
            target = Path(__file__).resolve().parent / "debug-opt.json"
            saved = self.client.dump_options_to_file(target)
            self.lbl_debug_result.setText(f"已保存: {saved}")
            self._log(f"已导出 WebUI 设置到: {saved}")
        except Exception as e:
            self.lbl_debug_result.setText(f"导出失败: {e}")
            QMessageBox.warning(self, "导出失败", str(e))

    @Slot()
    def _on_random_seed(self):
        import random
        self.spin_seed.setValue(random.randint(0, 2147483647))

    @Slot()
    def _on_preset_seed(self):
        gen_para = self.prompt_mgr.load_gen_para()
        if gen_para:
            self.spin_seed.setValue(gen_para.get("seed", -1))

    @Slot()
    def _on_generate_prompts(self):
        try:
            prompts = self.prompt_mgr.generate_prompts()
            self._log(f"已生成 {len(prompts)} 条提示词")
            self._refresh_prompt_count()
            self._refresh_prompt_list()
            self.process_mgr.reset()
            self._set_status("idle")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"生成提示词失败:\n{e}")

    @Slot()
    def _on_load_prompts(self):
        prompts = self.prompt_mgr.load_prompts()
        if prompts:
            self._log(f"已加载 {len(prompts)} 条提示词")
            self._refresh_prompt_count()
            self._refresh_prompt_list()
        else:
            self._log("没有找到已保存的提示词")

    @Slot()
    def _on_start(self):
        prompts = self.prompt_mgr.load_prompts()
        if not prompts:
            QMessageBox.information(self, "提示", "请先生成或加载提示词")
            return

        if not self.client.is_connected():
            QMessageBox.warning(
                self,
                "连接失败",
                f"无法连接到 WebUI API ({self.config.api_url})",
            )
            return

        gen_para = self.prompt_mgr.load_gen_para()
        if not gen_para:
            QMessageBox.warning(self, "错误", "无法读取生成参数")
            return

        seed_mode = "increment" if self.radio_increment.isChecked() else "fixed"
        seed_value = self.spin_seed.value()

        self.worker = GenerateWorker(
            self.client, gen_para, prompts, self.process_mgr,
            seed_mode, seed_value,
        )
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)

        self._set_status("generating")
        self._log("开始生图...")
        self.worker.start()

    @Slot()
    def _on_pause(self):
        if self.worker:
            self.worker.pause()
            self._log("正在暂停...")

    @Slot()
    def _on_cancel(self):
        if self.worker:
            reply = QMessageBox.question(
                self,
                "确认取消",
                "确定要取消吗？进度将被清空。",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                self._log("正在取消...")

    @Slot()
    def _on_interrupt(self):
        if self.worker:
            self.worker.interrupt()
            self._log("正在中断...")

    @Slot()
    def _on_terminate(self):
        if self.worker:
            reply = QMessageBox.question(
                self,
                "确认终止",
                "确定要终止吗？将立即停止并清空进度。",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                self.process_mgr.reset()
                self._log("已终止并清空进度")

    @Slot()
    def _on_restart(self):
        if self.worker:
            reply = QMessageBox.question(
                self,
                "确认重置进度",
                "正在生图中，确定要重置进度吗？当前进度将丢失。",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            self.worker.cancel()
            self.worker = None
        self.process_mgr.reset()
        self.progress_bar.setValue(0)
        self.lbl_progress_index.setText("序号: 0 / 0")
        self._set_status("idle")
        self._log("已重置进度, 可重新开始")

    @Slot(int, int, str)
    def _on_progress(self, current, total, status):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.lbl_status.setText(f"状态: 生成中 ({current}/{total})")
        self.lbl_progress_index.setText(f"序号: {current} / {total}")

    @Slot(str)
    def _on_finished(self, result):
        self.worker = None
        if result == "completed":
            self._set_status("completed")
            total = self.progress_bar.maximum()
            self.progress_bar.setValue(total)
            self.lbl_progress_index.setText(f"序号: {total} / {total}")
            self.process_mgr.reset()
            self._log("进度完成，已清理 process.json")
        elif result == "paused":
            self._set_status("paused")
        elif result in ("cancelled", "interrupted"):
            self._set_status("idle")
            self.progress_bar.setValue(0)
        else:
            self._set_status("idle")
