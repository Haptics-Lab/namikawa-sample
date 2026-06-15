import queue
from collections import deque

import matplotlib.pyplot as plt


def run_live_plot(
    plot_queue,
    start_event,
    stop_event,
    channel_labels: list[str],
    plot_groups: list[tuple[str, list[int]]],
    window_seconds: float = 5.0,
    title: str = "Live Plot",
    y_limits: tuple[float, float] | None = None,
    y_band: tuple[float, float] | None = None,
):
    if not _wait_until_started(start_event, stop_event):
        return

    plt.ion()

    fig, axes = plt.subplots(
        len(plot_groups),
        1,
        sharex=True,
        figsize=(10, 2.5 * len(plot_groups)),
    )
    fig.canvas.manager.set_window_title(title)

    if len(plot_groups) == 1:
        axes = [axes]

    buffers = None
    lines_by_channel = {}

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
                {"times": deque(), "values": deque()}
                for _ in range(channel_count)
            ]

            for ax, (group_name, channel_indices) in zip(axes, plot_groups):
                ax.set_title(group_name)
                if y_limits is not None:
                    ax.set_ylim(*y_limits)
                if y_band is not None:
                    ax.axhspan(*y_band, facecolor="lightyellow", edgecolor="gray", alpha=0.5, zorder=0)

                for channel_index in channel_indices:
                    label = channel_labels[channel_index]

                    if "sync" in label.lower():
                        line = ax.step([], [], where="post", label=label)[0]
                    else:
                        line = ax.plot([], [], label=label)[0]

                    lines_by_channel[channel_index] = line

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

        for channel_index, line in lines_by_channel.items():
            line.set_data(
                buffers[channel_index]["times"],
                buffers[channel_index]["values"],
            )

        for ax in axes:
            ax.relim()
            ax.autoscale_view(scalex=True, scaley=y_limits is None)
            if y_limits is not None:
                ax.set_ylim(*y_limits)

        fig.canvas.draw_idle()
        fig.canvas.flush_events()

    plt.close(fig)


def _wait_until_started(start_event, stop_event):
    while not stop_event.is_set():
        if start_event.wait(timeout=0.1):
            return True
    return False