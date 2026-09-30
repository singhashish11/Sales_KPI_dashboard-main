import streamlit as st
import pandas as pd
import plotly.express as px
from hub_report import render_hub_report


# ================================================================
# 1. PAGE CONFIGURATION
# ================================================================

st.set_page_config(
    page_title="Universal Data Dashboard",
    page_icon="📊",
    layout="wide"
)


# ================================================================
# 2. CUSTOM CSS
# ================================================================

st.markdown("""
<style>

.stMarkdown, .stTitle, .stSubheader, .stAlert {
    text-align: center;
    justify-content: center;
}

.dashboard-title {
    font-size: 40px !important;
    font-weight: 700 !important;
    margin-bottom: 5px !important;
    color: #333;
}

.dashboard-subtitle {
    font-size: 18px !important;
    color: #666;
    margin-bottom: 0px !important;
}


/* ------------------------------------------------
   FILE UPLOADER
------------------------------------------------ */

[data-testid="stFileUploaderDropzone"] {
    background-color: #E24A3F !important;
    border: 2px solid #D93F34 !important;
    border-radius: 12px !important;
    padding: 20px !important;
    max-width: 350px !important;
    margin: 0 auto !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    min-height: 80px !important;
    transition: background-color 0.2s;
    cursor: pointer;
}

[data-testid="stFileUploaderDropzone"]:hover {
    background-color: #D93F34 !important;
}

[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] div {
    display: none !important;
}

[data-testid="stFileUploaderDropzone"]::after {
    content: "Select CSV or Excel file";
    color: white;
    font-size: 20px;
    font-weight: 700;
    text-align: center;
    width: 100%;
}


/* ------------------------------------------------
   METRIC CARDS
------------------------------------------------ */

[data-testid="stMetric"] {
    background-color: #f9f9f9 !important;
    padding: 20px !important;
    border-radius: 10px !important;
    border: 1px solid #eee !important;
}

[data-testid="stMetricLabel"] {
    color: black !important;
}

[data-testid="stMetricValue"] {
    color: black !important;
}

[data-testid="stMetricDelta"] {
    color: black !important;
}

</style>
""", unsafe_allow_html=True)


# ================================================================
# 3. HEADER
# ================================================================

st.markdown(
    '<p class="dashboard-title">Universal Data Dashboard</p>',
    unsafe_allow_html=True
)

st.markdown(
    '<p class="dashboard-subtitle">'
    'Upload ANY dataset to generate instant insights.'
    '</p>',
    unsafe_allow_html=True
)


# ================================================================
# 4. FILE UPLOADER
# ================================================================

