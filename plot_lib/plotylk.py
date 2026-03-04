
from matplotlib.collections import LineCollection
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def plot_nodes(df_nodes,
            value_col=None,
            coord_type="cartesian",
            cmap="viridis",
            node_size=20,
            show_labels=False,
            label_offset=(2,2),
            font_size=8,
            ax=None):

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
    else:
        fig = ax.figure

    if coord_type == "geo":
        x_col, y_col = "long", "lat"
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
    else:
        x_col, y_col = "X", "Y"
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

    if value_col is None:
        sc = ax.scatter(df_nodes[x_col],
                        df_nodes[y_col],
                        s=node_size,
                        color="black",
                        zorder=3)
    else:
        sc = ax.scatter(df_nodes[x_col],
                        df_nodes[y_col],
                        c=df_nodes[value_col],
                        cmap=cmap,
                        s=node_size,
                        zorder=3)

        fig.colorbar(sc, ax=ax).set_label(value_col)
    if show_labels:
        dx, dy = label_offset

        for _, row in df_nodes.iterrows():
            ax.text(
                row[x_col] + dx,
                row[y_col] + dy,
                row["Name"],
                fontsize=font_size,
                color="black",
                alpha=0.8
            )

    ax.set_aspect("equal")

    return fig, ax


def plot_lines(df_lines,
            value_col=None,
            coord_type="cartesian",
            cmap="plasma",
            linewidth=2.5,
            ax=None):

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
    else:
        fig = ax.figure

    if coord_type == "geo":
        xi, yi = "long_i", "lat_i"
        xj, yj = "long_j", "lat_j"
        ax.set_xlabel("Longitude [°]")
        ax.set_ylabel("Latitude [°]")
    else:
        xi, yi = "Xi", "Yi"
        xj, yj = "Xj", "Yj"
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")

    segments = [
        [(x1, y1), (x2, y2)]
        for x1, y1, x2, y2 in zip(
            df_lines[xi],
            df_lines[yi],
            df_lines[xj],
            df_lines[yj]
        )
    ]

    if value_col is None:
        lc = LineCollection(segments,
                            colors="black",
                            linewidths=linewidth)
    else:
        lc = LineCollection(segments,
                            cmap=cmap,
                            linewidths=linewidth)
        lc.set_array(np.array(df_lines[value_col]))
        fig.colorbar(lc, ax=ax).set_label(value_col)

    ax.add_collection(lc)
    ax.autoscale()
    ax.set_aspect("equal")

    return fig, ax

def plot_lightnings(df_lightnings,
                    coord_type="cartesian",
                    mode="categorical",
                    value_col="Rusck_maxV",
                    threshold=50,
                    ax=None):

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 6))
    else:
        fig = ax.figure

    if coord_type == "geo":
        x_col, y_col = "Lng", "Lat"
        ax.set_xlabel("Longitude [°]")
        ax.set_ylabel("Latitude [°]")
    else:
        x_col, y_col = "X0", "Y0"
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")

    if mode == "categorical":
        df_ds = df_lightnings[df_lightnings["direct_strike"] == 1]
        ax.scatter(df_ds[x_col], df_ds[y_col],
                color="red", s=10, label="Direct")

        df_ind = df_lightnings[(df_lightnings["direct_strike"] == 0) & (df_lightnings[value_col] < threshold)]
        ax.scatter(df_ind[x_col], df_ind[y_col],
                color="blue", s=15, label="Indirect_eliminated")
        
        df_ind = df_lightnings[(df_lightnings["direct_strike"] == 0) & (df_lightnings[value_col] > threshold)]
        ax.scatter(df_ind[x_col], df_ind[y_col],
                color="green", s=20, label="Indirect")
        
        ax.legend()

    elif mode == "heatmap":
        sc = ax.scatter(df_lightnings[x_col],
                        df_lightnings[y_col],
                        c=df_lightnings[value_col],
                        cmap="inferno",
                        s=30)

        fig.colorbar(sc, ax=ax).set_label(value_col)

    ax.set_aspect("equal")

    return fig, ax 