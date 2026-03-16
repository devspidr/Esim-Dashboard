import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import io
from datetime import datetime

# Page configuration
st.set_page_config(page_title="eSIM Pricing Dashboard", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .main > div { padding-top: 2rem; }
    h1 {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 300;
        font-size: 2.5rem;
        margin-bottom: 2rem;
        color: #1a1a1a;
    }
    .filter-container {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 8px;
        margin-bottom: 2rem;
    }
    .stSelectbox label, .stTextInput label { font-weight: 500; color: #333; }
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; }
    .stTabs [data-baseweb="tab"] { font-size: 1.1rem; font-weight: 500; }
    .sort-info {
        background-color: #e3f2fd;
        padding: 0.75rem 1rem;
        border-radius: 6px;
        margin-bottom: 1rem;
        font-size: 0.95rem;
        color: #1565c0;
        border-left: 4px solid #1976d2;
    }
</style>
""", unsafe_allow_html=True)

# ==================== COLOURS ====================
DIVERSE_COLORS = [
    '#2E86AB', '#27AE60', '#F39C12', '#8E44AD', '#16A085',
    '#F1C40F', '#E67E22', '#1ABC9C', '#3498DB', '#D35400',
    '#2980B9', '#17A589', '#F0B27A', '#76D7C4', '#AED6F1',
    '#A9DFBF', '#FAD7A0', '#D7BDE2',
]
COUNTRY_COLORS = [
    '#2E86AB', '#27AE60', '#F39C12', '#8E44AD', '#16A085',
    '#E74C3C', '#1ABC9C', '#D35400', '#2980B9', '#F1C40F',
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
]
VODAFONE_RED = '#DC143C'


def get_diverse_color_map(items):
    color_map = {}
    non_vf_idx = 0
    for item in sorted(items):
        if 'Vodafone' in str(item):
            color_map[item] = VODAFONE_RED
        else:
            color_map[item] = DIVERSE_COLORS[non_vf_idx % len(DIVERSE_COLORS)]
            non_vf_idx += 1
    return color_map


# ==================== LOAD DATA ====================
@st.cache_data
def load_data():
    csv_df = pd.read_csv('germany_data_complete.csv')
    excel_df = pd.read_excel('market_research_pricing_news.xlsx')

    if 'updated_dtm' not in csv_df.columns:
        csv_df['updated_dtm'] = pd.Timestamp('2025-01-01')
        st.warning("Note: 'updated_dtm' column not found. Using placeholder date for Tab 4.")
    else:
        csv_df['updated_dtm'] = pd.to_datetime(csv_df['updated_dtm'])

    regular_df = csv_df[csv_df['data_amount_MB_numeric'].notna()].copy()
    unlimited_df = csv_df[csv_df['data_amount_MB_numeric'].isna()].copy()

    for df in [regular_df, unlimited_df]:
        df['plan_frequency_days'] = pd.to_numeric(df['plan_frequency_days'], errors='coerce')

    regular_df = regular_df[regular_df['plan_frequency_days'].notna()].drop_duplicates()
    regular_df = regular_df[regular_df['Cost in Euro'] > 0]
    unlimited_df = unlimited_df[unlimited_df['plan_frequency_days'].notna()].drop_duplicates()
    unlimited_df = unlimited_df[unlimited_df['Cost in Euro'] > 0]

    provider_type_map = excel_df[['Name', 'Type']].drop_duplicates().set_index('Name')['Type'].to_dict()

    def normalize_provider_type(type_value):
        if pd.isna(type_value):
            return 'Other'
        type_str = str(type_value).strip().upper()
        categories = {
            'MVNO': ['MVNO', 'M V N O', 'MV NO'],
            'MNO': ['MNO', 'M N O'],
            'RESELLER': ['RESELLER', 'RE SELLER', 'RE-SELLER'],
            'AGGREGATOR': ['AGGREGATOR', 'AGGR'],
            'CARRIER': ['CARRIER'],
            'OPERATOR': ['OPERATOR', 'TELCO OPERATOR']
        }
        for canonical, variations in categories.items():
            for variation in variations:
                if variation in type_str:
                    return canonical
        return type_str.title() if type_str != 'OTHER' else 'Other'

    for df in [regular_df, unlimited_df]:
        df['Provider_Type'] = df['Provider'].map(provider_type_map).fillna('Other').apply(normalize_provider_type)
        df['Provider_Display'] = df.apply(
            lambda row: row['Provider'] + ' - ' + row['Provider_Type'] if row['Provider'] == 'Vodafone' else row['Provider'], axis=1)
        df['Provider_Type_Display'] = df.apply(
            lambda row: 'Vodafone-' + row['Provider_Type'] if row['Provider'] == 'Vodafone' else row['Provider_Type'], axis=1)

    return regular_df, unlimited_df


regular_df, unlimited_df = load_data()


# ==================== EXPORT HELPER ====================
def csv_export_button(df, filename, label="⬇ Export CSV", extra_cols=None):
    base_cols = ['Country', 'Provider', 'Provider_Type', 'plan name',
                 'Size_GB', 'plan_frequency_days', 'Cost in Euro', 'Price_per_GB']
    if extra_cols:
        base_cols = base_cols + extra_cols
    export_cols = [c for c in base_cols if c in df.columns]

    export_df = df[export_cols].rename(columns={
        'plan name': 'Plan Name',
        'Size_GB': 'Data (GB)',
        'plan_frequency_days': 'Duration (Days)',
        'Cost in Euro': 'Retail Price (EUR)',
        'Price_per_GB': 'Price per GB (EUR)',
        'Provider_Type': 'Provider Type',
        'pct_diff': '% vs Vodafone Benchmark',
        'competitive_position': 'Competitive Position'
    })

    st.download_button(
        label=label,
        data=export_df.to_csv(index=False).encode('utf-8'),
        file_name=f"{filename}.csv",
        mime='text/csv'
    )


# ==================== TITLE ====================
st.title("📊 eSIM Pricing Analysis Dashboard")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Market Explorer",
    "🔍 Vodafone Comparison",
    "♾️ Unlimited Plans",
    "📅 Month-on-Month Trends",
    "🌍 Multi-Market Insights"
])


# ==================== TAB 1: MARKET EXPLORER ====================
with tab1:
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.subheader("Filters")

    col1, col2, col3 = st.columns(3)
    col4, col5, col6, col7 = st.columns(4)

    with col1:
        countries_tab1 = ['All'] + sorted(regular_df['Country'].unique().tolist())
        selected_country_tab1 = st.selectbox("Country", countries_tab1, key='tab1_country')

    filtered_df_tab1 = regular_df.copy()
    if selected_country_tab1 != 'All':
        filtered_df_tab1 = filtered_df_tab1[filtered_df_tab1['Country'] == selected_country_tab1]

    with col2:
        provider_types_tab1 = sorted(filtered_df_tab1['Provider_Type'].unique().tolist())
        selected_provider_types_tab1 = st.multiselect("Provider Type", provider_types_tab1, default=[], key='tab1_provider_type')

    if selected_provider_types_tab1:
        filtered_df_tab1 = filtered_df_tab1[filtered_df_tab1['Provider_Type'].isin(selected_provider_types_tab1)]

    with col3:
        providers_tab1 = sorted(filtered_df_tab1['Provider'].unique().tolist())
        selected_providers_tab1 = st.multiselect("Provider", providers_tab1, default=[], key='tab1_provider')

    if selected_providers_tab1:
        filtered_df_tab1 = filtered_df_tab1[filtered_df_tab1['Provider'].isin(selected_providers_tab1)]

    with col4:
        min_data_gb_tab1 = st.text_input("Min Data (GB)", value="", placeholder="e.g., 1", key='tab1_min_data')
    with col5:
        max_data_gb_tab1 = st.text_input("Max Data (GB)", value="", placeholder="e.g., 100", key='tab1_max_data')
    with col6:
        min_duration_tab1 = st.text_input("Min Duration (Days)", value="", placeholder="e.g., 7", key='tab1_min_dur')
    with col7:
        max_duration_tab1 = st.text_input("Max Duration (Days)", value="", placeholder="e.g., 30", key='tab1_max_dur')

    st.markdown("---")
    sort_col_left, _, _ = st.columns([1, 2, 1])
    with sort_col_left:
        sort_by_tab1 = st.selectbox("Sort by", ["Price per GB", "Retail Price"], key='tab1_sort_by')
    st.markdown('</div>', unsafe_allow_html=True)

    def build_sql_query_tab1(country, provider_types, providers, min_data, max_data, min_dur, max_dur):
        query = "SELECT * FROM esim_plans WHERE 1=1"
        params = []
        if country != 'All':
            query += " AND Country = ?"
            params.append(country)
        if provider_types:
            placeholders = ','.join(['?' for _ in provider_types])
            query += f" AND Provider_Type IN ({placeholders})"
            params.extend(provider_types)
        if providers:
            placeholders = ','.join(['?' for _ in providers])
            query += f" AND Provider IN ({placeholders})"
            params.extend(providers)
        if min_data:
            try:
                query += " AND data_amount_MB_numeric >= ?"
                params.append(float(min_data) * 1024)
            except ValueError:
                pass
        if max_data:
            try:
                query += " AND data_amount_MB_numeric <= ?"
                params.append(float(max_data) * 1024)
            except ValueError:
                pass
        if min_dur:
            try:
                query += " AND plan_frequency_days >= ?"
                params.append(int(min_dur))
            except ValueError:
                pass
        if max_dur:
            try:
                query += " AND plan_frequency_days <= ?"
                params.append(int(max_dur))
            except ValueError:
                pass
        query += " ORDER BY Provider, \"plan name\""
        return query, params

    conn_tab1 = sqlite3.connect(':memory:')
    filtered_df_tab1.to_sql('esim_plans', conn_tab1, index=False, if_exists='replace')
    sql_query_tab1, sql_params_tab1 = build_sql_query_tab1(
        selected_country_tab1, selected_provider_types_tab1, selected_providers_tab1,
        min_data_gb_tab1, max_data_gb_tab1, min_duration_tab1, max_duration_tab1
    )
    result_df_tab1 = pd.read_sql_query(sql_query_tab1, conn_tab1, params=sql_params_tab1)
    result_df_tab1 = result_df_tab1[(result_df_tab1['Cost in Euro'] > 0) & (result_df_tab1['Price_per_GB'] > 0)]
    conn_tab1.close()

    st.markdown("---")
    st.markdown("""
    **What this graph shows:** All eSIM plans matching your filters, ranked by the selected pricing metric.
    Use filters to narrow down by country, provider type, data volume, and duration.
    """)
    st.markdown(f'<div class="sort-info">ℹ️ Sorted by: <strong>{sort_by_tab1}</strong> — Ascending (Cheapest First)</div>', unsafe_allow_html=True)

    res_col_t1, exp_col_t1 = st.columns([5, 1])
    with res_col_t1:
        st.subheader(f"Results: {len(result_df_tab1)} plans found")

    if len(result_df_tab1) > 0:
        result_df_tab1['provider_plan'] = result_df_tab1['Provider'] + ' - ' + result_df_tab1['plan name']

        if 'Provider_Type_Display' not in result_df_tab1.columns:
            result_df_tab1['Provider_Type_Display'] = result_df_tab1.apply(
                lambda row: 'Vodafone-' + row['Provider_Type'] if row['Provider'] == 'Vodafone' else row['Provider_Type'], axis=1)
        if 'Provider_Display' not in result_df_tab1.columns:
            result_df_tab1['Provider_Display'] = result_df_tab1['Provider']

        result_df_tab1 = result_df_tab1.groupby('provider_plan', as_index=False).agg({
            'Cost in Euro': 'first', 'Provider_Type': 'first', 'Provider': 'first',
            'Provider_Display': 'first', 'Provider_Type_Display': 'first',
            'plan name': 'first', 'plan_frequency_days': 'first',
            'Size_GB': 'first', 'Price_per_GB': 'first'
        })

        result_df_tab1['hover_text'] = (
            '<b>' + result_df_tab1['plan name'] + '</b><br>' +
            'Provider: ' + result_df_tab1['Provider_Display'] + '<br>' +
            'Provider Type: ' + result_df_tab1['Provider_Type'] + '<br>' +
            'Duration: ' + result_df_tab1['plan_frequency_days'].astype(str) + ' days<br>' +
            'Data: ' + result_df_tab1['Size_GB'].astype(str) + ' GB<br>' +
            'Retail Price: €' + result_df_tab1['Cost in Euro'].round(2).astype(str) + '<br>' +
            'Price per GB: €' + result_df_tab1['Price_per_GB'].round(2).astype(str)
        )

        all_types_t1 = result_df_tab1['Provider_Type_Display'].unique()
        color_map_t1 = get_diverse_color_map(all_types_t1)
        result_df_tab1['color'] = result_df_tab1['Provider_Type_Display'].map(color_map_t1)

        sort_column = 'Price_per_GB' if sort_by_tab1 == "Price per GB" else 'Cost in Euro'
        x_axis_title = "Price per GB (EUR)" if sort_by_tab1 == "Price per GB" else "Retail Price (EUR)"
        result_df_tab1 = result_df_tab1.sort_values(sort_column, ascending=True)

        fig_tab1 = go.Figure()
        fig_tab1.add_trace(go.Bar(
            y=result_df_tab1['provider_plan'], x=result_df_tab1[sort_column],
            orientation='h', marker_color=result_df_tab1['color'],
            hovertext=result_df_tab1['hover_text'], hoverinfo='text',
            text='€' + result_df_tab1[sort_column].round(2).astype(str),
            textposition='outside', showlegend=False
        ))
        for ptype in sorted(all_types_t1):
            fig_tab1.add_trace(go.Bar(x=[None], y=[None], name=ptype, marker_color=color_map_t1[ptype], showlegend=True))

        fig_tab1.update_layout(
            title=dict(text=f"eSIM Plan Pricing Comparison (by {sort_by_tab1})", font=dict(size=20)),
            xaxis=dict(title=x_axis_title, gridcolor='#e0e0e0'),
            yaxis=dict(title="Provider - Plan", tickfont=dict(size=10)),
            plot_bgcolor='white', height=max(600, len(result_df_tab1) * 25),
            margin=dict(l=300, r=150), hovermode='closest', showlegend=True,
            legend=dict(title="Provider Type", orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )

        with exp_col_t1:
            st.markdown("<br>", unsafe_allow_html=True)
            csv_export_button(result_df_tab1, "market_explorer")

        st.plotly_chart(fig_tab1, use_container_width=True)
    else:
        st.info("No plans match the selected filters.")


# ==================== TAB 2: VODAFONE COMPARISON ====================
with tab2:
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.subheader("Filters")

    col1_t2, col2_t2, col3_t2 = st.columns(3)

    with col1_t2:
        countries_tab2 = sorted(regular_df['Country'].unique().tolist())
        default_country_idx = countries_tab2.index('Germany') if 'Germany' in countries_tab2 else 0
        selected_country_tab2 = st.selectbox("Country", countries_tab2, index=default_country_idx, key='tab2_country')

    tab2_df = regular_df[(regular_df['Country'] == selected_country_tab2) & (regular_df['Type'] == 'Domestic')].copy()

    with col2_t2:
        provider_types_tab2 = sorted(tab2_df['Provider_Type'].unique().tolist())
        selected_provider_types_tab2 = st.multiselect("Provider Type", provider_types_tab2, default=[], key='tab2_provider_type')

    filtered_tab2_df = tab2_df.copy()
    if selected_provider_types_tab2:
        filtered_tab2_df = filtered_tab2_df[filtered_tab2_df['Provider_Type'].isin(selected_provider_types_tab2)]

    with col3_t2:
        providers_tab2 = sorted(filtered_tab2_df['Provider'].unique().tolist())
        selected_providers_tab2 = st.multiselect("Provider", providers_tab2, default=[], key='tab2_provider')

    if selected_providers_tab2:
        filtered_tab2_df = filtered_tab2_df[filtered_tab2_df['Provider'].isin(selected_providers_tab2)]

    st.markdown('</div>', unsafe_allow_html=True)

    # ---- GRAPH 1 ----
    st.markdown("---")
    st.subheader("📊 Graph 1: Vodafone Competitive Analysis by Data & Duration Range")
    st.markdown("""
    **What this graph shows:** Compare all plans in your selected tier against a chosen Vodafone benchmark.
    Green = cheaper than Vodafone. Orange = more expensive.
    """)

    col1_g1, col2_g1, col3_g1, col4_g1 = st.columns(4)
    with col1_g1:
        min_data_g1 = st.text_input("Min Data (GB)", value="", placeholder="e.g., 1", key='g1_min_data')
    with col2_g1:
        max_data_g1 = st.text_input("Max Data (GB)", value="", placeholder="e.g., 100", key='g1_max_data')
    with col3_g1:
        min_duration_g1 = st.text_input("Min Duration (Days)", value="", placeholder="e.g., 7", key='g1_min_dur')
    with col4_g1:
        max_duration_g1 = st.text_input("Max Duration (Days)", value="", placeholder="e.g., 30", key='g1_max_dur')

    sort_col_g1 = st.columns([1, 3])[0]
    with sort_col_g1:
        sort_by_g1 = st.selectbox("Sort by", ["Price per GB", "Retail Price"], key='g1_sort_by')

    sort_column_g1 = 'Price_per_GB' if sort_by_g1 == "Price per GB" else 'Cost in Euro'

    vodafone_pool = tab2_df[tab2_df['Provider'] == 'Vodafone'].copy()
    vodafone_pool = vodafone_pool[(vodafone_pool['Cost in Euro'] > 0) & (vodafone_pool['Price_per_GB'] > 0)]

    if len(vodafone_pool) > 0:
        def make_vf_label(row):
            return (f"{row['plan name']}  |  {int(row['plan_frequency_days'])}d  |  "
                    f"€{row['Cost in Euro']:.2f}  |  €{row['Price_per_GB']:.2f}/GB")
        vodafone_pool = vodafone_pool.sort_values('plan name')
        vf_labels = vodafone_pool.apply(make_vf_label, axis=1).tolist()
        vf_plan_names = vodafone_pool['plan name'].tolist()
        selected_vf_label = st.selectbox("🔴 Select Vodafone Plan to Compare Against", options=vf_labels, index=0, key='g1_vf_plan_select')
        selected_vf_plan = vf_plan_names[vf_labels.index(selected_vf_label)]
    else:
        selected_vf_plan = None
        st.warning("⚠️ No Vodafone plans found for the selected country.")

    if selected_vf_plan:
        selected_vf_row = vodafone_pool[vodafone_pool['plan name'] == selected_vf_plan].iloc[0]
        benchmark_value = selected_vf_row[sort_column_g1]

        competitor_pool = tab2_df[tab2_df['Provider'] != 'Vodafone'].copy()
        competitor_pool = competitor_pool[(competitor_pool['Cost in Euro'] > 0) & (competitor_pool['Price_per_GB'] > 0)]

        if selected_provider_types_tab2:
            competitor_pool = competitor_pool[competitor_pool['Provider_Type'].isin(selected_provider_types_tab2)]
        non_vf_selected = [p for p in selected_providers_tab2 if p != 'Vodafone']
        if non_vf_selected:
            competitor_pool = competitor_pool[competitor_pool['Provider'].isin(non_vf_selected)]
        if min_data_g1:
            try: competitor_pool = competitor_pool[competitor_pool['Size_GB'] >= float(min_data_g1)]
            except ValueError: pass
        if max_data_g1:
            try: competitor_pool = competitor_pool[competitor_pool['Size_GB'] <= float(max_data_g1)]
            except ValueError: pass
        if min_duration_g1:
            try: competitor_pool = competitor_pool[competitor_pool['plan_frequency_days'] >= int(min_duration_g1)]
            except ValueError: pass
        if max_duration_g1:
            try: competitor_pool = competitor_pool[competitor_pool['plan_frequency_days'] <= int(max_duration_g1)]
            except ValueError: pass

        vf_selected_df = vodafone_pool[vodafone_pool['plan name'] == selected_vf_plan].copy()
        all_plans_g1 = pd.concat([vf_selected_df, competitor_pool], ignore_index=True)

        st.success(f"✓ Benchmark: **{selected_vf_plan}** — {sort_by_g1}: €{benchmark_value:.2f} | Comparing against {len(competitor_pool['Provider'].unique())} competitor provider(s)")
        st.markdown(f'<div class="sort-info">ℹ️ Benchmark: <strong>{selected_vf_plan}</strong> (€{benchmark_value:.2f})</div>', unsafe_allow_html=True)

        if len(all_plans_g1) > 0:
            all_plans_g1['provider_plan'] = all_plans_g1['Provider'] + ' - ' + all_plans_g1['plan name']
            all_plans_g1 = all_plans_g1.groupby('provider_plan', as_index=False).agg({
                'Provider': 'first', 'Price_per_GB': 'first', 'Provider_Type': 'first',
                'Provider_Display': 'first', 'plan name': 'first',
                'plan_frequency_days': 'first', 'Size_GB': 'first', 'Cost in Euro': 'first'
            })

            def get_plan_color_g1(row):
                if row['Provider'] == 'Vodafone': return VODAFONE_RED
                val = row['Price_per_GB'] if sort_by_g1 == "Price per GB" else row['Cost in Euro']
                return '#28A745' if val < benchmark_value else '#FD7E14'

            all_plans_g1['plan_color'] = all_plans_g1.apply(get_plan_color_g1, axis=1)
            all_plans_g1['pct_diff'] = (all_plans_g1[sort_column_g1] - benchmark_value) / benchmark_value * 100
            all_plans_g1['cheaper_than_vodafone'] = all_plans_g1.apply(
                lambda row: 'Vodafone' if row['Provider'] == 'Vodafone'
                else ('Yes' if row['pct_diff'] < 0 else 'No'),
                axis=1
            )
            all_plans_g1 = all_plans_g1.sort_values(sort_column_g1, ascending=True)

            all_plans_g1['hover_text'] = (
                '<b>' + all_plans_g1['plan name'] + '</b><br>' +
                'Provider: ' + all_plans_g1['Provider_Display'] + '<br>' +
                'Duration: ' + all_plans_g1['plan_frequency_days'].astype(str) + ' days<br>' +
                'Data: ' + all_plans_g1['Size_GB'].astype(str) + ' GB<br>' +
                'Retail Price: €' + all_plans_g1['Cost in Euro'].round(2).astype(str) + '<br>' +
                'Price per GB: €' + all_plans_g1['Price_per_GB'].round(2).astype(str) + '<br>' +
                '% vs Vodafone: ' + all_plans_g1['pct_diff'].round(1).astype(str) + '%'
            )
            text_labels = all_plans_g1.apply(
                lambda row: f"▶ {row['plan name']} (benchmark)" if row['Provider'] == 'Vodafone' else f"{row['pct_diff']:.1f}% vs Vodafone",
                axis=1
            )

            fig_g1 = go.Figure()
            fig_g1.add_trace(go.Bar(
                y=all_plans_g1['provider_plan'], x=all_plans_g1[sort_column_g1],
                orientation='h', marker_color=all_plans_g1['plan_color'],
                hovertext=all_plans_g1['hover_text'], hoverinfo='text',
                text=text_labels, textposition='inside', textfont=dict(size=9)
            ))
            fig_g1.update_layout(
                title=dict(text=f"Plans vs. {selected_vf_plan} (by {sort_by_g1})", font=dict(size=18)),
                xaxis=dict(title=f"{sort_by_g1} (EUR)", gridcolor='#e0e0e0'),
                yaxis=dict(title="", tickfont=dict(size=10)),
                plot_bgcolor='white', height=max(400, len(all_plans_g1) * 30),
                margin=dict(l=250), showlegend=False
            )

            g1_res_col, g1_exp_col = st.columns([5, 1])
            with g1_exp_col:
                st.markdown("<br>", unsafe_allow_html=True)
                csv_export_button(all_plans_g1, "vodafone_comparison_g1", extra_cols=['pct_diff', 'cheaper_than_vodafone'])

            st.plotly_chart(fig_g1, use_container_width=True)
            st.markdown("**Colour Legend:** 🔴 Red = Vodafone benchmark &nbsp;|&nbsp; 🟢 Green = Cheaper &nbsp;|&nbsp; 🟠 Orange = More expensive")
        else:
            st.info("No competitor plans match the selected filters.")

    # ---- GRAPH 2 ----
    st.markdown("---")
    st.subheader("📊 Graph 2: Average Price by Provider")
    st.markdown("""
    **What this graph shows:** Average price across all plans per provider.
    Green = cheaper than Vodafone average. Orange = more expensive.
    """)

    col1_g2, col2_g2 = st.columns(2)
    with col1_g2:
        min_duration_g2 = st.text_input("Min Duration (Days)", value="", placeholder="e.g., 7", key='g2_min_dur')
    with col2_g2:
        max_duration_g2 = st.text_input("Max Duration (Days)", value="", placeholder="e.g., 30", key='g2_max_dur')

    sort_col_g2 = st.columns([1, 3])[0]
    with sort_col_g2:
        sort_by_g2 = st.selectbox("Sort by", ["Price per GB", "Retail Price"], key='g2_sort_by')

    filtered_g2_df = tab2_df.copy()
    filtered_g2_df = filtered_g2_df[(filtered_g2_df['Cost in Euro'] > 0) & (filtered_g2_df['Price_per_GB'] > 0)]

    if selected_provider_types_tab2:
        filtered_g2_df = filtered_g2_df[
            filtered_g2_df['Provider_Type'].isin(selected_provider_types_tab2) | (filtered_g2_df['Provider'] == 'Vodafone')]
    if selected_providers_tab2:
        non_vf = [p for p in selected_providers_tab2 if p != 'Vodafone']
        filtered_g2_df = filtered_g2_df[filtered_g2_df['Provider'].isin(non_vf) | (filtered_g2_df['Provider'] == 'Vodafone')]
    if min_duration_g2:
        try: filtered_g2_df = filtered_g2_df[filtered_g2_df['plan_frequency_days'] >= int(min_duration_g2)]
        except ValueError: pass
    if max_duration_g2:
        try: filtered_g2_df = filtered_g2_df[filtered_g2_df['plan_frequency_days'] <= int(max_duration_g2)]
        except ValueError: pass

    st.markdown(f'<div class="sort-info">ℹ️ Sorted by: <strong>Average {sort_by_g2}</strong> — Ascending (Cheapest First)</div>', unsafe_allow_html=True)

    if len(filtered_g2_df) > 0:
        agg_col = 'Price_per_GB' if sort_by_g2 == "Price per GB" else 'Cost in Euro'
        provider_stats = filtered_g2_df.groupby('Provider').agg(
            Avg_Metric=(agg_col, 'mean'),
            Plan_Count=('plan name', 'count'),
            Provider_Type=('Provider_Type', 'first'),
            Provider_Display=('Provider_Display', 'first')
        ).reset_index()

        vodafone_avg_arr = provider_stats[provider_stats['Provider'] == 'Vodafone']['Avg_Metric'].values
        vodafone_avg = vodafone_avg_arr[0] if len(vodafone_avg_arr) > 0 else None

        def get_bar_color_g2(row):
            if row['Provider'] == 'Vodafone': return VODAFONE_RED
            elif vodafone_avg and row['Avg_Metric'] < vodafone_avg: return '#28A745'
            else: return '#FD7E14'

        provider_stats['color'] = provider_stats.apply(get_bar_color_g2, axis=1)
        provider_stats = provider_stats.sort_values('Avg_Metric', ascending=True)
        provider_stats['hover_text'] = (
            '<b>' + provider_stats['Provider_Display'] + '</b><br>' +
            ('Avg Price per GB: €' if sort_by_g2 == "Price per GB" else 'Avg Retail Price: €') +
            provider_stats['Avg_Metric'].round(2).astype(str) + '<br>' +
            'Plan Count: ' + provider_stats['Plan_Count'].astype(str)
        )

        fig_g2 = go.Figure()
        fig_g2.add_trace(go.Bar(
            x=provider_stats['Provider_Display'], y=provider_stats['Avg_Metric'],
            marker_color=provider_stats['color'],
            hovertext=provider_stats['hover_text'], hoverinfo='text',
            text=provider_stats['Plan_Count'].astype(str) + ' plans', textposition='outside'
        ))
        fig_g2.update_layout(
            title=dict(text=f"Average {sort_by_g2} by Provider", font=dict(size=18)),
            xaxis=dict(title="Provider", tickangle=-45, tickfont=dict(size=10)),
            yaxis=dict(title=f"Average {sort_by_g2} (EUR)", gridcolor='#e0e0e0'),
            plot_bgcolor='white', height=600, margin=dict(b=150, t=80), showlegend=False
        )

        g2_res_col, g2_exp_col = st.columns([5, 1])
        with g2_exp_col:
            st.markdown("<br>", unsafe_allow_html=True)
            csv_export_button(filtered_g2_df, "vodafone_comparison_g2")

        st.plotly_chart(fig_g2, use_container_width=True)
        st.markdown("**Colour Legend:** 🔴 Red = Vodafone &nbsp;|&nbsp; 🟢 Green = Cheaper than Vodafone avg &nbsp;|&nbsp; 🟠 Orange = More expensive")
    else:
        st.info("No plans match the selected filters.")


# ==================== TAB 3: UNLIMITED PLANS ====================
with tab3:
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.subheader("Filters")

    col1_t3, col2_t3, col3_t3 = st.columns(3)
    col4_t3, col5_t3 = st.columns(2)

    with col1_t3:
        countries_tab3 = ['All'] + sorted(unlimited_df['Country'].unique().tolist())
        selected_country_tab3 = st.selectbox("Country", countries_tab3, key='tab3_country')

    filtered_df_tab3 = unlimited_df.copy()
    if selected_country_tab3 != 'All':
        filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['Country'] == selected_country_tab3]

    with col2_t3:
        provider_types_tab3 = sorted(filtered_df_tab3['Provider_Type'].unique().tolist())
        selected_provider_types_tab3 = st.multiselect("Provider Type", provider_types_tab3, default=[], key='tab3_provider_type')

    if selected_provider_types_tab3:
        filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['Provider_Type'].isin(selected_provider_types_tab3)]

    with col3_t3:
        providers_tab3 = sorted(filtered_df_tab3['Provider'].unique().tolist())
        selected_providers_tab3 = st.multiselect("Provider", providers_tab3, default=[], key='tab3_provider')

    if selected_providers_tab3:
        filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['Provider'].isin(selected_providers_tab3)]

    with col4_t3:
        min_duration_tab3 = st.text_input("Min Duration (Days)", value="", placeholder="e.g., 1", key='tab3_min_dur')
    with col5_t3:
        max_duration_tab3 = st.text_input("Max Duration (Days)", value="", placeholder="e.g., 30", key='tab3_max_dur')

    st.markdown("---")
    sort_col_tab3 = st.columns([1, 3])[0]
    with sort_col_tab3:
        st.selectbox("Sort by", ["Retail Price"], key='tab3_sort_by', disabled=True,
                     help="Unlimited plans sorted by Retail Price only")
    st.markdown('</div>', unsafe_allow_html=True)

    if min_duration_tab3:
        try: filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['plan_frequency_days'] >= int(min_duration_tab3)]
        except ValueError: pass
    if max_duration_tab3:
        try: filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['plan_frequency_days'] <= int(max_duration_tab3)]
        except ValueError: pass

    filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['Cost in Euro'] > 0]

    st.markdown("---")
    st.markdown("**What this graph shows:** Unlimited data plans ranked by retail price and duration.")
    st.markdown('<div class="sort-info">ℹ️ Sorted by: <strong>Retail Price</strong> — Ascending (Cheapest First)</div>', unsafe_allow_html=True)

    t3_res_col, t3_exp_col = st.columns([5, 1])
    with t3_res_col:
        st.subheader(f"Results: {len(filtered_df_tab3)} unlimited plans found")

    if len(filtered_df_tab3) > 0:
        filtered_df_tab3['provider_plan'] = filtered_df_tab3['Provider'] + ' - ' + filtered_df_tab3['plan name']
        filtered_df_tab3 = filtered_df_tab3.groupby('provider_plan', as_index=False).agg({
            'Cost in Euro': 'first', 'Provider_Type': 'first', 'Provider': 'first',
            'Provider_Display': 'first', 'Provider_Type_Display': 'first',
            'plan name': 'first', 'plan_frequency_days': 'first'
        })
        filtered_df_tab3['hover_text'] = (
            '<b>' + filtered_df_tab3['plan name'] + '</b><br>' +
            'Provider: ' + filtered_df_tab3['Provider_Display'] + '<br>' +
            'Provider Type: ' + filtered_df_tab3['Provider_Type'] + '<br>' +
            'Duration: ' + filtered_df_tab3['plan_frequency_days'].astype(str) + ' days<br>' +
            'Data: Unlimited<br>' +
            'Retail Price: €' + filtered_df_tab3['Cost in Euro'].round(2).astype(str)
        )
        filtered_df_tab3 = filtered_df_tab3.sort_values('Cost in Euro', ascending=True)
        all_types_t3 = filtered_df_tab3['Provider_Type_Display'].unique()
        color_map_t3 = get_diverse_color_map(all_types_t3)
        filtered_df_tab3['color'] = filtered_df_tab3['Provider_Type_Display'].map(color_map_t3)

        fig_tab3 = go.Figure()
        fig_tab3.add_trace(go.Bar(
            y=filtered_df_tab3['provider_plan'], x=filtered_df_tab3['Cost in Euro'],
            orientation='h', marker_color=filtered_df_tab3['color'],
            hovertext=filtered_df_tab3['hover_text'], hoverinfo='text',
            text='€' + filtered_df_tab3['Cost in Euro'].round(2).astype(str),
            textposition='outside', showlegend=False
        ))
        for ptype in sorted(all_types_t3):
            fig_tab3.add_trace(go.Bar(x=[None], y=[None], name=ptype, marker_color=color_map_t3[ptype], showlegend=True))

        fig_tab3.update_layout(
            title=dict(text="Unlimited eSIM Plan Pricing (by Retail Price)", font=dict(size=20)),
            xaxis=dict(title="Retail Price (EUR)", gridcolor='#e0e0e0'),
            yaxis=dict(title="Provider - Plan", tickfont=dict(size=10)),
            plot_bgcolor='white', height=max(600, len(filtered_df_tab3) * 25),
            margin=dict(l=300, r=150), hovermode='closest', showlegend=True,
            legend=dict(title="Provider Type", orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )

        with t3_exp_col:
            st.markdown("<br>", unsafe_allow_html=True)
            csv_export_button(filtered_df_tab3, "unlimited_plans")

        st.plotly_chart(fig_tab3, use_container_width=True)
    else:
        st.info("No unlimited plans match the selected filters.")


# ==================== TAB 4: MONTH-ON-MONTH TRENDS ====================
with tab4:
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.subheader("Filters")

    col1_t4, col2_t4 = st.columns(2)
    col3_t4, col4_t4, col5_t4 = st.columns(3)
    col6_t4, col7_t4, col8_t4, col9_t4 = st.columns(4)

    with col1_t4:
        min_date = regular_df['updated_dtm'].min().date()
        max_date = regular_df['updated_dtm'].max().date()
        start_date_t4 = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date, key='tab4_start_date')
    with col2_t4:
        end_date_t4 = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date, key='tab4_end_date')
    with col3_t4:
        countries_tab4 = sorted(regular_df['Country'].unique().tolist())
        selected_country_tab4 = st.selectbox("Country", countries_tab4, key='tab4_country')

    filtered_t4_df = regular_df[
        (regular_df['Country'] == selected_country_tab4) &
        (regular_df['updated_dtm'].dt.date >= start_date_t4) &
        (regular_df['updated_dtm'].dt.date <= end_date_t4)
    ].copy()

    with col4_t4:
        provider_types_tab4 = sorted(filtered_t4_df['Provider_Type'].unique().tolist())
        selected_provider_types_tab4 = st.multiselect("Provider Type", provider_types_tab4, default=[], key='tab4_provider_type')
    if selected_provider_types_tab4:
        filtered_t4_df = filtered_t4_df[filtered_t4_df['Provider_Type'].isin(selected_provider_types_tab4)]

    with col5_t4:
        providers_tab4 = sorted(filtered_t4_df['Provider'].unique().tolist())
        selected_providers_tab4 = st.multiselect("Provider", providers_tab4, default=[], key='tab4_provider')
    if selected_providers_tab4:
        filtered_t4_df = filtered_t4_df[filtered_t4_df['Provider'].isin(selected_providers_tab4)]

    with col6_t4:
        min_data_gb_t4 = st.text_input("Min Data (GB)", value="", placeholder="e.g., 1", key='tab4_min_data')
    with col7_t4:
        max_data_gb_t4 = st.text_input("Max Data (GB)", value="", placeholder="e.g., 100", key='tab4_max_data')
    with col8_t4:
        min_duration_t4 = st.text_input("Min Duration (Days)", value="", placeholder="e.g., 7", key='tab4_min_dur')
    with col9_t4:
        max_duration_t4 = st.text_input("Max Duration (Days)", value="", placeholder="e.g., 30", key='tab4_max_dur')

    st.markdown('</div>', unsafe_allow_html=True)

    if min_data_gb_t4:
        try: filtered_t4_df = filtered_t4_df[filtered_t4_df['Size_GB'] >= float(min_data_gb_t4)]
        except ValueError: pass
    if max_data_gb_t4:
        try: filtered_t4_df = filtered_t4_df[filtered_t4_df['Size_GB'] <= float(max_data_gb_t4)]
        except ValueError: pass
    if min_duration_t4:
        try: filtered_t4_df = filtered_t4_df[filtered_t4_df['plan_frequency_days'] >= int(min_duration_t4)]
        except ValueError: pass
    if max_duration_t4:
        try: filtered_t4_df = filtered_t4_df[filtered_t4_df['plan_frequency_days'] <= int(max_duration_t4)]
        except ValueError: pass

    filtered_t4_df = filtered_t4_df[(filtered_t4_df['Cost in Euro'] > 0) & (filtered_t4_df['Price_per_GB'] > 0)]

    st.markdown("---")
    sort_max_cols_t4 = st.columns([1, 1, 2])
    with sort_max_cols_t4[0]:
        sort_by_t4 = st.selectbox("Sort by", ["Price per GB", "Retail Price"], key='tab4_sort_by')
    with sort_max_cols_t4[1]:
        max_lines_t4 = st.number_input("Max Lines to Display", min_value=1, max_value=50, value=10, key='tab4_max_lines')

    st.markdown("---")

    if len(filtered_t4_df) > 0:
        st.markdown("**What this graph shows:** Price trends over time for plan combinations with the most price movement.")
        st.markdown(f'<div class="sort-info">ℹ️ Sorted by: <strong>{sort_by_t4}</strong> — Top combinations by price movement</div>', unsafe_allow_html=True)

        filtered_t4_df['month'] = filtered_t4_df['updated_dtm'].dt.to_period('M')
        metric_col = 'Avg_Price_per_GB' if sort_by_t4 == "Price per GB" else 'Avg_Retail_Price'
        y_axis_title_t4 = "Average Price per GB (EUR)" if sort_by_t4 == "Price per GB" else "Average Retail Price (EUR)"
        chart_title_t4 = "Price per GB Trends Over Time" if sort_by_t4 == "Price per GB" else "Retail Price Trends Over Time"
        hover_metric_label = "Avg Price per GB" if sort_by_t4 == "Price per GB" else "Avg Retail Price"

        grouped = filtered_t4_df.groupby(
            ['Country', 'Provider', 'Provider_Type', 'Provider_Display', 'Size_GB', 'plan_frequency_days', 'month']
        ).agg({
            'Cost in Euro': 'mean', 'Price_per_GB': 'mean',
            'plan name': lambda x: ', '.join([str(n) for n in x.unique() if pd.notna(n)])
        }).reset_index()
        grouped.columns = ['Country', 'Provider', 'Provider_Type', 'Provider_Display',
                           'Size_GB', 'Duration', 'Month', 'Avg_Retail_Price', 'Avg_Price_per_GB', 'Plan_Names']
        grouped = grouped[(grouped['Avg_Retail_Price'] > 0) & (grouped['Avg_Price_per_GB'] > 0)]
        grouped['combo'] = grouped['Provider_Display'] + ' - ' + grouped['Size_GB'].astype(str) + 'GB - ' + grouped['Duration'].astype(str) + 'days'

        variance_stats = grouped.groupby('combo')[metric_col].agg(['std', 'count']).reset_index()
        variance_stats = variance_stats[variance_stats['count'] > 1].sort_values('std', ascending=False)
        top_combos = variance_stats.head(max_lines_t4)['combo'].tolist()

        if len(top_combos) > 0:
            plot_data = grouped[grouped['combo'].isin(top_combos)]
            st.subheader(f"Month-on-Month Price Trends (Top {len(top_combos)} by {sort_by_t4} Movement)")

            SOLID_50 = [
                '#0057FF','#00C444','#FF8C00','#9B00FF','#00CED1','#FFD700','#FF1493','#00A86B','#FF6600','#4B0082',
                '#39FF14','#FF00FF','#1E90FF','#8B4513','#00FA9A','#FF4500','#BA55D3','#20B2AA','#DAA520','#7FFF00',
                '#00BFFF','#FF69B4','#228B22','#9400D3','#F4A460','#40E0D0','#FF7F50','#6495ED','#ADFF2F','#C71585',
            ]
            combo_providers = {row['combo']: row['Provider'] for _, row in plot_data.drop_duplicates('combo').iterrows()}
            non_vf_combos = [c for c in top_combos if combo_providers.get(c, '') != 'Vodafone']
            vf_combos = [c for c in top_combos if combo_providers.get(c, '') == 'Vodafone']
            line_color_map = {c: VODAFONE_RED for c in vf_combos}
            line_color_map.update({c: SOLID_50[i % len(SOLID_50)] for i, c in enumerate(non_vf_combos)})

            fig_t4 = go.Figure()
            for combo in top_combos:
                combo_data = plot_data[plot_data['combo'] == combo].sort_values('Month')
                combo_data['month_str'] = combo_data['Month'].dt.strftime('%b %Y')
                hover_text = [
                    f"<b>{row['combo']}</b><br>Month: {row['month_str']}<br>"
                    f"Data: {row['Size_GB']}GB | Duration: {row['Duration']} days<br>"
                    f"{hover_metric_label}: €{row[metric_col]:.2f}<br>"
                    f"Avg Retail Price: €{row['Avg_Retail_Price']:.2f}<br>"
                    f"Avg Price per GB: €{row['Avg_Price_per_GB']:.2f}"
                    for _, row in combo_data.iterrows()
                ]
                fig_t4.add_trace(go.Scatter(
                    x=combo_data['month_str'], y=combo_data[metric_col],
                    mode='lines+markers', name=combo,
                    line=dict(color=line_color_map.get(combo, '#333333'), width=2),
                    marker=dict(size=8), hovertext=hover_text, hoverinfo='text'
                ))

            fig_t4.update_layout(
                title=dict(text=chart_title_t4, font=dict(size=20)),
                xaxis=dict(title="Month", tickangle=-45),
                yaxis=dict(title=y_axis_title_t4, gridcolor='#e0e0e0'),
                plot_bgcolor='white', height=600, hovermode='closest',
                showlegend=True, legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02, font=dict(size=9))
            )

            t4_res_col, t4_exp_col = st.columns([5, 1])
            with t4_exp_col:
                st.markdown("<br>", unsafe_allow_html=True)
                csv_export_button(filtered_t4_df, "month_on_month_trends")

            st.plotly_chart(fig_t4, use_container_width=True)

            with st.expander("📊 Price Movement Statistics"):
                variance_display = variance_stats.head(max_lines_t4).copy()
                variance_display.columns = ['Plan Combination', f'{sort_by_t4} Movement (€)', 'Months Available']
                st.dataframe(variance_display, use_container_width=True)
        else:
            st.info("Not enough data points. Need at least 2 months of data per plan combination.")
    else:
        st.info("No plans match the selected filters.")


# ==================== TAB 5: MULTI-MARKET INSIGHTS ====================
with tab5:
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.subheader("Filters")

    col1_t5, col2_t5, col3_t5 = st.columns(3)

    # Step 1 — Provider Type first (no dependency)
    with col1_t5:
        all_provider_types_t5 = sorted(regular_df['Provider_Type'].unique().tolist())
        selected_provider_types_t5 = st.multiselect(
            "Provider Type", all_provider_types_t5, default=[], key='tab5_provider_type')

    filtered_t5_df = regular_df.copy()
    if selected_provider_types_t5:
        filtered_t5_df = filtered_t5_df[filtered_t5_df['Provider_Type'].isin(selected_provider_types_t5)]

    # Step 2 — Provider updates based on selected provider type
    with col2_t5:
        providers_t5 = sorted(filtered_t5_df['Provider'].unique().tolist())
        selected_providers_t5 = st.multiselect(
            "Provider", providers_t5, default=[], key='tab5_provider')

    if selected_providers_t5:
        filtered_t5_df = filtered_t5_df[filtered_t5_df['Provider'].isin(selected_providers_t5)]

    # Step 3 — Countries updates based on selected provider type AND provider
    with col3_t5:
        available_countries_t5 = sorted(filtered_t5_df['Country'].unique().tolist())
        selected_countries_t5 = st.multiselect(
            "Countries", available_countries_t5, default=available_countries_t5, key='tab5_countries')

    if selected_countries_t5:
        filtered_t5_df = filtered_t5_df[filtered_t5_df['Country'].isin(selected_countries_t5)]

    col4_t5, col5_t5, col6_t5, col7_t5, col8_t5 = st.columns(5)
    with col4_t5:
        sort_by_t5 = st.selectbox("Sort By", ["Price per GB", "Retail Price"], key='tab5_sort_by')
    with col5_t5:
        min_data_t5 = st.text_input("Min Data (GB)", value="", placeholder="e.g., 1", key='tab5_min_data')
    with col6_t5:
        max_data_t5 = st.text_input("Max Data (GB)", value="", placeholder="e.g., 100", key='tab5_max_data')
    with col7_t5:
        min_duration_t5 = st.text_input("Min Duration (Days)", value="", placeholder="e.g., 7", key='tab5_min_dur')
    with col8_t5:
        max_duration_t5 = st.text_input("Max Duration (Days)", value="", placeholder="e.g., 30", key='tab5_max_dur')

    st.markdown('</div>', unsafe_allow_html=True)

    if min_data_t5:
        try: filtered_t5_df = filtered_t5_df[filtered_t5_df['Size_GB'] >= float(min_data_t5)]
        except ValueError: pass
    if max_data_t5:
        try: filtered_t5_df = filtered_t5_df[filtered_t5_df['Size_GB'] <= float(max_data_t5)]
        except ValueError: pass
    if min_duration_t5:
        try: filtered_t5_df = filtered_t5_df[filtered_t5_df['plan_frequency_days'] >= int(min_duration_t5)]
        except ValueError: pass
    if max_duration_t5:
        try: filtered_t5_df = filtered_t5_df[filtered_t5_df['plan_frequency_days'] <= int(max_duration_t5)]
        except ValueError: pass

    filtered_t5_df = filtered_t5_df[
        (filtered_t5_df['Cost in Euro'] > 0) & (filtered_t5_df['Price_per_GB'] > 0)
    ].drop_duplicates()

    sort_column_t5 = 'Price_per_GB' if sort_by_t5 == "Price per GB" else 'Cost in Euro'
    x_axis_title_t5 = "Price per GB (EUR)" if sort_by_t5 == "Price per GB" else "Retail Price (EUR)"

    st.markdown("---")
    st.markdown("""
    **What this view shows:** Select a Provider Type or Provider to see which markets they operate in.
    Countries update automatically based on your selection. Narrow down further using data and duration filters.
    """)

    if len(selected_countries_t5) < 2:
        st.info("Please select a Provider Type or Provider first — Countries will update automatically. Ensure at least 2 countries are selected to see a comparison.")
    elif len(filtered_t5_df) == 0:
        st.info("No plans match the selected filters.")
    else:
        filtered_t5_df['provider_plan'] = (
            filtered_t5_df['Country'] + ' | ' +
            filtered_t5_df['Provider'] + ' - ' +
            filtered_t5_df['plan name']
        )
        filtered_t5_df = filtered_t5_df.groupby('provider_plan', as_index=False).agg({
            'Cost in Euro': 'first', 'Price_per_GB': 'first',
            'Provider': 'first', 'Provider_Type': 'first', 'Provider_Display': 'first',
            'plan name': 'first', 'plan_frequency_days': 'first', 'Size_GB': 'first', 'Country': 'first'
        })
        filtered_t5_df = filtered_t5_df.sort_values(sort_column_t5, ascending=True)

        unique_countries_t5 = sorted(filtered_t5_df['Country'].unique().tolist())
        country_color_map = {
            c: VODAFONE_RED if c == 'Vodafone' else COUNTRY_COLORS[i % len(COUNTRY_COLORS)]
            for i, c in enumerate(unique_countries_t5)
        }
        filtered_t5_df['color'] = filtered_t5_df['Country'].map(country_color_map)

        filtered_t5_df['hover_text'] = (
            '<b>' + filtered_t5_df['plan name'] + '</b><br>' +
            'Country: ' + filtered_t5_df['Country'] + '<br>' +
            'Provider: ' + filtered_t5_df['Provider_Display'] + '<br>' +
            'Provider Type: ' + filtered_t5_df['Provider_Type'] + '<br>' +
            'Duration: ' + filtered_t5_df['plan_frequency_days'].astype(str) + ' days<br>' +
            'Data: ' + filtered_t5_df['Size_GB'].astype(str) + ' GB<br>' +
            'Retail Price: €' + filtered_t5_df['Cost in Euro'].round(2).astype(str) + '<br>' +
            'Price per GB: €' + filtered_t5_df['Price_per_GB'].round(2).astype(str)
        )

        t5_res_col, t5_exp_col = st.columns([5, 1])
        with t5_res_col:
            st.subheader(f"Results: {len(filtered_t5_df)} plans across {len(selected_countries_t5)} markets")

        fig_t5 = go.Figure()
        fig_t5.add_trace(go.Bar(
            y=filtered_t5_df['provider_plan'], x=filtered_t5_df[sort_column_t5],
            orientation='h', marker_color=filtered_t5_df['color'],
            hovertext=filtered_t5_df['hover_text'], hoverinfo='text',
            text='€' + filtered_t5_df[sort_column_t5].round(2).astype(str),
            textposition='outside', showlegend=False
        ))
        for country in unique_countries_t5:
            fig_t5.add_trace(go.Bar(x=[None], y=[None], name=country, marker_color=country_color_map[country], showlegend=True))

        fig_t5.update_layout(
            title=dict(text=f"Cross-Market Pricing Comparison (by {sort_by_t5})", font=dict(size=20)),
            xaxis=dict(title=x_axis_title_t5, gridcolor='#e0e0e0'),
            yaxis=dict(title="Country | Provider - Plan", tickfont=dict(size=10)),
            plot_bgcolor='white', height=max(600, len(filtered_t5_df) * 25),
            margin=dict(l=350, r=150), hovermode='closest', showlegend=True,
            legend=dict(title="Country", orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )

        with t5_exp_col:
            st.markdown("<br>", unsafe_allow_html=True)
            csv_export_button(
                filtered_t5_df,
                f"multi_market_{'_'.join(selected_countries_t5)}",
                label="⬇ Export CSV"
            )

        st.plotly_chart(fig_t5, use_container_width=True)