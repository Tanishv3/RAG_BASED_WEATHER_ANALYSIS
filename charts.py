import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from analysis import next_hours

BLUE, RED, ORANGE, GREY = "#2b7bba", "#e4572e", "#f4a261", "#8d99ae"


def _finish(fig, ax, title, ylabel=None):
    ax.set_title(title, fontsize=11, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig


def bar(labels, values, title, ylabel, color=BLUE, fmt="%.0f"):
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.bar(labels, values, color=color)
    ax.bar_label(ax.containers[0], fmt=fmt, fontsize=8)
    ax.margins(y=0.15)
    return _finish(fig, ax, title, ylabel)


def temp_bars(d):
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = np.arange(len(d))
    ax.bar(x - 0.2, d.high, 0.4, label="High", color=RED)
    ax.bar(x + 0.2, d.low, 0.4, label="Low", color=BLUE)
    ax.bar_label(ax.containers[0], fmt="%.0f", fontsize=8)
    ax.bar_label(ax.containers[1], fmt="%.0f", fontsize=8)
    ax.set_xticks(x, d.label)
    ax.legend(frameon=False, fontsize=8)
    ax.margins(y=0.15)
    return _finish(fig, ax, "Daily high / low temperature", "°C")


def rain_bars(d):
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.bar(d.label, d.rain, color=BLUE)
    ax.set_ylabel("Rain (mm)")
    ax2 = ax.twinx()
    ax2.plot(d.label, d.rain_prob, color=ORANGE, marker="o", label="Chance of rain")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("Chance (%)")
    ax2.legend(frameon=False, fontsize=8, loc="upper right")
    return _finish(fig, ax, "Daily rainfall (bars) and chance of rain (line)")


def next24(fc):
    h = next_hours(fc)
    fig, ax = plt.subplots(figsize=(12, 3.2))
    x = h.time.dt.strftime("%I%p").str.lstrip("0")
    ax.bar(x, h.precipitation, color=BLUE)
    ax.set_ylabel("Rain (mm)")
    ax.tick_params(axis="x", labelsize=8)
    ax2 = ax.twinx()
    ax2.plot(x, h.temperature_2m, color=RED, marker="o", markersize=3)
    ax2.set_ylabel("Temperature °C")
    return _finish(fig, ax, "Next 24 hours: rain (bars) and temperature (line)")


def hbar(names, values, title, xlabel, color=BLUE, fmt="%.0f"):
    order = np.argsort(values)
    fig, ax = plt.subplots(figsize=(6, max(3, 0.3 * len(names))))
    ax.barh(np.array(names)[order], np.array(values)[order], color=color)
    ax.bar_label(ax.containers[0], fmt=fmt, fontsize=8, padding=2)
    ax.margins(x=0.12)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_xlabel(xlabel)
    return _finish(fig, ax, title)


def rc(dark):
    """matplotlib settings so PNG charts match the light/dark app theme (transparent background)."""
    fg = "#e6e9ef" if dark else "#1f2933"
    edge = "#3a4458" if dark else "#c5d0dc"
    return {"figure.facecolor": "none", "axes.facecolor": "none", "savefig.facecolor": "none",
            "savefig.transparent": True, "text.color": fg, "axes.labelcolor": fg, "axes.edgecolor": edge,
            "xtick.color": fg, "ytick.color": fg, "axes.titlecolor": fg}


def alt_chart(df, col, ylabel, dark, bar=False):
    """Interactive line/bar chart with explicit colours (readable in light and dark mode)."""
    import altair as alt
    fg, grid = ("#e6e9ef", "#2a3446") if dark else ("#1f2933", "#d5dfea")
    base = alt.Chart(df.reset_index()).encode(
        x=alt.X("time:T", title=None), y=alt.Y(f"{col}:Q", title=ylabel),
        tooltip=[alt.Tooltip("time:T", title="Time", format="%a %d %b %H:%M"),
                 alt.Tooltip(f"{col}:Q", title=ylabel, format=".1f")])
    mark = base.mark_bar(color=BLUE) if bar else base.mark_line(color=BLUE, interpolate="monotone", strokeWidth=2)
    return (mark.properties(height=250).configure(background="transparent")
            .configure_axis(labelColor=fg, titleColor=fg, gridColor=grid, domainColor=grid, tickColor=grid)
            .configure_view(stroke=None))
