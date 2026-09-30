"""
hub_report.py
--------------
Standalone module that builds a Hub-wise Sales Report from a
district-wise table (rows = districts, columns = dates).

Features:
- Automatically maps districts to hubs
- Calculates hub-wise totals
- Creates a final Total row
- Shows Total in tables and Excel
- Does NOT show Total in bar chart or pie chart
- Allows date selection
- Downloads selected-date and full reports as Excel

Usage from app.py:
    from hub_report import render_hub_report

    ...
    render_hub_report(filtered_df, cat_col, date_cols)
"""

import re
import io
import difflib

import pandas as pd
import streamlit as st
import plotly.express as px


# ================================================================
# 1. DISTRICT -> HUB MAPPING
# ================================================================

HUB_MAPPING = {
    "Ranchi Hub": [
        "Ranchi",
        "Ramgarh",
        "Khunti",
        "Bokaro",
        "Simdega",
        "Dhanbad",
        "Purbi Singhbhum",
        "Gumla",
        "Saraikela",
        "West Singhbhum"
    ],

    "Deoghar Hub": [
        "Deoghar",
        "Dumka",
        "Godda",
        "Jamtara",
        "Giridih"
    ],

    "Koderma Hub": [
        "Hazaribag",
        "Koderma",
        "Chatra"
    ],

    "Latehar Hub": [
        "Palamu",
        "Garhwa",
        "Latehar"
    ],

    "Sahibganj Hub": [
        "Sahibganj"
    ],
}


# ================================================================
# 2. NORMALIZE DISTRICT NAMES
# ================================================================

def _normalize(name):
    """
    Lowercase and remove everything except letters.

    Example:
        Hazaribagh -> hazaribagh
        Hazaribag  -> hazaribag
    """

    return re.sub(
        r"[^a-z]",
        "",
        str(name).lower()
    )


# ================================================================
# 3. CREATE DISTRICT -> HUB LOOKUP
# ================================================================

_DISTRICT_TO_HUB = {}

for _hub, _districts in HUB_MAPPING.items():

    for _district in _districts:

        _DISTRICT_TO_HUB[
            _normalize(_district)
        ] = _hub


_KNOWN_NORMALIZED = list(
    _DISTRICT_TO_HUB.keys()
)


# ================================================================
# 4. MAP DISTRICT TO HUB
# ================================================================

def map_district_to_hub(district_name):
    """
    Map a district name to its hub.

    First tries exact matching.

    If exact matching fails, fuzzy matching is used for
    small spelling differences.

    Returns None if no hub can be identified.
    """

    norm = _normalize(district_name)

    # Exact match
    if norm in _DISTRICT_TO_HUB:
        return _DISTRICT_TO_HUB[norm]

    # Fuzzy match
    close = difflib.get_close_matches(
        norm,
        _KNOWN_NORMALIZED,
        n=1,
        cutoff=0.75
    )

    if close:
        return _DISTRICT_TO_HUB[close[0]]

    return None


# ================================================================
# 5. BUILD HUB-WISE REPORT
# ================================================================

def build_hub_report(df, cat_col, date_cols):
    """
    Creates the complete Hub-wise report.

    Output:

        Hub              Date1    Date2    Date3    Grand Total
        ---------------------------------------------------------
        Ranchi Hub       ...
        Deoghar Hub      ...
        Koderma Hub      ...
        Latehar Hub      ...
        Sahibganj Hub    ...
        Total             ...      ...      ...       ...

    The Total row is calculated automatically.
    """

    # Keep only required columns
    work = df[
        [cat_col] + date_cols
    ].copy()

    # Convert date columns to numeric
    work[date_cols] = work[
        date_cols
    ].apply(
        pd.to_numeric,
        errors="coerce"
    )

    # Map each district to a hub
    work["Hub"] = work[
        cat_col
    ].apply(
        map_district_to_hub
    )

    # Remove rows that cannot be mapped
    # Example: Total JMF
    work = work.dropna(
        subset=["Hub"]
    )

    # ============================================================
    # Calculate hub totals for every date
    # ============================================================

    hub_totals = (
        work
        .groupby("Hub")[date_cols]
        .sum(min_count=1)
        .reset_index()
    )

    # ============================================================
    # Calculate Grand Total for each Hub
    # ============================================================

    hub_totals["Grand Total"] = (
        hub_totals[date_cols]
        .sum(axis=1)
    )

    # ============================================================
    # Sort hubs by Grand Total
    # ============================================================

    hub_totals = (
        hub_totals
        .sort_values(
            "Grand Total",
            ascending=False
        )
        .reset_index(drop=True)
    )

    # ============================================================
    # Create final Total row
    # ============================================================

    total_row = {
        "Hub": "Total"
    }

    for col in date_cols:

        total_row[col] = (
            hub_totals[col]
            .sum()
        )

    total_row["Grand Total"] = (
        hub_totals["Grand Total"]
        .sum()
    )

    # ============================================================
    # Add Total row at bottom
    # ============================================================

    hub_totals = pd.concat(
        [
            hub_totals,
            pd.DataFrame([total_row])
        ],
        ignore_index=True
    )

    return hub_totals


# ================================================================
# 6. CONVERT DATAFRAME TO EXCEL
# ================================================================

def to_excel_bytes(dataframe):
    """
    Convert dataframe into Excel bytes for download.
    """

    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl"
    ) as writer:

        dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Hub Wise Report"
        )

    return buffer.getvalue()


# ================================================================
# 7. RENDER HUB REPORT
# ================================================================

