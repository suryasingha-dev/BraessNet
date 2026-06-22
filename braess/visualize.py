"""
Module 4 — Visualisation & Export.

Three visual outputs (static classification map, interactive dashboard,
top-edges highlight map) plus CSV/JSON export of the full results table.
"""
import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
from matplotlib.patches import Patch
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _node_xy(G):
    return {n: (d["x"], d["y"]) for n, d in G.nodes(data=True)}


def plot_static_map(G, df, output_dir):
    """Two-panel matplotlib map: Braess classification + redundancy heatmap."""
    pos = _node_xy(G)
    braess_set = set(zip(df[df["is_braess"]].u, df[df["is_braess"]].v))
    tested_set = set(zip(df.u, df.v))
    score_map = dict(zip(zip(df.u, df.v), df["redundancy_score"]))
    cmap = cm.get_cmap("RdYlGn_r")

    fig, axes = plt.subplots(1, 2, figsize=(22, 10))
    fig.patch.set_facecolor("#0d1117")

    # ── Panel A: Classification ──────────────────────────────────────────
    ax = axes[0]
    ax.set_facecolor("#0d1117")
    ax.set_title("Braess Paradox Edge Classification", color="white", fontsize=15, pad=14, fontweight="bold")
    for u, v in G.edges():
        xs = [pos[u][0], pos[v][0]]
        ys = [pos[u][1], pos[v][1]]
        if (u, v) in braess_set:
            ax.plot(xs, ys, color="#ff3a3a", lw=2.8, zorder=5, solid_capstyle="round")
        elif (u, v) in tested_set:
            ax.plot(xs, ys, color="#3a8eff", lw=0.9, zorder=3, alpha=0.8)
        else:
            ax.plot(xs, ys, color="#1e2332", lw=0.35, zorder=1)

    xs_n = [pos[n][0] for n in G.nodes()]
    ys_n = [pos[n][1] for n in G.nodes()]
    ax.scatter(xs_n, ys_n, s=6, c="#aaaaaa", zorder=6, linewidths=0)

    nb = int(df["is_braess"].sum())
    leg = [Patch(facecolor="#ff3a3a", label=f"Braess edge (n={nb}) — removal ↓ system cost"),
           Patch(facecolor="#3a8eff", label="Tested — no Braess effect"),
           Patch(facecolor="#1e2332", label="Untested")]
    ax.legend(handles=leg, loc="lower left", facecolor="#161b27", edgecolor="#333",
              labelcolor="white", fontsize=9, framealpha=0.9)
    ax.set_axis_off()

    # ── Panel B: Redundancy Heatmap ───────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor("#0d1117")
    ax2.set_title("Edge Redundancy Score (Braess + Under-utilisation)", color="white",
                  fontsize=15, pad=14, fontweight="bold")
    for u, v in G.edges():
        xs = [pos[u][0], pos[v][0]]
        ys = [pos[u][1], pos[v][1]]
        s = score_map.get((u, v))
        if s is not None:
            ax2.plot(xs, ys, color=cmap(s), lw=1.6, zorder=3, solid_capstyle="round")
        else:
            ax2.plot(xs, ys, color="#1a1f2e", lw=0.3, zorder=1)
    ax2.scatter(xs_n, ys_n, s=6, c="#aaaaaa", zorder=6, linewidths=0)

    sm = cm.ScalarMappable(cmap=cmap, norm=mcolors.Normalize(0, 1))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax2, fraction=0.025, pad=0.02)
    cb.set_label("Redundancy Score →", color="white", fontsize=10)
    cb.ax.yaxis.set_tick_params(color="white")
    plt.setp(cb.ax.yaxis.get_ticklabels(), color="white")
    ax2.set_axis_off()

    plt.tight_layout(pad=2)
    p = os.path.join(output_dir, "braess_map.png")
    plt.savefig(p, dpi=160, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    print(f"      Map saved: {p}")
    return p


def plot_dashboard(df, gaps, output_dir):
    """Interactive 4-panel Plotly dashboard (delta cost, convergence, score distribution, road-type breakdown)."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "ΔSystem Cost on Edge Removal  (red = Braess edges)",
            "Frank-Wolfe Convergence (Relative Gap)",
            "Redundancy Score Distribution",
            "Braess Edge Rate by Road Type (%)",
        ],
        vertical_spacing=0.16, horizontal_spacing=0.10,
    )
    dark = "#0d1117"

    # 1. Bar: delta cost
    df_s = df.sort_values("delta_cost")
    colors = ["#ff3a3a" if b else "#3a8eff" for b in df_s["is_braess"]]
    fig.add_trace(go.Bar(
        x=list(range(len(df_s))), y=df_s["delta_cost"],
        marker_color=colors, name="ΔCost",
        hovertext=[f"({r.u},{r.v}) | {r.highway}<br>Δ={r.delta_cost:.3f} min·veh<br>{r.pct_change:.2f}%"
                   for r in df_s.itertuples()],
        hoverinfo="text",
    ), row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.4)", row=1, col=1)

    # 2. Line: convergence gap
    fig.add_trace(go.Scatter(
        x=list(range(1, len(gaps) + 1)), y=gaps,
        mode="lines+markers", name="Rel. Gap",
        line=dict(color="#00e5b0", width=2.5),
        marker=dict(size=5),
    ), row=1, col=2)
    fig.add_hline(y=1e-4, line_dash="dash", line_color="#f59e0b",
                  annotation_text="Convergence threshold", row=1, col=2)

    # 3. Histogram: redundancy score
    fig.add_trace(go.Histogram(
        x=df["redundancy_score"], nbinsx=20,
        marker_color="#a78bfa", name="Redundancy",
        opacity=0.85,
    ), row=2, col=1)

    # 4. Bar: Braess rate by road type
    grp = df.groupby("highway")["is_braess"].agg(["sum", "count"]).reset_index()
    grp.columns = ["highway", "braess", "total"]
    grp["pct"] = grp["braess"] / grp["total"] * 100
    grp = grp.sort_values("pct", ascending=False)
    fig.add_trace(go.Bar(
        x=grp["highway"], y=grp["pct"],
        marker_color="#f59e0b", name="Braess %",
        hovertext=[f"{r.highway}: {r.braess}/{r.total} = {r.pct:.1f}%" for r in grp.itertuples()],
        hoverinfo="text",
    ), row=2, col=2)

    fig.update_layout(
        template="plotly_dark", showlegend=False,
        title=dict(text="<b>Braess Paradox Research Dashboard</b>", font=dict(size=20)),
        height=750, paper_bgcolor=dark, plot_bgcolor=dark,
        font=dict(color="white"),
    )
    fig.update_yaxes(gridcolor="#1e2332")
    fig.update_xaxes(gridcolor="#1e2332")

    p = os.path.join(output_dir, "braess_dashboard.html")
    fig.write_html(p)
    print(f"      Dashboard saved: {p}")
    return p


def plot_top_braess(G, df, output_dir, top_n=10):
    """Highlight top-N most impactful Braess edges individually, on the full road network as backdrop."""
    top = df[df["is_braess"]].head(top_n)
    if top.empty:
        return None
    pos = _node_xy(G)
    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.set_title(f"Top-{len(top)} Braess Edges by Redundancy Score", color="white", fontsize=14, pad=12)

    for u, v in G.edges():
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                color="#3a4156", lw=0.7, zorder=1, alpha=0.8)
    xs_n = [pos[n][0] for n in G.nodes()]
    ys_n = [pos[n][1] for n in G.nodes()]
    ax.scatter(xs_n, ys_n, s=5, c="#666f87", zorder=2, linewidths=0)

    cmap2 = cm.get_cmap("plasma")
    for rank, row in enumerate(top.itertuples()):
        u, v = row.u, row.v
        if u not in pos or v not in pos:
            continue
        c = cmap2(rank / max(len(top) - 1, 1))
        ax.annotate("", xy=(pos[v][0], pos[v][1]), xytext=(pos[u][0], pos[u][1]),
                    arrowprops=dict(arrowstyle="-|>", color=c, lw=2.5), zorder=8)
        mx = (pos[u][0] + pos[v][0]) / 2
        my = (pos[u][1] + pos[v][1]) / 2
        ax.text(mx, my, f"#{rank+1}\n{row.pct_change:.2f}%",
                color=c, fontsize=7, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="#0d1117", ec=c, lw=0.8), zorder=9)

    ax.set_axis_off()
    p = os.path.join(output_dir, "braess_top_edges.png")
    plt.savefig(p, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    print(f"      Top edges map saved: {p}")
    return p


def export_results(df, baseline_cost, output_dir):
    """Write the full results table to CSV, plus an aggregate summary to JSON."""
    csv_p = os.path.join(output_dir, "braess_results.csv")
    df.to_csv(csv_p, index=False)

    braess_df = df[df["is_braess"]]
    reliable_braess_df = df[df["is_braess"] & df["reliable"]]
    summary = {
        "baseline_system_cost_min_veh": round(baseline_cost, 4),
        "edges_tested": len(df),
        "edges_reliable": int(df["reliable"].sum()),
        "braess_edges_found": int(braess_df.shape[0]),
        "braess_edges_reliable": int(reliable_braess_df.shape[0]),
        "braess_rate_pct": round(braess_df.shape[0] / max(len(df), 1) * 100, 2),
        "max_improvement_pct": round(df["pct_change"].min(), 4),
        "avg_improvement_braess_pct": round(braess_df["pct_change"].mean(), 4) if len(braess_df) else 0,
        "top_braess_edges": reliable_braess_df.head(10)[[
            "u", "v", "street_name", "highway", "length_m", "delta_cost", "pct_change",
            "redundancy_score", "betweenness", "convergence_gap"
        ]].to_dict(orient="records"),
    }
    json_p = os.path.join(output_dir, "braess_summary.json")
    with open(json_p, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"      CSV saved:  {csv_p}")
    print(f"      JSON saved: {json_p}")
    return summary
