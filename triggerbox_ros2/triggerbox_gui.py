#!/usr/bin/env python3
"""Small Qt GUI for triggerbox_ros2.

Drop into triggerbox_ros2/triggerbox_ros2/triggerbox_gui.py and add a
console_scripts entry point:

    triggerbox_gui = triggerbox_ros2.triggerbox_gui:main

Run with:

    ros2 run triggerbox_ros2 triggerbox_gui

This intentionally talks to the host over normal ROS 2 topics/services instead
of importing TriggerboxClient, so it can control any already-running host node.
"""

import datetime as _dt
import glob
import os
import signal
import sys
from typing import Dict, List, Optional, Tuple

import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool, Float32
from std_srvs.srv import SetBool, Trigger

from triggerbox_ros2_interfaces.msg import TriggerClockMeasurement, TriggerClockModel
from triggerbox_ros2_interfaces.srv import SetFramerate

from PyQt5.QtCore import QObject, QProcess, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


SET_FRAMERATE_TYPE = "triggerbox_ros2_interfaces/srv/SetFramerate"
TRIGGER_TYPE = "std_srvs/srv/Trigger"
SET_BOOL_TYPE = "std_srvs/srv/SetBool"


class GuiSignals(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    fps_seen = pyqtSignal(float)
    output_enabled_seen = pyqtSignal(bool)


class TriggerboxGuiNode(Node):
    """ROS side of the GUI.

    Discovers hosts by looking for */set_framerate services, then attaches to
    the selected host's telemetry topics and command services.
    """

    def __init__(self, signals: GuiSignals):
        super().__init__("triggerbox_gui")
        self.signals = signals
        self._base: Optional[str] = None
        self._gui_subscriptions = []
        self._pause_publishers: Dict[str, object] = {}
        self._gui_service_clients: Dict[Tuple[str, object, str], object] = {}
        self._last_raw_pulse: Optional[int] = None

    @staticmethod
    def _join(base: str, leaf: str) -> str:
        return base.rstrip("/") + "/" + leaf.lstrip("/")

    def find_triggerbox_bases(self) -> List[str]:
        bases = []
        for name, types in self.get_service_names_and_types():
            if name.endswith("/set_framerate") and SET_FRAMERATE_TYPE in types:
                bases.append(name[: -len("/set_framerate")])
        return sorted(set(bases))

    def select_base(self, base: Optional[str]) -> None:
        if base == self._base:
            return
        for sub in self._gui_subscriptions:
            self.destroy_subscription(sub)
        self._gui_subscriptions = []
        self._last_raw_pulse = None
        self._base = base
        if not base:
            self.signals.status.emit("No triggerbox selected")
            return

        self._gui_subscriptions.append(
            self.create_subscription(
                TriggerClockModel,
                self._join(base, "time_model"),
                self._on_time_model,
                10,
            )
        )
        self._gui_subscriptions.append(
            self.create_subscription(
                Float32,
                self._join(base, "expected_framerate"),
                self._on_expected_framerate,
                10,
            )
        )
        self._gui_subscriptions.append(
            self.create_subscription(
                Bool,
                self._join(base, "output_enabled"),
                self._on_output_enabled,
                10,
            )
        )
        self._gui_subscriptions.append(
            self.create_subscription(
                TriggerClockMeasurement,
                self._join(base, "raw_measurements"),
                self._on_raw_measurement,
                10,
            )
        )
        self.signals.status.emit(f"Attached to {base}")
        self.signals.log.emit(f"Attached to {base}")

    def _client(self, srv_type, service_name: str):
        if not self._base:
            self.signals.log.emit("No triggerbox host selected")
            return None
        key = (self._base, srv_type, service_name)
        if key not in self._gui_service_clients:
            self._gui_service_clients[key] = self.create_client(srv_type, self._join(self._base, service_name))
        return self._gui_service_clients[key]

    def call_set_framerate(self, fps: float) -> None:
        client = self._client(SetFramerate, "set_framerate")
        if client is None:
            return
        if not client.service_is_ready():
            self.signals.log.emit(f"Waiting for {client.srv_name} ...")
        req = SetFramerate.Request()
        req.data = float(fps)
        future = client.call_async(req)
        future.add_done_callback(lambda fut: self._log_future(fut, f"set_framerate {fps:g} Hz"))
        self.signals.log.emit(f"Requested FPS {fps:g}")

    def call_set_output_enabled(self, enabled: bool) -> None:
        client = self._client(SetBool, "set_output_enabled")
        if client is None:
            return
        req = SetBool.Request()
        req.data = bool(enabled)
        future = client.call_async(req)
        future.add_done_callback(
            lambda fut: self._log_future(fut, f"set_output_enabled {bool(enabled)}")
        )
        self.signals.log.emit(f"Requested physical trigger output enabled={bool(enabled)}")

    def call_trigger_service(self, service_name: str) -> None:
        client = self._client(Trigger, service_name)
        if client is None:
            return
        future = client.call_async(Trigger.Request())
        future.add_done_callback(lambda fut: self._log_future(fut, service_name))
        self.signals.log.emit(f"Requested {service_name}")

    def publish_pause_and_reset(self, seconds: float) -> None:
        if not self._base:
            self.signals.log.emit("No triggerbox host selected")
            return
        topic = self._join(self._base, "pause_and_reset")
        if topic not in self._pause_publishers:
            self._pause_publishers[topic] = self.create_publisher(Float32, topic, 10)
        msg = Float32()
        msg.data = float(seconds)
        self._pause_publishers[topic].publish(msg)
        self.signals.log.emit(f"Published pause_and_reset {seconds:g} s")

    def _log_future(self, future, action: str) -> None:
        try:
            response = future.result()
        except Exception as exc:  # noqa: BLE001, GUI should show everything useful
            self.signals.log.emit(f"{action} FAILED: {exc!r}")
            return

        # std_srvs responses have success/message. The custom set_framerate
        # response may be empty, depending on the srv definition.
        success = getattr(response, "success", None)
        message = getattr(response, "message", "")
        if success is None:
            self.signals.log.emit(f"{action} complete")
        else:
            self.signals.log.emit(f"{action}: success={success} {message}")

    def _on_time_model(self, msg: TriggerClockModel) -> None:
        if msg.gain != msg.gain or msg.offset != msg.offset:  # NaN check without numpy
            self.signals.status.emit("Clock model reset / waiting for estimate")
            self.signals.log.emit("Clock model reset / waiting for estimate")
            return
        approx_fps = 1.0 / msg.gain if msg.gain else float("nan")
        self.signals.status.emit(
            f"Clock model OK: gain={msg.gain:.9g}, offset={msg.offset:.3f}, approx={approx_fps:.3f} Hz"
        )
        self.signals.log.emit(
            f"Clock model: gain={msg.gain:.9g}, offset={msg.offset:.3f}, approx={approx_fps:.3f} Hz"
        )

    def _on_expected_framerate(self, msg: Float32) -> None:
        self.signals.fps_seen.emit(float(msg.data))
        self.signals.log.emit(f"Expected FPS: {float(msg.data):.6g}")

    def _on_output_enabled(self, msg: Bool) -> None:
        self.signals.output_enabled_seen.emit(bool(msg.data))
        self.signals.log.emit(f"Physical trigger output enabled: {bool(msg.data)}")

    def _on_raw_measurement(self, msg: TriggerClockMeasurement) -> None:
        # Raw measurements can be chatty. Log pulse progress, but skip duplicates.
        if msg.pulsenumber == self._last_raw_pulse:
            return
        self._last_raw_pulse = msg.pulsenumber
        self.signals.log.emit(
            f"Raw clock: pulse={msg.pulsenumber} frac={msg.fraction_n_of_255}/255 "
            f"roundtrip={(msg.stop_timestamp - msg.start_timestamp) * 1e3:.2f} ms"
        )


class TriggerboxGui(QMainWindow):
    def __init__(self, node: TriggerboxGuiNode, signals: GuiSignals):
        super().__init__()
        self.node = node
        self.signals = signals
        self.host_process: Optional[QProcess] = None
        self.host_pid: Optional[int] = None

        self.setWindowTitle("triggerbox_ros2 GUI")
        self.resize(980, 680)

        root = QWidget()
        outer = QVBoxLayout(root)
        self.setCentralWidget(root)

        top = QHBoxLayout()
        outer.addLayout(top)

        hosts_box = QGroupBox("Running triggerbox hosts")
        hosts_layout = QVBoxLayout(hosts_box)
        self.host_list = QListWidget()
        hosts_layout.addWidget(self.host_list)
        refresh_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.selected_label = QLabel("Selected: none")
        refresh_row.addWidget(self.refresh_button)
        refresh_row.addWidget(self.selected_label, stretch=1)
        hosts_layout.addLayout(refresh_row)
        top.addWidget(hosts_box, stretch=1)

        controls_box = QGroupBox("Controls")
        controls = QGridLayout(controls_box)
        row = 0

        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.0, 2000.0)
        self.fps_spin.setDecimals(3)
        self.fps_spin.setSingleStep(25.0)
        self.fps_spin.setValue(250.0)
        self.set_fps_button = QPushButton("Set FPS")
        controls.addWidget(QLabel("FPS"), row, 0)
        controls.addWidget(self.fps_spin, row, 1)
        controls.addWidget(self.set_fps_button, row, 2)
        row += 1

        preset_row = QHBoxLayout()
        for fps in (25, 50, 100, 125, 200, 250, 500):
            b = QPushButton(str(fps))
            b.clicked.connect(lambda _checked=False, value=fps: self._set_fps_preset(value))
            preset_row.addWidget(b)
        controls.addWidget(QLabel("Presets"), row, 0)
        controls.addLayout(preset_row, row, 1, 1, 2)
        row += 1

        self.enable_button = QPushButton("Enable physical output")
        self.disable_button = QPushButton("Disable physical output")
        controls.addWidget(self.enable_button, row, 0, 1, 2)
        controls.addWidget(self.disable_button, row, 2)
        row += 1

        self.start_clock_button = QPushButton("Start clock")
        self.stop_clock_button = QPushButton("Stop clock")
        controls.addWidget(self.start_clock_button, row, 0, 1, 2)
        controls.addWidget(self.stop_clock_button, row, 2)
        row += 1

        self.pause_seconds = QDoubleSpinBox()
        self.pause_seconds.setRange(0.0, 60.0)
        self.pause_seconds.setDecimals(2)
        self.pause_seconds.setValue(2.0)
        self.pause_reset_button = QPushButton("Pause + reset")
        controls.addWidget(QLabel("Pause seconds"), row, 0)
        controls.addWidget(self.pause_seconds, row, 1)
        controls.addWidget(self.pause_reset_button, row, 2)
        row += 1

        self.live_fps_label = QLabel("Expected FPS: unknown")
        self.output_label = QLabel("Output: unknown")
        self.status_label = QLabel("Clock model: waiting")
        controls.addWidget(self.live_fps_label, row, 0, 1, 3)
        row += 1
        controls.addWidget(self.output_label, row, 0, 1, 3)
        row += 1
        controls.addWidget(self.status_label, row, 0, 1, 3)
        row += 1

        top.addWidget(controls_box, stretch=2)

        launch_box = QGroupBox("Start a triggerbox_host")
        launch = QGridLayout(launch_box)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.refresh_ports_button = QPushButton("Scan ports")
        self.start_host_button = QPushButton("Start host")
        self.stop_host_button = QPushButton("Stop GUI-launched host")
        self.start_enabled_check = QCheckBox("Enable physical output on start")
        self.default_fps_spin = QDoubleSpinBox()
        self.default_fps_spin.setRange(0.0, 2000.0)
        self.default_fps_spin.setDecimals(3)
        self.default_fps_spin.setSingleStep(25.0)
        self.default_fps_spin.setValue(250.0)
        launch.addWidget(QLabel("Serial port"), 0, 0)
        launch.addWidget(self.port_combo, 0, 1)
        launch.addWidget(self.refresh_ports_button, 0, 2)
        launch.addWidget(QLabel("Default FPS"), 1, 0)
        launch.addWidget(self.default_fps_spin, 1, 1)
        launch.addWidget(self.start_enabled_check, 1, 2)
        launch.addWidget(self.start_host_button, 2, 0, 1, 2)
        launch.addWidget(self.stop_host_button, 2, 2)
        outer.addWidget(launch_box)

        console_box = QGroupBox("Console")
        console_layout = QVBoxLayout(console_box)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(2000)
        console_layout.addWidget(self.console)
        outer.addWidget(console_box, stretch=1)

        self.refresh_button.clicked.connect(self.refresh_hosts)
        self.host_list.currentItemChanged.connect(self._host_selection_changed)
        self.set_fps_button.clicked.connect(lambda: self.node.call_set_framerate(self.fps_spin.value()))
        self.enable_button.clicked.connect(lambda: self.node.call_set_output_enabled(True))
        self.disable_button.clicked.connect(lambda: self.node.call_set_output_enabled(False))
        self.start_clock_button.clicked.connect(lambda: self.node.call_trigger_service("start_clock"))
        self.stop_clock_button.clicked.connect(lambda: self.node.call_trigger_service("stop_clock"))
        self.pause_reset_button.clicked.connect(
            lambda: self.node.publish_pause_and_reset(self.pause_seconds.value())
        )
        self.refresh_ports_button.clicked.connect(self.refresh_ports)
        self.start_host_button.clicked.connect(self.start_host)
        self.stop_host_button.clicked.connect(self.stop_host)

        self.signals.log.connect(self.log)
        self.signals.status.connect(self.status_label.setText)
        self.signals.fps_seen.connect(lambda fps: self.live_fps_label.setText(f"Expected FPS: {fps:.6g}"))
        self.signals.output_enabled_seen.connect(
            lambda enabled: self.output_label.setText(f"Output: {'ENABLED' if enabled else 'disabled'}")
        )

        self.refresh_ports()
        self.refresh_hosts()

        self.host_refresh_timer = QTimer(self)
        self.host_refresh_timer.timeout.connect(self.refresh_hosts)
        self.host_refresh_timer.start(2000)

    def _timestamp(self) -> str:
        return _dt.datetime.now().strftime("%H:%M:%S")

    def log(self, text: str) -> None:
        self.console.appendPlainText(f"[{self._timestamp()}] {text}")

    def refresh_ports(self) -> None:
        current = self.port_combo.currentText().strip()

        detected = []
        for pattern in ("/dev/trig*", "/dev/ttyACM*", "/dev/ttyUSB*"):
            detected.extend(glob.glob(pattern))
        detected = sorted(set(detected))

        # Keep common fallback names editable/visible, but do not prefer a
        # nonexistent default over a real detected device. This matters when
        # udev creates /dev/trig1 today and /dev/trig2 on another rig.
        defaults = ["/dev/trig1", "/dev/trig2", "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"]
        ports = []
        for port in detected + defaults:
            if port not in ports:
                ports.append(port)

        self.port_combo.clear()
        self.port_combo.addItems(ports)

        current_exists = bool(current and os.path.exists(current))
        if current_exists:
            idx = self.port_combo.findText(current)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
            else:
                self.port_combo.setEditText(current)
        elif detected:
            self.port_combo.setCurrentText(detected[0])
        elif current:
            self.port_combo.setEditText(current)
        elif ports:
            self.port_combo.setCurrentText(ports[0])

        self.log("Serial ports: " + (", ".join(detected) if detected else "no detected /dev/trig*, /dev/ttyACM*, or /dev/ttyUSB* devices"))

    def refresh_hosts(self) -> None:
        if not rclpy.ok():
            return
        previous = self.host_list.currentItem().text() if self.host_list.currentItem() else None
        try:
            bases = self.node.find_triggerbox_bases()
        except Exception as exc:  # noqa: BLE001
            # This can happen briefly during shutdown if Qt fires a timer after
            # the ROS context has been invalidated. Do not let it explode the GUI.
            self.log(f"Could not refresh triggerbox hosts: {exc!r}")
            return
        current_items = [self.host_list.item(i).text() for i in range(self.host_list.count())]
        if bases == current_items:
            return
        self.host_list.clear()
        for base in bases:
            self.host_list.addItem(QListWidgetItem(base))
        if previous in bases:
            self.host_list.setCurrentRow(bases.index(previous))
        elif bases:
            self.host_list.setCurrentRow(0)
        else:
            self.node.select_base(None)
            self.selected_label.setText("Selected: none")

    def _host_selection_changed(self, current: Optional[QListWidgetItem], previous) -> None:
        del previous
        base = current.text() if current is not None else None
        self.selected_label.setText(f"Selected: {base or 'none'}")
        self.node.select_base(base)

    def _set_fps_preset(self, fps: float) -> None:
        self.fps_spin.setValue(float(fps))
        self.node.call_set_framerate(float(fps))

    def start_host(self) -> None:
        if self.host_process is not None and self.host_process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "triggerbox_host already running", "This GUI already launched a host process.")
            return

        port = self.port_combo.currentText().strip()
        fps = self.default_fps_spin.value()
        output_on_start = "true" if self.start_enabled_check.isChecked() else "false"

        # Start the Python entrypoint directly rather than shelling through
        # `ros2 run`. That makes the actual triggerbox_host the direct child of
        # the GUI, so Stop can signal the right PID and cannot accidentally send
        # SIGINT to the GUI's own terminal/process group.
        args = [
            "-m",
            "triggerbox_ros2.triggerbox_host",
            "--device",
            port,
            "--ros-args",
            "-p",
            f"default_fps:={fps}",
            "-p",
            f"output_enabled_on_start:={output_on_start}",
        ]

        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setArguments(args)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.started.connect(self._on_host_started)
        proc.readyReadStandardOutput.connect(self._read_host_output)
        proc.finished.connect(self._on_host_finished)
        proc.errorOccurred.connect(lambda err: self.log(f"triggerbox_host process error: {err}"))
        self.host_process = proc
        self.host_pid = None
        self.log("Starting: " + sys.executable + " " + " ".join(args))
        proc.start()

    def _read_host_output(self) -> None:
        if self.host_process is None:
            return
        data = bytes(self.host_process.readAllStandardOutput()).decode(errors="replace")
        for line in data.rstrip().splitlines():
            self.log("host | " + line)

    def _on_host_started(self) -> None:
        if self.host_process is None:
            return
        self.host_pid = int(self.host_process.processId())
        self.log(f"triggerbox_host process started: pid={self.host_pid}")

    def _on_host_finished(self, code: int, status) -> None:
        self.log(f"triggerbox_host exited: code={code} status={status}")
        self.host_pid = None

    def _host_process_alive(self) -> bool:
        if self.host_process is not None and self.host_process.state() != QProcess.NotRunning:
            return True
        if self.host_pid is None:
            return False
        try:
            os.kill(self.host_pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception as exc:  # noqa: BLE001
            self.log(f"Could not check triggerbox_host pid {self.host_pid}: {exc!r}")
            return False

    def _signal_host_process(self, sig: int) -> None:
        if self.host_pid is not None and self.host_pid != os.getpid():
            try:
                os.kill(self.host_pid, sig)
                self.log(f"Sent {signal.Signals(sig).name} to triggerbox_host pid {self.host_pid}")
                return
            except ProcessLookupError:
                self.log(f"triggerbox_host pid {self.host_pid} is already gone")
                self.host_pid = None
                return
            except Exception as exc:  # noqa: BLE001
                self.log(f"Could not signal pid {self.host_pid}: {exc!r}; falling back to QProcess")

        if self.host_process is not None and self.host_process.state() != QProcess.NotRunning:
            if sig == signal.SIGKILL:
                self.host_process.kill()
            else:
                self.host_process.terminate()

    def stop_host(self) -> None:
        if not self._host_process_alive():
            self.log("No GUI-launched triggerbox_host process to stop")
            return

        self.log("Stopping GUI-launched triggerbox_host: disabling output, stopping clock, then signaling host process")
        self.node.call_set_output_enabled(False)
        self.node.call_trigger_service("stop_clock")
        QTimer.singleShot(500, lambda: self._signal_host_process(signal.SIGINT))
        QTimer.singleShot(2500, self._terminate_host_if_needed)
        QTimer.singleShot(4500, self._kill_host_if_needed)

    def _terminate_host_if_needed(self) -> None:
        if self._host_process_alive():
            self.log("triggerbox_host still alive after SIGINT; sending SIGTERM")
            self._signal_host_process(signal.SIGTERM)

    def _kill_host_if_needed(self) -> None:
        if self._host_process_alive():
            self.log("triggerbox_host still alive after SIGTERM; sending SIGKILL")
            self._signal_host_process(signal.SIGKILL)
        else:
            self.host_pid = None
            self.refresh_hosts()

    def closeEvent(self, event):
        if self.host_process is not None and self.host_process.state() != QProcess.NotRunning:
            self.node.call_set_output_enabled(False)
            self.node.call_trigger_service("stop_clock")
            self._signal_host_process(signal.SIGINT)
            if not self.host_process.waitForFinished(1500):
                self._signal_host_process(signal.SIGTERM)
            if not self.host_process.waitForFinished(1000):
                self._signal_host_process(signal.SIGKILL)
        super().closeEvent(event)


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    rclpy.init(args=argv)
    app = QApplication(argv)
    signals = GuiSignals()
    node = TriggerboxGuiNode(signals)
    window = TriggerboxGui(node, signals)

    # Let Qt own the main loop. Spin ROS frequently without a second thread.
    spin_timer = QTimer()
    spin_timer.timeout.connect(lambda: rclpy.spin_once(node, timeout_sec=0.0) if rclpy.ok() else None)
    spin_timer.start(20)

    window.show()
    try:
        rc = app.exec_()
    finally:
        spin_timer.stop()
        node.destroy_node()
        rclpy.shutdown()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
