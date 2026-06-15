import multiprocessing as mp
import queue

from src.plot.live_plotter import run_live_plot


def start_live_plot_process(
    enabled: bool,
    channel_labels: list[str],
    plot_groups: list[tuple[str, list[int]]],
    title: str,
    window_seconds: float = 5.0,
    queue_maxsize: int = 1,
    y_limits: tuple[float, float] | None = None,
    y_band: tuple[float, float] | None = None,
):
    if not enabled:
        return None, None, None, None

    plot_queue = mp.Queue(maxsize=queue_maxsize)
    plot_queue.cancel_join_thread()

    plot_start_event = mp.Event()
    plot_stop_event = mp.Event()

    plot_process = mp.Process(
        target=run_live_plot,
        kwargs={
            "plot_queue": plot_queue,
            "start_event": plot_start_event,
            "stop_event": plot_stop_event,
            "channel_labels": channel_labels,
            "plot_groups": plot_groups,
            "window_seconds": window_seconds,
            "title": title,
            "y_limits": y_limits,
            "y_band": y_band,
        },
        name=f"{title} Live Plot Process",
    )
    plot_process.start()

    return plot_queue, plot_start_event, plot_stop_event, plot_process


def send_latest_to_plot(plot_queue, plot_start_event, data):
    if plot_queue is None or plot_start_event is None or not plot_start_event.is_set():
        return

    try:
        plot_queue.put_nowait(data)
    except queue.Full:
        try:
            plot_queue.get_nowait()
        except queue.Empty:
            pass

        try:
            plot_queue.put_nowait(data)
        except queue.Full:
            pass


def stop_live_plot_process(plot_queue, plot_stop_event, plot_process):
    if plot_stop_event is not None:
        plot_stop_event.set()

    if plot_process is not None:
        plot_process.join(timeout=5.0)
        if plot_process.is_alive():
            plot_process.terminate()
            plot_process.join()

    if plot_queue is not None:
        plot_queue.close()
        plot_queue.cancel_join_thread()