uploaded_file = st.file_uploader(
    "",
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is None:
    st.stop()


# ================================================================
# 4B. SHEET SELECTOR
# ================================================================

is_excel = uploaded_file.name.endswith((".xlsx", ".xls"))

sheet_name = 0

if is_excel:

    xl = pd.ExcelFile(uploaded_file)

    if len(xl.sheet_names) > 1:

        sheet_name = st.selectbox(
            "This file has multiple sheets — select one to analyze:",
            xl.sheet_names
        )

    else:
        sheet_name = xl.sheet_names[0]


# ================================================================
# 4C. HEADER ROW PICKER
# ================================================================

@st.cache_data
def preview_raw(file, sheet):

    if file.name.endswith(".csv"):

        return pd.read_csv(
            file,
            header=None,
            nrows=10
        )

    else:

        return pd.read_excel(
            file,
            sheet_name=sheet,
            header=None,
            nrows=10
        )


raw_preview = preview_raw(
    uploaded_file,
    sheet_name
)

st.markdown("##### Preview (first 10 raw rows)")

st.dataframe(
    raw_preview,
    use_container_width=True
)


header_row = st.number_input(
    "Which row number actually contains the column names? "
    "(0 = the first row shown above)",
    min_value=0,
    max_value=len(raw_preview) - 1,
    value=0,
    step=1
)


# ================================================================
# 5. LOAD DATA
# ================================================================

@st.cache_data
def load_data(file, sheet, header_row):

    if file.name.endswith(".csv"):

        data = pd.read_csv(
            file,
            header=header_row
        )

    elif file.name.endswith((".xlsx", ".xls")):

        data = pd.read_excel(
            file,
            sheet_name=sheet,
            header=header_row
        )

    else:

        return None

    # Remove completely empty rows
    data = data.dropna(
        axis=0,
        how="all"
    )

    # Remove completely empty columns
    data = data.dropna(
        axis=1,
        how="all"
    )

    return data


try:

    df = load_data(
        uploaded_file,
        sheet_name,
        header_row
    )

except Exception as e:

    st.error(
        f"Error reading file: {e}"
    )

    st.stop()


if df is None or df.empty:

    st.warning(
        "No usable data found after removing blank rows."
    )

    st.stop()


# ================================================================
# 6. SMART COLUMN DETECTION
# ================================================================

all_columns = df.columns.tolist()


# ------------------------------------------------
# 6A. NUMERIC COLUMNS
# ------------------------------------------------

numeric_columns = df.select_dtypes(
    include="number"
).columns.tolist()


# ------------------------------------------------
# 6B. DATE COLUMNS WHERE DATE IS STORED AS VALUES
#
# Example:
#
# Date          Plant       Quantity
# 01-Sep-26     Plant A     100
# 02-Sep-26     Plant B     200
# ------------------------------------------------

date_value_columns = []

for col in all_columns:

    if col in numeric_columns:
        continue

    try:

        converted = pd.to_datetime(
            df[col],
            errors="coerce",
            dayfirst=True
        )

        non_null = df[col].notna().sum()

        if non_null > 0:

            valid_dates = converted.notna().sum()

            if valid_dates / non_null >= 0.70:

                date_value_columns.append(col)

    except Exception:
        pass


# ------------------------------------------------
# 6C. DATE COLUMNS WHERE DATE IS STORED IN HEADER
#
# Example:
#
# Plant | 01-Sep-26 | 02-Sep-26 | 03-Sep-26
# ------------------------------------------------

date_header_columns = []

for col in all_columns:

    try:

        parsed_date = pd.to_datetime(
            str(col),
            dayfirst=True,
            errors="coerce"
        )

        if pd.notna(parsed_date):

            date_header_columns.append(col)

    except Exception:

        pass


# ------------------------------------------------
# 6D. CATEGORY COLUMNS
#
# Exclude:
# - numeric columns
# - date-value columns
# - date-header columns
# ------------------------------------------------

category_columns = [
    col
    for col in all_columns
    if col not in numeric_columns
    and col not in date_value_columns
    and col not in date_header_columns
]


# ------------------------------------------------
# 6E. VALUE COLUMNS
#
# Numeric columns + date-header columns
# ------------------------------------------------

value_columns = numeric_columns + date_header_columns

# Remove duplicates while preserving order
value_columns = list(
    dict.fromkeys(value_columns)
)


# ------------------------------------------------
# VALIDATION
# ------------------------------------------------

if not category_columns:

    st.error(
        "No suitable category column was detected. "
        "Please check your header row."
    )

    st.stop()


if not value_columns:

    st.error(
        "No numeric or date-based value columns were detected."
    )

    st.stop()


# ================================================================
# 7. DATA MAPPING
# ================================================================

st.divider()

st.markdown(
    "### ⚙️ 1. Select relevant option"
)

map_col1, map_col2 = st.columns(2)


# ------------------------------------------------
# CATEGORY
# ------------------------------------------------

with map_col1:

    cat_col = st.selectbox(
        "Select District / State ",
        category_columns,
        index=0
    )


# ------------------------------------------------
# VALUE
# ------------------------------------------------

with map_col2:

    val_col = st.selectbox(
        "Select Date /  Value",
        value_columns,
        index=0
    )


# ================================================================
# 8. FILTER DATA
# ================================================================

st.markdown(
    "### 🔍 2. You may deselect"
)

_, filter_mid, _ = st.columns([1, 2, 1])


with filter_mid:

    unique_categories = (
        df[cat_col]
        .dropna()
        .unique()
    )

    selected_cats = st.multiselect(
        f"Filter by {cat_col}:",
        options=unique_categories,
        default=unique_categories,
        label_visibility="collapsed"
    )


filtered_df = df[
    df[cat_col].isin(selected_cats)
].copy()


if filtered_df.empty:

    st.warning(
        "No data selected to display."
    )

    st.stop()


# ================================================================
# 8B. REMOVE TOTAL ROWS FOR GENERAL ANALYSIS
#
# Keep filtered_df unchanged because contribution analysis
# needs the Total row.
# ================================================================

total_row_mask = (
    filtered_df[cat_col]
    .astype(str)
    .str.contains(
        "total",
        case=False,
        na=False
    )
)

analysis_df = filtered_df[
    ~total_row_mask
].copy()


# If everything was detected as Total,
# use the original data.
if analysis_df.empty:

    analysis_df = filtered_df.copy()


# ================================================================
# 9. DASHBOARD TITLE
# ================================================================

st.divider()

st.subheader(
    f"📊 Analyzing {val_col} grouped by {cat_col}"
)


# ================================================================
# 10. TOP 10 AND BOTTOM 10
# ================================================================

st.markdown(
    "### 🏆 Sales Ranking"
)

st.markdown(
    f"""
    <p style='text-align:center;color:#666;'>
    Sales ranked according to total <b>{val_col}</b>.
    </p>
    """,
    unsafe_allow_html=True
)


# Convert selected value column to numeric safely
analysis_df[val_col] = pd.to_numeric(
    analysis_df[val_col],
    errors="coerce"
)


# Remove rows where selected value is null
ranking_df = analysis_df.dropna(
    subset=[val_col]
).copy()


if not ranking_df.empty:

    customer_sales = (
        ranking_df
        .groupby(cat_col)[val_col]
        .sum()
        .reset_index()
    )

    customer_sales = customer_sales.sort_values(
        by=val_col,
        ascending=False
    )


    # ============================================================
    # TOP 10
    # ============================================================

    top_10 = customer_sales.head(10).copy()

    top_10.insert(
        0,
        "Rank",
        range(1, len(top_10) + 1)
    )


    # ============================================================
    # LOWEST 10
    # ============================================================

    bottom_10 = (
        customer_sales
        .sort_values(
            by=val_col,
            ascending=True
        )
        .head(10)
        .copy()
    )

    bottom_10.insert(
        0,
        "Rank",
        range(1, len(bottom_10) + 1)
    )


    # ============================================================
    # DISPLAY
    # ============================================================

    table1, table2 = st.columns(2)


    with table1:

        st.markdown(
            "#### 🥇 Top 10 Districts"
        )

        st.dataframe(
            top_10,
            use_container_width=True,
            hide_index=True
        )


    with table2:

        st.markdown(
            "#### 📉 Lowest 10 Districts"
        )

        st.dataframe(
            bottom_10,
            use_container_width=True,
            hide_index=True
        )

else:

    st.info(
        "No numeric values available for ranking."
    )


st.divider()


# ================================================================
# 11. PLANT / LOCATION CONTRIBUTION ANALYSIS
# ================================================================

st.markdown(
    "### 📈 Location Contribution Analysis"
)


# Use the already detected date-header columns
date_cols = [
    c
    for c in date_header_columns
    if c in filtered_df.columns
]


if date_cols:

    # ------------------------------------------------------------
    # FIND TOTAL ROW
    # ------------------------------------------------------------

    total_mask = (
        filtered_df[cat_col]
        .astype(str)
        .str.contains(
            "total",
            case=False,
            na=False
        )
    )


    if total_mask.any():

        total_row = (
            filtered_df
            .loc[
                total_mask,
                date_cols
            ]
            .apply(
                pd.to_numeric,
                errors="coerce"
            )
            .iloc[0]
        )

        plant_options = (
            filtered_df
            .loc[
                ~total_mask,
                cat_col
            ]
            .dropna()
            .unique()
        )

    else:

        total_row = (
            filtered_df[date_cols]
            .apply(
                pd.to_numeric,
                errors="coerce"
            )
            .sum()
        )

        plant_options = (
            filtered_df[cat_col]
            .dropna()
            .unique()
        )


    if len(plant_options) > 0:

        # --------------------------------------------------------
        # SELECT PLANT
        # --------------------------------------------------------

        selected_plant = st.selectbox(
            "Select a location to see its contribution to the total:",
            plant_options
        )


        # --------------------------------------------------------
        # SELECTED PLANT DATA
        # --------------------------------------------------------

        selected_rows = filtered_df.loc[
            filtered_df[cat_col] == selected_plant,
            date_cols
        ]


        if not selected_rows.empty:

            plant_row = (
                selected_rows
                .apply(
                    pd.to_numeric,
                    errors="coerce"
                )
                .iloc[0]
            )


            # ----------------------------------------------------
            # CONTRIBUTION %
            # ----------------------------------------------------

            contribution = (
                plant_row
                .div(total_row.replace(0, pd.NA))
                .mul(100)
                .reset_index()
            )


            contribution.columns = [
                "Date",
                "Contribution %"
            ]


            contribution["Date"] = pd.to_datetime(
                contribution["Date"],
                dayfirst=True,
                errors="coerce"
            )


            contribution["Contribution %"] = pd.to_numeric(
                contribution["Contribution %"],
                errors="coerce"
            )


            contribution = (
                contribution
                .dropna(
                    subset=[
                        "Date",
                        "Contribution %"
                    ]
                )
                .sort_values("Date")
            )


            if not contribution.empty:

                # ------------------------------------------------
                # KPI METRICS
                # ------------------------------------------------

                c1, c2, c3 = st.columns(3)


                c1.metric(
                    "Average Contribution",
                    f"{contribution['Contribution %'].mean():.2f}%"
                )


                c2.metric(
                    "Highest Contribution",
                    f"{contribution['Contribution %'].max():.2f}%"
                )


                c3.metric(
                    "Lowest Contribution",
                    f"{contribution['Contribution %'].min():.2f}%"
                )


                # ------------------------------------------------
                # CONTRIBUTION TREND
                # ------------------------------------------------

                fig_contribution = px.line(
                    contribution,
                    x="Date",
                    y="Contribution %",
                    markers=True,
                    title=(
                        f"{selected_plant}'s Contribution "
                        f"% to Total over Time"
                    ),
                    template="simple_white"
                )

                fig_contribution.update_yaxes(rangemode="tozero")

                st.plotly_chart(
                    fig_contribution,
                    use_container_width=True
                )


                # ------------------------------------------------
                # CONTRIBUTION ON SPECIFIC DATE
                # ------------------------------------------------

                st.markdown(
                    "#### 📅 Contribution on a Specific Date"
                )


                selected_date = st.selectbox(
                    "Pick a date:",
                    contribution[
                        "Date"
                    ]
                    .dt
                    .strftime("%d-%b-%y")
                    .tolist(),

                    index=len(contribution) - 1
                )


                day_row = contribution[
                    contribution["Date"]
                    .dt
                    .strftime("%d-%b-%y")
                    == selected_date
                ].iloc[0]


                st.metric(
                    f"{selected_plant}'s Contribution on {selected_date}",
                    f"{day_row['Contribution %']:.2f}%"
                )


                # ------------------------------------------------
                # FIND SELECTED DATE COLUMN
                # ------------------------------------------------

                date_col_match = None

                for c in date_cols:

                    parsed = pd.to_datetime(
                        c,
                        dayfirst=True,
                        errors="coerce"
                    )

                    if (
                        pd.notna(parsed)
                        and parsed.strftime("%d-%b-%y")
                        == selected_date
                    ):

                        date_col_match = c
                        break


                if date_col_match is not None:

                    # --------------------------------------------
                    # ALL PLANTS ON SELECTED DATE
                    # --------------------------------------------

                    if total_mask.any:

                        all_plants_that_day = (
                            filtered_df
                            .loc[
                                ~total_mask,
                                [cat_col, date_col_match]
                            ]
                            .copy()
                        )

                    else:

                        all_plants_that_day = (
                            filtered_df[
                                [cat_col, date_col_match]
                            ]
                            .copy()
                        )


                    all_plants_that_day[
                        date_col_match
                    ] = pd.to_numeric(
                        all_plants_that_day[
                            date_col_match
                        ],
                        errors="coerce"
                    )


                    total_for_date = pd.to_numeric(
                        total_row[date_col_match],
                        errors="coerce"
                    )


                    if (
                        pd.notna(total_for_date)
                        and total_for_date != 0
                    ):

                        all_plants_that_day[
                            "Contribution %"
                        ] = (
                            all_plants_that_day[
                                date_col_match
                            ]
                            / total_for_date
                            * 100
                        )


                        all_plants_that_day = (
                            all_plants_that_day
                            .dropna(
                                subset=[
                                    "Contribution %"
                                ]
                            )
                            .sort_values(
                                "Contribution %",
                                ascending=False
                            )
                        )


                        # ----------------------------------------
                        # DAY BAR CHART
                        # ----------------------------------------

                        selected_flag = (
                            all_plants_that_day[
                                cat_col
                            ] == selected_plant
                        )


                        fig_day_bar = px.bar(
                            all_plants_that_day,
                            x=cat_col,
                            y="Contribution %",
                            text_auto=".2f",
                            color=selected_flag.map({
                                True: "Selected",
                                False: "Other"
                            }),
                            title=(
                                f"Every location's Contribution "
                                f"% on {selected_date}"
                            ),
                            template="simple_white"
                        )


                        fig_day_bar.update_layout(
                            showlegend=False
                        )

                        fig_day_bar.update_yaxes(rangemode="tozero")


                        st.plotly_chart(
                            fig_day_bar,
                            use_container_width=True
                        )

            else:

                st.info(
                    "No valid contribution data available."
                )

    else:

        st.info(
            "No plant/location rows found."
        )

else:

    st.info(
        "No date-formatted columns detected in this sheet "
        "for contribution analysis."
    )


st.divider()


# ================================================================
# 11C. HUB-WISE REPORT
# ================================================================

render_hub_report(
    filtered_df,
    cat_col,
    date_cols
)

st.divider()


# ================================================================
# 12. AUTOMATIC TREND LINE (TOTAL ACROSS ALL LOCATIONS)
#
# Supports BOTH:
#
# A. Dates stored as column headers
#
#    Plant | 01-Sep-26 | 02-Sep-26 | 03-Sep-26
#
# B. Dates stored as values
#
#    Date | Plant | Quantity
#
# Y-AXIS FIX: Plotly auto-ranges the y-axis tightly around the data
# (e.g. 180-225) instead of starting at 0. That makes ordinary day-
# to-day changes (like 192 -> 211, a difference of only ~19) look
# like a dramatic spike. rangemode="tozero" forces the axis to start
# at 0 so the line reflects the TRUE proportional scale of the data.
# ================================================================

if date_header_columns:

    # ------------------------------------------------------------
    # WIDE FORMAT
    # ------------------------------------------------------------

    trend_data = (
        analysis_df[
            [cat_col] + date_header_columns
        ]
        .melt(
            id_vars=[cat_col],
            value_vars=date_header_columns,
            var_name="Date",
            value_name="Value"
        )
    )


    trend_data["Value"] = pd.to_numeric(
        trend_data["Value"],
        errors="coerce"
    )


    trend_data["Date"] = pd.to_datetime(
        trend_data["Date"],
        dayfirst=True,
        errors="coerce"
    )


    trend_data = trend_data.dropna(
        subset=[
            "Date",
            "Value"
        ]
    )


    trend_data = (
        trend_data
        .groupby("Date")["Value"]
        .sum()
        .reset_index()
        .sort_values("Date")
    )


    if not trend_data.empty:

        fig_line = px.line(
            trend_data,
            x="Date",
            y="Value",
            markers=True,
            title="Sales trend over Time (Total across all locations)",
            template="simple_white"
        )

        fig_line.update_yaxes(rangemode="tozero")

        st.plotly_chart(
            fig_line,
            use_container_width=True
        )


        st.divider()


elif date_value_columns:

    # ------------------------------------------------------------
    # LONG FORMAT
    # ------------------------------------------------------------

    automatic_date_col = date_value_columns[0]


    trend_data = analysis_df.copy()


    trend_data[automatic_date_col] = pd.to_datetime(
        trend_data[automatic_date_col],
        errors="coerce",
        dayfirst=True
    )


    trend_data[val_col] = pd.to_numeric(
        trend_data[val_col],
        errors="coerce"
    )


    trend_data = trend_data.dropna(
        subset=[
            automatic_date_col,
            val_col
        ]
    )


    trend_data = (
        trend_data
        .groupby(automatic_date_col)[val_col]
        .sum()
        .reset_index()
        .sort_values(automatic_date_col)
    )


    if not trend_data.empty:

        fig_line = px.line(
            trend_data,
            x=automatic_date_col,
            y=val_col,
            markers=True,
            title=f"{val_col} Trend over Time (Total across all locations)",
            template="simple_white"
        )

        fig_line.update_yaxes(rangemode="tozero")

        st.plotly_chart(
            fig_line,
            use_container_width=True
        )


        st.divider()


# ================================================================
# 13. CATEGORY CHARTS
# ================================================================

chart1, chart2 = st.columns(2)


# ------------------------------------------------
# BAR CHART
# ------------------------------------------------

with chart1:

    bar_data = (
        ranking_df
        .groupby(cat_col)[val_col]
        .sum()
        .reset_index()
        .sort_values(
            by=val_col,
            ascending=False
        )
        .head(10)
    )


    if not bar_data.empty:

        fig_bar = px.bar(
            bar_data,
            x=cat_col,
            y=val_col,
            text_auto=True,
            color=cat_col,
            title=f"Top 10 {cat_col} by {val_col}",
            template="simple_white"
        )


        fig_bar.update_layout(
            showlegend=False
        )

        fig_bar.update_yaxes(rangemode="tozero")


        st.plotly_chart(
            fig_bar,
            use_container_width=True
        )


# ------------------------------------------------
# PIE CHART
# ------------------------------------------------

with chart2:

    pie_data = (
        ranking_df
        .groupby(cat_col)[val_col]
        .sum()
        .reset_index()
    )


    if not pie_data.empty:

        fig_pie = px.pie(
            pie_data,
            names=cat_col,
            values=val_col,
            hole=0.4,
            title=f"Distribution of {val_col} across {cat_col}",
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


st.divider()


# ================================================================
# 14. CORRELATION ANALYSIS
# ================================================================

# if len(numeric_columns) >= 2:

#     st.markdown(
#         "### 🔬 Deep Dive: Correlation Analysis"
#     )


#     st.markdown(
#         """
#         <p style='text-align:center;color:#666;'>
#         See how two different metrics relate to one another.
#         </p>
#         """,
#         unsafe_allow_html=True
#     )


#     scat_col1, scat_col2 = st.columns(2)


#     with scat_col1:

#         x_axis = st.selectbox(
#             "X-Axis Metric:",
#             numeric_columns,
#             index=0
#         )


#     with scat_col2:

#         y_axis = st.selectbox(
#             "Y-Axis Metric:",
#             numeric_columns,
#             index=1
#         )


#     fig_scatter = px.scatter(
#         filtered_df,
#         x=x_axis,
#         y=y_axis,
#         color=cat_col,
#         opacity=0.7,
#         title=f"Correlation: {x_axis} vs {y_axis}",
#         template="simple_white"
#     )


#     st.plotly_chart(
#         fig_scatter,
#         use_container_width=True
#     )


#     st.divider()


# ================================================================
# 15. RAW DATA
# ================================================================

st.markdown(
    "### 🗃️ Raw Data View"
)

st.dataframe(
    filtered_df,
    use_container_width=True
)