def render_hub_report(
    df,
    cat_col,
    date_cols
):
    """
    Renders:

    1. Date selector
    2. Hub-wise table
    3. Bar chart
    4. Pie chart
    5. Selected-date Excel download
    6. Full report for all dates
    7. Full Excel download

    IMPORTANT:

    Total is displayed in the table and Excel.

    Total is NOT displayed in:
    - Bar chart
    - Pie chart
    """

    # ============================================================
    # Check whether date columns exist
    # ============================================================

    if not date_cols:

        st.info(
            "No date columns detected — "
            "the hub-wise report needs at least "
            "one date column."
        )

        return

    # ============================================================
    # Section title
    # ============================================================

    st.markdown(
        "### 🏭 Hub-wise Sales Report"
    )

    # ============================================================
    # Build complete hub report
    # ============================================================

    hub_totals = build_hub_report(
        df,
        cat_col,
        date_cols
    )

    # ============================================================
    # Check whether any hub was found
    # ============================================================

    if hub_totals.empty:

        st.warning(
            "Could not map any district to a hub. "
            "Check district spellings in the sheet "
            "against HUB_MAPPING in hub_report.py."
        )

        return

    # ============================================================
    # Convert date column names into readable labels
    # ============================================================

    date_labels = []

    for col in date_cols:

        parsed_date = pd.to_datetime(
            col,
            dayfirst=True,
            errors="coerce"
        )

        if pd.notna(parsed_date):

            date_labels.append(
                parsed_date.strftime(
                    "%d-%b-%y"
                )
            )

        else:

            date_labels.append(
                str(col)
            )

    # ============================================================
    # Date selector
    # ============================================================

    selected_label = st.selectbox(
        "Select a date for the Hub-wise Report:",
        date_labels,
        index=len(date_labels) - 1,
        key="hub_report_date"
    )

    # Find selected date column
    selected_date_index = date_labels.index(
        selected_label
    )

    selected_date_col = date_cols[
        selected_date_index
    ]

    # ============================================================
    # Create selected-date table
    # ============================================================

    day_table = (
        hub_totals[
            ["Hub", selected_date_col]
        ]
        .rename(
            columns={
                selected_date_col:
                "Total (TKgPD)"
            }
        )
    )

    # ============================================================
    # Separate Total row
    # ============================================================

    total_day_row = day_table[
        day_table["Hub"] == "Total"
    ]

    # ============================================================
    # Create chart data
    #
    # IMPORTANT:
    # Total is removed here.
    #
    # Therefore:
    # - Total will NOT appear in bar chart
    # - Total will NOT appear in pie chart
    # ============================================================

    chart_data = day_table[
        day_table["Hub"] != "Total"
    ].copy()

    # ============================================================
    # Sort only actual hubs
    # ============================================================

    chart_data = (
        chart_data
        .sort_values(
            "Total (TKgPD)",
            ascending=False
        )
        .reset_index(drop=True)
    )

    # ============================================================
    # Put Total back at bottom of table
    # ============================================================

    day_table = pd.concat(
        [
            chart_data,
            total_day_row
        ],
        ignore_index=True
    )

    # ============================================================
    # Display table
    # ============================================================

    st.markdown(
        f"**Hub-wise totals on {selected_label}**"
    )

    st.dataframe(
        day_table,
        use_container_width=True,
        hide_index=True
    )

    # ============================================================
    # BAR CHART + PIE CHART
    # ============================================================

    col_a, col_b = st.columns(2)

    # ============================================================
    # BAR CHART
    # ============================================================

    with col_a:

        fig_bar = px.bar(
            chart_data,
            x="Hub",
            y="Total (TKgPD)",
            text_auto=".2f",
            color="Hub",
            title=(
                f"Hub-wise Sales on "
                f"{selected_label}"
            ),
            template="simple_white"
        )

        fig_bar.update_layout(
            showlegend=False
        )

        st.plotly_chart(
            fig_bar,
            use_container_width=True
        )

    # ============================================================
    # PIE CHART
    # ============================================================

    with col_b:

        fig_pie = px.pie(
            chart_data,
            names="Hub",
            values="Total (TKgPD)",
            hole=0.4,
            title=(
                f"Hub Share on "
                f"{selected_label}"
            ),
            template="simple_white"
        )

        fig_pie.update_traces(
            textposition="inside",
            textinfo="percent+label"
        )

        fig_pie.update_layout(
            showlegend=False
        )

        st.plotly_chart(
            fig_pie,
            use_container_width=True
        )

    # ============================================================
    # DOWNLOAD SELECTED DATE REPORT
    # ============================================================

    st.download_button(
        label=(
            f"⬇️ Download Hub-wise Report "
            f"({selected_label}) as Excel"
        ),

        data=to_excel_bytes(
            day_table
        ),

        file_name=(
            f"Hub_Wise_Report_"
            f"{selected_label}.xlsx"
        ),

        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),

        key="hub_report_download_day"
    )

    # ============================================================
    # FULL REPORT
    # ============================================================

    with st.expander(
        "View full Hub-wise Report — every date in one table"
    ):

        st.dataframe(
            hub_totals,
            use_container_width=True,
            hide_index=True
        )

        # ========================================================
        # DOWNLOAD FULL REPORT
        # ========================================================

        st.download_button(
            label=(
                "⬇️ Download Full Hub-wise "
                "Report (All Dates) as Excel"
            ),

            data=to_excel_bytes(
                hub_totals
            ),

            file_name=(
                "Hub_Wise_Report_All_Dates.xlsx"
            ),

            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),

            key="hub_report_download_all"
        )