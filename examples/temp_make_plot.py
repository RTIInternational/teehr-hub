def plot_timeseries_completeness(
    pdf: pd.DataFrame,
    group_by: str,
    period: str,
    sort_y_axis_by: str
):

    pdf["period"] = pd.to_datetime(pdf["period"])

    # ──  Calculate completeness → actual/expected ───────────────────
    pdf["completeness"] = (
        (pdf["actual_count"] / pdf["expected_count"] * 100.0)
        .clip(upper=100.0)
    )

    # ──  Pivot → rows = group_by, columns = period ───────────────────
    pivot = pdf.pivot(index=group_by, columns="period", values="completeness")
    pivot.columns = pd.DatetimeIndex(pivot.columns)

    # ──  Sort and (optionally) cap number of locations ──────────────────
    if sort_y_axis_by == "completeness":
        order = pivot.mean(axis=1).sort_values()   # least complete first
        pivot = pivot.loc[order.index]
    else:
        pivot = pivot.sort_index()

    # if max_locations and len(pivot) > max_locations:
    #     pivot = pivot.iloc[:max_locations]

    # ──  Build Plotly heatmap ────────────────────────────────────────────
    n_locs = len(pivot)
    x_labels = [t.strftime("%Y-%m-%d") for t in pivot.columns]

    # print(f"YO!: {pivot.index.tolist()}")

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=x_labels,
        y=pivot.index.tolist(),
        zmin=0,
        zmax=100,
        colorscale=[
            [0.00, "#d62728"],   # red    → 0 % complete
            [0.50, "#ffdd57"],   # yellow → 50%
            [1.00, "#2ca02c"],   # green  → 100%
        ],
        colorbar=dict(title="Completeness (%)"),
        hovertemplate=(
            "HUC8: %{y}<br>"
            "Period: %{x}<br>"
            "Completeness: %{z:.1f}%"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=(
            f"Primary Timeseries Data Completeness "
            f"(by {period}, {group_by})"
        ),
        xaxis_title=f"Time ({period})",
        yaxis_title=group_by,
        xaxis=dict(tickangle=-45, nticks=24),
        # Scale height to number of locations, capped for usability
        # height=max(500, min(n_locs * 10, 3000)),
        height=700,
        yaxis=dict(
            # Hide individual tick labels when too many to read
            showticklabels=n_locs <= 150,
            tickfont=dict(size=8),
        ),
        margin=dict(l=160 if n_locs <= 150 else 60, b=80),
    )
    return fig