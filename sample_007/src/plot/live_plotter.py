import queue
from collections import deque

import matplotlib.pyplot as plt


def run_live_plot(plot_queue, start_event, stop_event, window_seconds=5.0):
    if not _wait_until_started(start_event, stop_event):
        return

    plt.ion()
    fig, ax = plt.subplots()

    buffers = None
    lines = []

    while not stop_event.is_set():
        try:
            times, values = plot_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if not values:
            continue

        if buffers is None:
            channel_count = len(values[0])
            buffers = [
                {
                    "times": deque(),
                    "values": deque(),
                }
                for _ in range(channel_count)
            ]
            lines = [ax.plot([], [], label=f"ch{index}")[0] for index in range(channel_count)]
            ax.legend(loc="upper right")

        latest_time = times[-1]

        for time_value, sample_values in zip(times, values):
            for channel_index, channel_value in enumerate(sample_values):
                buffers[channel_index]["times"].append(time_value)
                buffers[channel_index]["values"].append(channel_value)

        for buffer in buffers:
            while buffer["times"] and buffer["times"][0] < latest_time - window_seconds:
                buffer["times"].popleft()
                buffer["values"].popleft()

        for line, buffer in zip(lines, buffers):
            line.set_data(buffer["times"], buffer["values"])

        ax.relim()
        ax.autoscale_view()
        fig.canvas.draw()
        fig.canvas.flush_events()

    plt.close(fig)


def _wait_until_started(start_event, stop_event):
    while not stop_event.is_set():
        if start_event.wait(timeout=0.1):
            return True
    return False