import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from plot_lib.plotylk import plot_lightnings, plot_lines, plot_nodes

def compute_voltage_bins(df,
                         vmin=50,
                         vmax=300,
                         bin_size=25,
                         exceed_value=None):

    # Remove first column if it's the stroke label
    df_numeric = df.drop(columns=["Column1"], errors="ignore")

    bins = np.arange(vmin, vmax + bin_size, bin_size)

    results = {}

    for node in df_numeric.columns:

        values = df_numeric[node]

        # Histogram counts
        counts, edges = np.histogram(values, bins=bins)

        table = pd.DataFrame({
            "bin_min": edges[:-1],
            "bin_max": edges[1:],
            "count": counts
        })

        # Exceedance count
        if exceed_value is not None:
            table["exceed_count"] = [
                (values >= edge).sum() for edge in edges[:-1]
            ]

        results[node] = table

    return results

def plot_exceedance_across_nodes(df, threshold):

    df_numeric = df.drop(columns=["Column1"], errors="ignore")

    exceed_counts = (df_numeric >= threshold).sum()

    result_df = exceed_counts.reset_index()
    result_df.columns = ["Nodo", "Conteo de Eventos"]

    sns.set_theme(style="whitegrid", context="talk")

    plt.figure(figsize=(10,6))
    ax=sns.barplot(data=result_df,
                x="Nodo",
                y="Conteo de Eventos",
                color="#a8063c" )
    # palette="deep" "Blues", "Blues_d", "BuGn", "GnBu", "OrRd", "Purples", "Greens"

    #Formateando eje x
        
    # 1) Tomar las etiquetas originales que Seaborn puso
    labels = [t.get_text() for t in ax.get_xticklabels()]

    # 2) Truncar a 8 caracteres (agregando "…" si excede)
    def trunc8(s):
        s = str(s)
        return (s[:8] + "…") if len(s) > 8 else s

    trunc_labels = [trunc8(s) for s in labels]

    # 3) Mostrar solo cada 3er valor en el eje X
    positions = list(range(0, len(trunc_labels), 3))
    ax.set_xticks(positions)
    ax.set_xticklabels([trunc_labels[i] for i in positions],
                          rotation=90,
                          ha="right",size=10)




    plt.title(f"Eventos que superan valor de {threshold} kV")
    #plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    return result_df


def plot_node_bins(bin_table, node_name):

    sns.set_theme(style="whitegrid", context="talk")

    bin_table["bin_label"] = (
        bin_table["bin_min"].astype(str)
        + "-"
        + bin_table["bin_max"].astype(str)
    )

    plt.figure(figsize=(10,6))
    sns.barplot(
        x="bin_label",
        y="count",
        data=bin_table,
        color="steelblue"
    )

    plt.xticks(rotation=45)
    plt.title(f"Distribution de Tensión - {node_name}")
    plt.xlabel("Tensión (kV)")
    plt.ylabel("Número de eventos")
    plt.tight_layout()
    plt.show()

    import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

def plot_log_fail(bin_dict,
                        key="max",
                        nmax=None,
                        minVoltage=100,CFO_factor=1.25,Vcfo=200,Area=10,GFD=1):

    sns.set_theme(style="whitegrid", context="talk")

    df = bin_dict[key].copy()

    if nmax is None:
        nmax = df["exceed_count"].max()

    # Scale exceedance
    df["scaled_exceed"] = df["exceed_count"] / nmax*GFD*Area

    # Remove zero values (log scale protection)
    df = df[df["scaled_exceed"] > 0]

    # Apply minimum voltage filter
    if minVoltage is not None:
        df = df[df["bin_min"] >= minVoltage]

    x = df["bin_min"]
    y = df["scaled_exceed"]

    fig, ax = plt.subplots(figsize=(9,6))

    ax.step(x/CFO_factor, y, where="post", linewidth=2)

    ax.set_yscale("log")

    ax.set_xlabel("CFO (kV)")
    ax.set_ylabel("Flameos por año")

    # Set X-axis lower bound if provided
    if minVoltage is not None:
        ax.set_xlim(left=minVoltage)

    ax.grid(True,
            which="both",
            linestyle="--",
            linewidth=0.6,
            color="gray",
            alpha=0.6)

    ax.set_title(f"Flameos línea por año vs CFO con GFD: {GFD} [rayos/km²] y Área: {Area} km²")

    intersection_value = None
    # ---- Add Vcfo line and compute intersection ----
    if Vcfo is not None:

        ax.axvline(Vcfo,
                   color="red",
                   linestyle="--",
                   linewidth=2,
                   label=f"Vcfo = {Vcfo} kV")

        # Interpolate exceedance value at Vcfo
        if Vcfo >= x.min() and Vcfo <= x.max():
            intersection_value = np.interp(Vcfo, x/CFO_factor, y)
            print(f"Salidas por año Vcfo ({Vcfo} kV): {intersection_value:.6e}")

            # Mark intersection point
            ax.scatter(Vcfo,
                       intersection_value,
                       color="red",
                       zorder=3)

    ax.legend()
    plt.tight_layout()

    return fig, ax
