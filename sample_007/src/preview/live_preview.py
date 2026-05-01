from collections import defaultdict, deque
from dataclasses import dataclass
import threading
import time
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class PreviewItem:
    modality: str
    payload: dict[str, Any]
    updated_at: float


class LivePreview:
    """Low-overhead GUI preview for NI and Audio waveforms."""

    def __init__(
        self,
        stop_event: threading.Event,
        render_interval_sec: float = 1.0,
    ):
        self._stop_event = stop_event
        self._local_stop_event = threading.Event()
        self._render_interval_sec = render_interval_sec

        self._lock = threading.Lock()
        self._latest: dict[str, PreviewItem] = {}
        self._last_publish_perf: dict[str, float] = defaultdict(float)
        self._ni_histories: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=120))
        self._audio_waveform: deque[float] = deque(maxlen=240)

        self._preview_enabled = True
        self._modality_enabled: dict[str, bool] = defaultdict(lambda: True)

        self._render_thread: threading.Thread | None = None
        self._window_open = False
        self._window_name = "Live Preview (NI / Audio)"

    def start(self) -> None:
        self._render_thread = threading.Thread(target=self._render_loop, name="PreviewRender", daemon=True)
        self._render_thread.start()
        print("[Preview GUI] Controls (window focus): v=show/hide, n=NI on/off, a=Audio on/off, q=stop")

    def stop(self) -> None:
        self._local_stop_event.set()

    def join(self) -> None:
        if self._render_thread is not None:
            self._render_thread.join(timeout=1.0)

    def publish(
        self,
        modality: str,
        payload: dict[str, Any],
        min_interval_sec: float,
    ) -> None:
        now = time.perf_counter()
        with self._lock:
            elapsed = now - self._last_publish_perf[modality]
            if elapsed < min_interval_sec:
                return

            self._last_publish_perf[modality] = now
            self._latest[modality] = PreviewItem(
                modality=modality,
                payload=payload,
                updated_at=time.time(),
            )
            self._ingest_for_graph(modality, payload)

    def _ingest_for_graph(self, modality: str, payload: dict[str, Any]) -> None:
        if modality == "ni":
            channel_names = payload.get("channel_names", [])
            values = payload.get("values", [])
            for channel_name, value in zip(channel_names, values):
                self._ni_histories[str(channel_name)].append(float(value))
            return

        if modality == "audio":
            waveform = payload.get("waveform", [])
            if waveform:
                self._audio_waveform.extend(float(v) for v in waveform)

    def _should_stop(self) -> bool:
        return self._local_stop_event.is_set() or self._stop_event.is_set()

    def _handle_key(self, key: str) -> None:
        if key == "v":
            with self._lock:
                self._preview_enabled = not self._preview_enabled
                enabled = self._preview_enabled
            print(f"[Preview GUI] {'ON' if enabled else 'OFF'}")
            return

        if key == "q":
            print("[Preview GUI] Requested stop.")
            self._stop_event.set()
            return

        modality_keys = {
            "n": "ni",
            "a": "audio",
        }
        modality = modality_keys.get(key)
        if modality is None:
            return

        with self._lock:
            self._modality_enabled[modality] = not self._modality_enabled[modality]
            enabled = self._modality_enabled[modality]
        print(f"[Preview GUI] {modality} {'ON' if enabled else 'OFF'}")

    def _render_loop(self) -> None:
        while not self._should_stop():
            started_at = time.perf_counter()
            with self._lock:
                if not self._preview_enabled:
                    snapshot = None
                else:
                    snapshot = dict(self._latest)
                    enabled = dict(self._modality_enabled)

            if snapshot is not None:
                frame = self._build_frame(snapshot, enabled)
                cv2.imshow(self._window_name, frame)
                self._window_open = True
                key = cv2.waitKey(1) & 0xFF
                if key != 255:
                    self._handle_key(chr(key).lower())
            else:
                if self._window_open:
                    cv2.destroyWindow(self._window_name)
                    self._window_open = False
                time.sleep(0.05)

            elapsed = time.perf_counter() - started_at
            rest = self._render_interval_sec - elapsed
            if rest > 0:
                time.sleep(rest)

        if self._window_open:
            cv2.destroyWindow(self._window_name)
            self._window_open = False

    def _build_frame(self, snapshot: dict[str, PreviewItem], enabled: dict[str, bool]) -> np.ndarray:
        width, height = 1200, 760
        frame = np.full((height, width, 3), 250, dtype=np.uint8)

        cv2.putText(
            frame,
            "Live Preview (v:show/hide, n:NI, a:Audio, q:stop)",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (30, 30, 30),
            2,
            cv2.LINE_AA,
        )

        self._draw_ni_panel(frame, snapshot.get("ni"), enabled.get("ni", True), (20, 60, width - 40, 420))
        self._draw_audio_panel(frame, snapshot.get("audio"), enabled.get("audio", True), (20, 500, width - 40, 230))
        return frame

    def _draw_ni_panel(
        self,
        frame: np.ndarray,
        item: PreviewItem | None,
        is_enabled: bool,
        rect: tuple[int, int, int, int],
    ) -> None:
        x, y, w, h = rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (190, 190, 190), 1)
        cv2.putText(frame, "NI Waveforms", (x + 10, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30, 30, 30), 2)

        if not is_enabled:
            cv2.putText(frame, "disabled", (x + 10, y + 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 100), 1)
            return
        if item is None:
            cv2.putText(frame, "waiting data", (x + 10, y + 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 100), 1)
            return

        channel_names = list(item.payload.get("channel_names", []))
        values = list(item.payload.get("values", []))
        if not channel_names:
            return

        rows, cols = 3, 3
        plot_top = y + 36
        plot_height = h - 46
        cell_w = w // cols
        cell_h = max(1, plot_height // rows)

        for idx, name in enumerate(channel_names[: rows * cols]):
            row = idx // cols
            col = idx % cols
            cx = x + col * cell_w
            cy = plot_top + row * cell_h
            cw = cell_w - 8
            ch = cell_h - 10
            self._draw_wave_box(
                frame=frame,
                box=(cx + 4, cy + 4, cw, ch),
                values=list(self._ni_histories.get(str(name), [])),
                title=f"{name} {values[idx]:+.3f}" if idx < len(values) else str(name),
                color=(65, 105, 225),
            )

    def _draw_audio_panel(
        self,
        frame: np.ndarray,
        item: PreviewItem | None,
        is_enabled: bool,
        rect: tuple[int, int, int, int],
    ) -> None:
        x, y, w, h = rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (190, 190, 190), 1)
        cv2.putText(frame, "Audio Waveform", (x + 10, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30, 30, 30), 2)

        if not is_enabled:
            cv2.putText(frame, "disabled", (x + 10, y + 54), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 100), 1)
            return
        if item is None:
            cv2.putText(frame, "waiting data", (x + 10, y + 54), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 100), 1)
            return

        rms = item.payload.get("rms", [])
        peak = item.payload.get("peak", [])
        status = " ".join(
            [f"RMS ch{i}:{val:.1f}" for i, val in enumerate(rms)]
            + [f"Peak ch{i}:{val:.1f}" for i, val in enumerate(peak)]
        )
        cv2.putText(frame, status[:140], (x + 10, y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (50, 50, 50), 1)

        self._draw_wave_box(
            frame=frame,
            box=(x + 8, y + 62, w - 16, h - 72),
            values=list(self._audio_waveform),
            title="mono preview",
            color=(46, 139, 87),
        )

    @staticmethod
    def _draw_wave_box(
        frame: np.ndarray,
        box: tuple[int, int, int, int],
        values: list[float],
        title: str,
        color: tuple[int, int, int],
    ) -> None:
        x, y, w, h = box
        if w < 4 or h < 4:
            return

        cv2.rectangle(frame, (x, y), (x + w, y + h), (210, 210, 210), 1)
        cv2.putText(frame, title, (x + 6, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (40, 40, 40), 1)

        plot_x, plot_y = x + 6, y + 24
        plot_w, plot_h = w - 12, h - 30
        if plot_w < 4 or plot_h < 4:
            return

        cv2.line(
            frame,
            (plot_x, plot_y + plot_h // 2),
            (plot_x + plot_w, plot_y + plot_h // 2),
            (225, 225, 225),
            1,
        )

        if len(values) < 2:
            return

        arr = np.asarray(values, dtype=np.float32)
        v_min = float(arr.min())
        v_max = float(arr.max())
        if abs(v_max - v_min) < 1e-12:
            arr = arr - v_min
            v_min, v_max = -1.0, 1.0

        if arr.size > plot_w:
            idx = np.linspace(0, arr.size - 1, plot_w).astype(np.int32)
            arr = arr[idx]

        y_norm = (arr - v_min) / (v_max - v_min)
        pts_x = np.linspace(plot_x, plot_x + plot_w - 1, arr.size).astype(np.int32)
        pts_y = (plot_y + (1.0 - y_norm) * (plot_h - 1)).astype(np.int32)
        pts = np.stack([pts_x, pts_y], axis=1).reshape(-1, 1, 2)
        cv2.polylines(frame, [pts], isClosed=False, color=color, thickness=1, lineType=cv2.LINE_AA)
