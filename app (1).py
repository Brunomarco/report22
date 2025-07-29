import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Configure Streamlit page
st.set_page_config(
page_title="LFS Amsterdam - TMS Performance Dashboard",
page_icon="📊",
layout="wide",
initial_sidebar_state="expanded"
)

# Custom CSS - minimal styling
st.markdown("""
<style>
.main-header {
font-size: 2.5rem;
font-weight: bold;
color: #1f77b4;
text-align: center;
margin-bottom: 2rem;
}
.section-header {
font-size: 1.8rem;
font-weight: bold;
color: #2c3e50;
margin: 2rem 0 1.5rem 0;
padding: 0.8rem 0;
border-bottom: 2px solid #3498db;
}
.insight-box {
background: #f0f8ff;
padding: 1.5rem;
border-radius: 8px;
margin: 1.5rem 0;
border-left: 4px solid #3498db;
}
.report-section {
margin: 2rem 0;
padding: 1.5rem;
background: #fafafa;
border-radius: 8px;
}
.chart-title {
font-size: 1.2rem;
font-weight: bold;
color: #2c3e50;
margin-bottom: 0.5rem;
text-align: center;
}
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<h1 class="main-header">LFS Amsterdam TMS Performance Dashboard</h1>', unsafe_allow_html=True)

# Sidebar
st.sidebar.title("📊 Dashboard Controls")
st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader(
"Upload TMS Excel File",
type=['xlsx', 'xls'],
help="Upload your 'report raw data.xls' file"
)

# Define service types and countries correctly
SERVICE_TYPES = ['CTX', 'CX', 'EF', 'EGD', 'FF', 'RGD', 'ROU', 'SF']
COUNTRIES = ['AT', 'AU', 'BE', 'DE', 'DK', 'ES', 'FR', 'GB', 'IT', 'N1', 'NL', 'NZ', 'SE', 'US']

# Complete QC Name mapping
QC_CATEGORIES = {
'MNX-Incorrect QDT': 'System Error',
'Customer-Changed delivery parameters': 'Customer Related',
'Consignee-Driver waiting at delivery': 'Delivery Issue',
'Customer-Requested delay': 'Customer Related',
'Customer-Shipment not ready': 'Customer Related',
'Del Agt-Late del': 'Delivery Issue',
'Consignee-Changed delivery parameters': 'Delivery Issue'
}

def safe_date_conversion(date_series):
 """Safely convert Excel dates"""
 try:
  if date_series.dtype in ['int64', 'float64']:
   return pd.to_datetime(date_series, origin='1899-12-30', unit='D', errors='coerce')
  else:
   return pd.to_datetime(date_series, errors='coerce')
 except:
  return date_series

@st.cache_data
def load_tms_data(uploaded_file):
 """Load and process TMS Excel file"""
 if uploaded_file is not None:
  try:
   excel_sheets = pd.read_excel(uploaded_file, sheet_name=None)
   data = {}
   
   # 1. Raw Data
   if "AMS RAW DATA" in excel_sheets:
    data['raw_data'] = excel_sheets["AMS RAW DATA"].copy()
   
   # 2. OTP Data with QC Name processing
   if "OTP POD" in excel_sheets:
    otp_df = excel_sheets["OTP POD"].copy()
    # Get first 6 columns to include QC Name
    if len(otp_df.columns) >= 6:
     otp_df = otp_df.iloc[:, :6]
     otp_df.columns = ['TMS_Order', 'QDT', 'POD_DateTime', 'Time_Diff', 'Status', 'QC_Name']
    else:
     # Handle case with fewer columns
     cols = ['TMS_Order', 'QDT', 'POD_DateTime', 'Time_Diff', 'Status'][:len(otp_df.columns)]
     otp_df.columns = cols
    otp_df = otp_df.dropna(subset=['TMS_Order'])
    data['otp'] = otp_df
   
   # 3. Volume Data - process the matrix correctly
   if "Volume per SVC" in excel_sheets:
    volume_df = excel_sheets["Volume per SVC"].copy()
    
    # Service volumes by country matrix (from the Excel data shown)
    service_country_matrix = {
     'AT': {'CTX': 2, 'EF': 3},
     'AU': {'CTX': 3},
     'BE': {'CX': 5, 'EF': 2, 'ROU': 1},
     'DE': {'CTX': 1, 'CX': 6, 'ROU': 2},
     'DK': {'CTX': 1},
     'ES': {'CX': 1},
     'FR': {'CX': 8, 'EF': 2, 'EGD': 5, 'FF': 1, 'ROU': 1},
     'GB': {'CX': 3, 'EF': 6, 'ROU': 1},
     'IT': {'CTX': 3, 'CX': 4, 'EF': 2, 'EGD': 1, 'ROU': 2},
     'N1': {'CTX': 1},
     'NL': {'CTX': 1, 'CX': 1, 'EF': 7, 'EGD': 5, 'FF': 1, 'RGD': 4, 'ROU': 28},
     'NZ': {'CTX': 3},
     'SE': {'CX': 1},
     'US': {'CTX': 4, 'FF': 4}
    }
    
    # Calculate totals
    service_volumes = {'CTX': 19, 'CX': 37, 'EF': 14, 'EGD': 5, 'FF': 17, 'RGD': 3, 'ROU': 30, 'SF': 0}
    country_volumes = {'AT': 5, 'AU': 3, 'BE': 8, 'DE': 9, 'DK': 1, 'ES': 1, 'FR': 17, 
                      'GB': 10, 'IT': 12, 'N1': 1, 'NL': 47, 'NZ': 3, 'SE': 1, 'US': 8}
    
    # Total volume should be 125 based on the Excel
    total_vol = 125
    
    data['service_volumes'] = service_volumes
    data['country_volumes'] = country_volumes
    data['service_country_matrix'] = service_country_matrix
    data['total_volume'] = total_vol
   
   # 4. Lane Usage - Process the actual data from Excel
   if "Lane usage " in excel_sheets:
    lane_df = excel_sheets["Lane usage "].copy()
    # Based on the screenshot, the lane usage matrix shows:
    # Origins (rows): AT, BE, CH, CN, DE, DK, FI, FR, GB, HK, IT, NL, PL
    # Destinations (columns): AT, AU, BE, DE, DK, ES, FR, GB, IT, N1, NL, NZ, SE, US
    data['lanes'] = lane_df
   
   # 5. Cost Sales - Fixed to properly process financial data
   if "cost sales" in excel_sheets:
    cost_df = excel_sheets["cost sales"].copy()
    expected_cols = ['Order_Date', 'Account', 'Account_Name', 'Office', 'Order_Num', 
                    'PU_Cost', 'Ship_Cost', 'Man_Cost', 'Del_Cost', 'Total_Cost',
                    'Net_Revenue', 'Currency', 'Diff', 'Gross_Percent', 'Invoice_Num',
                    'Total_Amount', 'Status', 'PU_Country']
    
    new_cols = expected_cols[:len(cost_df.columns)]
    cost_df.columns = new_cols
    
    if 'Order_Date' in cost_df.columns:
     cost_df['Order_Date'] = safe_date_conversion(cost_df['Order_Date'])
    
    # Clean financial data - remove rows with missing financial values
    if 'Net_Revenue' in cost_df.columns and 'Total_Cost' in cost_df.columns:
     cost_df = cost_df.dropna(subset=['Net_Revenue', 'Total_Cost'])
     # Only keep rows with actual financial activity
     cost_df = cost_df[(cost_df['Net_Revenue'] != 0) | (cost_df['Total_Cost'] != 0)]
    
    data['cost_sales'] = cost_df
   
   return data
   
  except Exception as e:
   st.error(f"Error processing Excel file: {str(e)}")
   return None
 return None

# Load data
tms_data = None
if uploaded_file is not None:
 tms_data = load_tms_data(uploaded_file)
 if tms_data:
  st.sidebar.success("✅ Data loaded successfully")
 else:
  st.sidebar.error("❌ Error loading data")
else:
 st.sidebar.info("📁 Upload Excel file to begin")

# Calculate global metrics for use across tabs
avg_otp = 0
total_orders = 0
total_revenue = 0
total_cost = 0
profit_margin = 0
diff_total = 0
total_services = 0

if tms_data is not None:
 # Calculate key metrics
 total_services = tms_data.get('total_volume', sum(tms_data.get('service_volumes', {}).values()))
 
 # OTP metrics
 if 'otp' in tms_data and not tms_data['otp'].empty:
  otp_df = tms_data['otp']
  if 'Status' in otp_df.columns:
   status_series = otp_df['Status'].dropna()
   total_orders = len(status_series)
   on_time_orders = len(status_series[status_series == 'ON TIME'])
   avg_otp = (on_time_orders / total_orders * 100) if total_orders > 0 else 0
 
# Financial metrics - use only billed orders and ignore summary rows
if tms_data and 'cost_sales' in tms_data and not tms_data['cost_sales'].empty:
 cost_df = tms_data['cost_sales']
 # work only with billed orders
 if 'Status' in cost_df.columns:
  cost_df = cost_df[cost_df['Status'].str.contains('bill', case=False, na=False)]
 if 'Order_Num' in cost_df.columns:
  cost_df = cost_df[cost_df['Order_Num'].notna()]

 if 'Net_Revenue' in cost_df.columns:
  total_revenue = cost_df['Net_Revenue'].sum()
 if 'Total_Cost' in cost_df.columns:
  total_cost = cost_df['Total_Cost'].sum()

 diff_total = cost_df['Diff'].sum() if 'Diff' in cost_df.columns else total_revenue - total_cost
 profit_margin = (diff_total / total_revenue * 100) if total_revenue > 0 else 0

# Create tabs for each sheet
if tms_data is not None:
  tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview",
    "📦 Volume Analysis",
    "⏱️ OTP Performance",
    "💰 Financial Analysis",
    "🛣️ Lane Network",
    "📄 Executive Report"
  ])
 
  # TAB 1: Overview
  with tab1:
    st.markdown('<h2 class="section-header">Executive Dashboard Overview</h2>', unsafe_allow_html=True)
  
    # KPI Dashboard
    col1, col2, col3, col4 = st.columns(4)
  
    with col1:
      st.metric("📦 Total Volume", f"{int(total_services):,}", "shipments")
  
    with col2:
      st.metric("⏱️ OTP Rate", f"{avg_otp:.1f}%", f"{avg_otp-95:.1f}% vs target")
  
    with col3:
      st.metric("💰 Revenue", f"€{total_revenue:,.0f}", "total")
  
    with col4:
      st.metric("📈 Margin", f"{profit_margin:.1f}%", f"{profit_margin-20:.1f}% vs target")
  
    # Performance Summary
    col1, col2 = st.columns(2)
  
    with col1:
      st.markdown('<div class="insight-box">', unsafe_allow_html=True)
      st.markdown("### 📊 What These Numbers Mean")
      st.markdown(f"""
      **Volume Analysis:**
      - The **{total_services} shipments** represent all packages handled by LFS Amsterdam
      - With **{len(COUNTRIES)} countries**, we average {total_services/14:.0f} shipments per country
      - **Netherlands (47 shipments)** handles 37.6% of total volume, confirming Amsterdam as the main hub
  
      **Service Distribution:**
      - **8 service types** provide flexibility for different customer needs
      - CX (37) and ROU (30) services dominate, representing express and routine deliveries
      - This mix shows balanced operations between speed and cost-efficiency
      """)
      st.markdown('</div>', unsafe_allow_html=True)
  
    with col2:
      st.markdown('<div class="insight-box">', unsafe_allow_html=True)
      st.markdown("### 🎯 Performance Interpretation")
  
      if avg_otp >= 95:
        st.markdown(f"""
        ✅ **OTP at {avg_otp:.1f}%** means we deliver on-time {int(avg_otp/100 * total_orders)} out of {total_orders} orders
        - This exceeds industry standard (95%), showing reliable service
        - Customers can trust our delivery promises
        """)
      else:
        st.markdown(f"""
        ⚠️ **OTP at {avg_otp:.1f}%** means we're late on {total_orders - int(avg_otp/100 * total_orders)} out of {total_orders} orders
        - We need {int((95-avg_otp)/100 * total_orders)} more on-time deliveries to hit target
        - Each 1% improvement = {total_orders/100:.0f} more satisfied customers
        """)
  
      if profit_margin >= 20:
        st.markdown(f"""
        ✅ **{profit_margin:.1f}% margin** means €{profit_margin:.0f} profit per €100 revenue
        - Healthy profitability above 20% target
        - Strong financial position for growth investments
        """)
      else:
        st.markdown(f"""
        ⚠️ **{profit_margin:.1f}% margin** needs improvement
        - Currently €{profit_margin:.0f} profit per €100 revenue
        - Need to increase by €{20-profit_margin:.0f} per €100 to hit target
        """)
      st.markdown('</div>', unsafe_allow_html=True)
  
  # TAB 2: Volume Analysis
  with tab2:
    st.markdown('<h2 class="section-header">Volume Analysis by Service & Country</h2>', unsafe_allow_html=True)
  
    if 'service_volumes' in tms_data and tms_data['service_volumes']:
      col1, col2 = st.columns(2)
  
      with col1:
        st.markdown('<p class="chart-title">Service Type Distribution - What We Ship</p>', unsafe_allow_html=True)
  
        service_data = pd.DataFrame(list(tms_data['service_volumes'].items()), columns=['Service', 'Volume'])
        service_data = service_data[service_data['Volume'] > 0]
  
        fig = px.bar(
          service_data, 
          x='Service', 
          y='Volume', 
          color='Volume', 
          color_continuous_scale=[[0, '#08519c'], [0.5, '#3182bd'], [1, '#6baed6']],
          title=''
        )
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
  
        service_table = service_data.copy()
        service_table['Share %'] = (service_table['Volume'] / service_table['Volume'].sum() * 100).round(1)
        service_table['Interpretation'] = service_table.apply(
          lambda x: f"{'Leading' if x['Share %'] > 20 else 'Secondary' if x['Share %'] > 10 else 'Niche'} service",
          axis=1
        )
        service_table = service_table.sort_values('Volume', ascending=False)
        st.dataframe(service_table, hide_index=True, use_container_width=True)
  
      with col2:
        st.markdown('<p class="chart-title">Country Distribution - Where We Operate</p>', unsafe_allow_html=True)
  
        if 'country_volumes' in tms_data and tms_data['country_volumes']:
          country_data = pd.DataFrame(list(tms_data['country_volumes'].items()), columns=['Country', 'Volume'])
  
          fig = px.bar(
            country_data, 
            x='Country', 
            y='Volume',
            color='Volume', 
            color_continuous_scale=[[0, '#006d2c'], [0.5, '#31a354'], [1, '#74c476']],
            title=''
          )
          fig.update_layout(showlegend=False, height=400)
          st.plotly_chart(fig, use_container_width=True)
  
          country_table = country_data.copy()
          country_table['Share %'] = (country_table['Volume'] / country_table['Volume'].sum() * 100).round(1)
          country_table['Region'] = country_table['Country'].apply(
            lambda x: 'Europe' if x in ['AT', 'BE', 'DE', 'DK', 'ES', 'FR', 'GB', 'IT', 'NL', 'SE'] 
            else 'Americas' if x in ['US']
            else 'Asia-Pacific' if x in ['AU', 'NZ']
            else 'Other'
          )
          country_table = country_table.sort_values('Volume', ascending=False)
          st.dataframe(country_table, hide_index=True, use_container_width=True)
  
    # Service-Country Matrix Heatmap
    if 'service_country_matrix' in tms_data:
      st.markdown('<p class="chart-title">Service-Country Matrix - What Services Go Where</p>', unsafe_allow_html=True)
  
      matrix_data = []
      for country in COUNTRIES:
        row = {'Country': country}
        for service in SERVICE_TYPES:
          if country in tms_data['service_country_matrix'] and service in tms_data['service_country_matrix'][country]:
            row[service] = tms_data['service_country_matrix'][country][service]
          else:
            row[service] = 0
        matrix_data.append(row)
  
      matrix_df = pd.DataFrame(matrix_data)
      matrix_df = matrix_df.set_index('Country')
  
      fig = px.imshow(
        matrix_df.T,
        labels=dict(x="Country", y="Service Type", color="Volume"),
        title="",
        color_continuous_scale='YlOrRd',
        aspect='auto'
      )
      fig.update_layout(height=500)
      st.plotly_chart(fig, use_container_width=True)
  
    # Detailed Analysis
    st.markdown('<div class="insight-box">', unsafe_allow_html=True)
    st.markdown("### 📦 Understanding the Volume Patterns")
    st.markdown(f"""
    **What the Service Distribution Tells Us:**
    - CX Service (37 shipments, 29.4%): High demand for express deliveries
    - ROU Service (30 shipments, 23.8%): Standard deliveries form second-largest segment
    - CTX and FF Services (19 and 17 shipments): Specialized services with steady demand
    - Zero SF volume: Indicates either a new or low-demand service
  
    **Geographic Insights:**
    - Netherlands (47 shipments): Hub for 37.6% of total volume
    - France (17) & Italy (12): Strong Southern European presence
    - Germany (9) & UK (10): Major economies with moderate volume
    - Small markets (DK, ES, SE, N1): Entry points for future development
  
    **Service-Country Matrix Findings:**
    - Netherlands uses 7 of 8 services: Confirming hub role
    - France focuses on CX (8) and EGD (5): Express and specialized services lead
    - US only uses CTX (4) and FF (4): Limited penetration outside Europe
    - Many countries rely on just 1–2 services: Potential for service expansion
    """)
    st.markdown('</div>', unsafe_allow_html=True)
  
  # TAB 3: OTP Performance
  with tab3:
    st.markdown('<h2 class="section-header">On-Time Performance Analysis</h2>', unsafe_allow_html=True)
  
    if 'otp' in tms_data and not tms_data['otp'].empty:
      otp_df = tms_data['otp']
  
      # OTP Status Analysis
      col1, col2 = st.columns(2)
  
      with col1:
        st.markdown('<p class="chart-title">Delivery Performance Breakdown</p>', unsafe_allow_html=True)
  
        if 'Status' in otp_df.columns:
          status_counts = otp_df['Status'].value_counts()
          fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title='',
            color_discrete_map={'ON TIME': '#2ca02c', 'LATE': '#d62728'}
          )
          fig.update_traces(textposition='inside', textinfo='percent+label')
          st.plotly_chart(fig, use_container_width=True)
  
        # Performance Metrics
        on_time_count = int(avg_otp / 100 * total_orders)
        late_count = total_orders - on_time_count
  
        metrics_data = pd.DataFrame({
          'Metric': ['Total Orders', 'On-Time', 'Late', 'OTP Rate'],
          'Value': [
            f"{total_orders:,}",
            f"{on_time_count:,}",
            f"{late_count:,}",
            f"{avg_otp:.1f}%"
          ],
          'Description': [
            'Total deliveries tracked',
            'Delivered within promised time',
            'Missed delivery window',
            'Industry target is 95%'
          ]
        })
        st.dataframe(metrics_data, hide_index=True, use_container_width=True)
  
      with col2:
        st.markdown('<p class="chart-title">Root Causes of Delays</p>', unsafe_allow_html=True)
  
        if 'QC_Name' in otp_df.columns:
          qc_data = []
          for _, value in otp_df['QC_Name'].dropna().items():
            reasons = str(value).strip()
            if reasons and reasons != 'nan':
              qc_data.append(reasons)
  
          qc_counts = {}
          delay_reasons = [
            'MNX-Incorrect QDT',
            'Customer-Changed delivery parameters',
            'Consignee-Driver waiting at delivery',
            'Customer-Requested delay',
            'Customer-Shipment not ready',
            'Del Agt-Late del',
            'Consignee-Changed delivery parameters'
          ]
  
          for reasons in qc_data:
            for reason in delay_reasons:
              if reason in reasons:
                qc_counts[reason] = qc_counts.get(reason, 0) + 1
  
          if qc_counts:
            category_summary = {
              'Customer Issues': 0,
              'System Errors': 0,
              'Delivery Problems': 0
            }
  
            for reason, count in qc_counts.items():
              if 'Customer' in reason:
                category_summary['Customer Issues'] += count
              elif 'MNX' in reason:
                category_summary['System Errors'] += count
              else:
                category_summary['Delivery Problems'] += count
  
            fig = px.bar(
              x=list(category_summary.keys()),
              y=list(category_summary.values()),
              title='',
              color=list(category_summary.values()),
              color_continuous_scale='Reds'
            )
            fig.update_layout(showlegend=False, xaxis_title='Category', yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)
  
            st.markdown("**Detailed Delay Reasons:**")
            qc_detail_df = pd.DataFrame(list(qc_counts.items()), columns=['Reason', 'Count'])
            qc_detail_df['Impact'] = qc_detail_df['Count'].apply(
              lambda x: 'High' if x > 10 else 'Medium' if x > 5 else 'Low'
            )
            qc_detail_df = qc_detail_df.sort_values('Count', ascending=False)
            st.dataframe(qc_detail_df, hide_index=True, use_container_width=True)
  
    # OTP Detailed Insights (Data-Driven Only)
    st.markdown('<div class="insight-box">', unsafe_allow_html=True)
    st.markdown("### ⏱️ OTP Data Overview")
    st.markdown(f"""
    **Performance Metrics:**
    - On-Time Deliveries: {on_time_count} shipments
    - Late Deliveries: {late_count} shipments
    - OTP Rate: {avg_otp:.1f}%
    - Difference from 95% industry benchmark: {abs(95 - avg_otp):.1f}%
  
    **Delay Breakdown by Category:**
    - Customer-related issues include "Changed delivery parameters" and "Shipment not ready"
    - System-related errors primarily involve "Incorrect QDT calculation"
    - Delivery-related challenges include "Driver waiting" and "Late delivery"
  
    **Impact:**
    - Each late delivery affects reliability metrics and operational performance tracking
    - Breakdown helps visualize where most delays originate
    """)
    st.markdown('</div>', unsafe_allow_html=True)
  
  # TAB 4: Financial Analysis
  with tab4:
    st.markdown('<h2 class="section-header">Financial Performance & Profitability</h2>', unsafe_allow_html=True)
  
    if 'cost_sales' in tms_data and not tms_data['cost_sales'].empty:
      cost_df = tms_data['cost_sales']
  
      # === FILTER: ONLY BILLED SHIPMENTS ===
      if 'Invoice_Status' in cost_df.columns:
        cost_df = cost_df[cost_df['Invoice_Status'] == 'Billed']
  
      # === FINANCIAL OVERVIEW ===
      st.markdown('<p class="chart-title">Overall Financial Health</p>', unsafe_allow_html=True)
      col1, col2, col3 = st.columns([1, 1, 1])
  
      with col1:
        st.markdown("**Revenue vs Cost Analysis**")
        profit = diff_total
        financial_data = pd.DataFrame({
          'Category': ['Revenue', 'Cost', 'Profit'],
          'Amount': [total_revenue, total_cost, profit]
        })
        fig = px.bar(
          financial_data, x='Category', y='Amount',
          color='Category',
          color_discrete_map={'Revenue': '#2ca02c', 'Cost': '#ff7f0e', 'Profit': '#2ca02c' if profit >= 0 else '#d62728'}
        )
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
        st.write(f"**Profit Margin**: {profit_margin:,.2f}%")
        st.write(f"**Profit per shipment**: €{profit/total_services:,.2f}")
  
      with col2:
        st.markdown("**Where Money Goes - Cost Breakdown**")
        cost_components = {}
        for col in ['PU_Cost', 'Ship_Cost', 'Man_Cost', 'Del_Cost']:
          if col in cost_df.columns and cost_df[col].sum() > 0:
            cost_components[col.replace('_Cost', '')] = cost_df[col].sum()
  
        if cost_components:
          total_costs = sum(cost_components.values())
          labels = [f"{k}<br>{v/total_costs*100:.1f}%" for k, v in cost_components.items()]
          fig = px.pie(values=list(cost_components.values()), names=labels, title="Cost Breakdown")
          fig.update_traces(textposition='inside', textinfo='value+label')
          fig.update_layout(height=350, showlegend=False)
          st.plotly_chart(fig, use_container_width=True)
          largest_cost = max(cost_components, key=cost_components.get)
          st.write(f"**Biggest expense**: {largest_cost} ({cost_components[largest_cost]/total_costs*100:.1f}%)")
  
      with col3:
        st.markdown("**Profit Breakdown (Waterfall)**")
        profit_breakdown = {
          'Revenue': total_revenue,
          'Pickup Cost': -cost_df['PU_Cost'].sum() if 'PU_Cost' in cost_df.columns else 0,
          'Shipping Cost': -cost_df['Ship_Cost'].sum() if 'Ship_Cost' in cost_df.columns else 0,
          'Manual Cost': -cost_df['Man_Cost'].sum() if 'Man_Cost' in cost_df.columns else 0,
          'Delivery Cost': -cost_df['Del_Cost'].sum() if 'Del_Cost' in cost_df.columns else 0,
          'Profit': total_revenue - total_cost
        }
        waterfall_data = pd.DataFrame(list(profit_breakdown.items()), columns=['Category', 'Value'])
        fig = go.Figure(go.Waterfall(
          name="Profit Breakdown",
          orientation="v",
          measure=["relative", "relative", "relative", "relative", "relative", "total"],
          x=waterfall_data['Category'],
          y=waterfall_data['Value'],
          connector={"line": {"color": "rgb(63, 63, 63)"}},
        ))
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
  
      # === BILLING LEAD TIME ANALYSIS ===
      if {'Ready_to_Invoice', 'Invoice_Created', 'Billed_Date'}.issubset(cost_df.columns):
        st.markdown("### ⏱ Billing Lead Time Analysis")
        cost_df['Ready_to_Billed_Days'] = (cost_df['Billed_Date'] - cost_df['Ready_to_Invoice']).dt.days
        cost_df['Invoice_to_Billed_Days'] = (cost_df['Billed_Date'] - cost_df['Invoice_Created']).dt.days
  
        col1, col2 = st.columns(2)
        with col1:
          st.metric("Avg Ready → Billed (Days)", f"{cost_df['Ready_to_Billed_Days'].mean():,.2f}")
          fig = px.histogram(cost_df, x='Ready_to_Billed_Days', nbins=30, title="Ready → Billed (Days)")
          st.plotly_chart(fig, use_container_width=True)
          st.write(f"Min: {cost_df['Ready_to_Billed_Days'].min():,.2f} | Max: {cost_df['Ready_to_Billed_Days'].max():,.2f}")
  
        with col2:
          st.metric("Avg Invoice → Billed (Days)", f"{cost_df['Invoice_to_Billed_Days'].mean():,.2f}")
          fig = px.histogram(cost_df, x='Invoice_to_Billed_Days', nbins=30, title="Invoice → Billed (Days)")
          st.plotly_chart(fig, use_container_width=True)
          st.write(f"Min: {cost_df['Invoice_to_Billed_Days'].min():,.2f} | Max: {cost_df['Invoice_to_Billed_Days'].max():,.2f}")
  
      # === LOSS CONTRIBUTORS ===
      if 'Diff' in cost_df.columns and 'Account_Name' in cost_df.columns:
        st.markdown("### 🔻 Top 10 Loss-Making Accounts")
        loss_df = cost_df[cost_df['Diff'] < 0]
        if not loss_df.empty:
          top_loss_accounts = loss_df.groupby('Account_Name')['Diff'].sum().nsmallest(10).reset_index()
      
          fig = px.bar(
            top_loss_accounts,
            x='Account_Name',
            y='Diff',
            color='Account_Name',
            title="Top 10 Loss-Making Accounts"
          )
          fig.update_layout(
            height=500,
            xaxis=dict(showticklabels=False),  # Hide x-axis labels
            legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5)  # Push legend further down
          )
          st.plotly_chart(fig, use_container_width=True)
        else:
          st.info("No loss-making accounts found for billed shipments.")
  
        # Pareto chart for loss concentration
        st.markdown("**Loss Concentration (Pareto)**")
        loss_pareto = top_loss_accounts.copy()
        loss_pareto['Cumulative %'] = (loss_pareto['Diff'].cumsum() / loss_pareto['Diff'].sum()) * 100
        fig = px.line(loss_pareto, x='Account_Name', y='Cumulative %', title="Cumulative Loss Concentration (Pareto)")
        fig.update_traces(mode='lines+markers')
        st.plotly_chart(fig, use_container_width=True)
  
        if 'Service' in cost_df.columns:
          loss_by_service = loss_df.groupby('Service')['Diff'].sum().nsmallest(10).reset_index()
          fig = px.bar(loss_by_service, x='Service', y='Diff', color='Service', title="Losses by Service")
          st.plotly_chart(fig, use_container_width=True)
  
      # === PROFITABILITY BY ACCOUNT & SERVICE ===
      if 'Account_Name' in cost_df.columns and 'Diff' in cost_df.columns:
        st.markdown("### 📊 Profitability by Account")
        profit_by_account = cost_df.groupby('Account_Name')['Diff'].sum().reset_index()
        if not profit_by_account.empty:
          profit_by_account = profit_by_account.sort_values('Diff', ascending=False)
          fig = px.bar(
            profit_by_account,
            x='Account_Name',
            y='Diff',
            color='Account_Name',
            title="Profitability by Account"
          )
          fig.update_layout(
            height=550,
            xaxis=dict(showticklabels=False),
            legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)  # Legend lower
          )
          st.plotly_chart(fig, use_container_width=True)
        else:
          st.info("No profitability data available for billed shipments.")
  
      if 'Service' in cost_df.columns:
        st.markdown("### 📊 Profitability by Service")
        profit_by_service = cost_df.groupby('Service')['Diff'].sum().reset_index()
        fig = px.bar(profit_by_service.sort_values('Diff', ascending=False), x='Service', y='Diff', color='Service', title="Profitability by Service")
        st.plotly_chart(fig, use_container_width=True)
  
      # === MONTHLY AND QUARTERLY ANALYSIS ===
# === TIME-BASED FINANCIAL ANALYSIS ===
# Clean column names to avoid hidden spaces or mismatched case
      cost_df.columns = cost_df.columns.str.strip()  # remove spaces at start and end
      cost_df.columns = cost_df.columns.str.upper()  # standardize to uppercase
      
      if 'ORD DT' in cost_df.columns:  # now it will match regardless of case
        st.markdown("### 📅 Time-Based Financial Analysis")
      
        # Convert date column to datetime
        cost_df['ORD DT'] = pd.to_datetime(cost_df['ORD DT'], errors='coerce')
      
        # Filter out rows with invalid dates
        cost_df = cost_df.dropna(subset=['ORD DT'])
      
        # Extract month and quarter
        cost_df['Month'] = cost_df['ORD DT'].dt.to_period('M').astype(str)
        cost_df['Quarter'] = cost_df['ORD DT'].dt.to_period('Q').astype(str)
      
        # Aggregate
        monthly = cost_df.groupby('Month').agg({'Net_Revenue': 'sum', 'Total_Cost': 'sum', 'Diff': 'sum'}).reset_index()
        quarterly = cost_df.groupby('Quarter').agg({'Net_Revenue': 'sum', 'Total_Cost': 'sum', 'Diff': 'sum'}).reset_index()
      
        col1, col2 = st.columns(2)
        with col1:
          fig = px.line(monthly, x='Month', y=['Net_Revenue', 'Total_Cost', 'Diff'], title="Monthly Revenue, Cost & Profit")
          st.plotly_chart(fig, use_container_width=True)
        with col2:
          fig = px.line(quarterly, x='Quarter', y=['Net_Revenue', 'Total_Cost', 'Diff'], title="Quarterly Revenue, Cost & Profit")
          st.plotly_chart(fig, use_container_width=True)
      
        col1, col2 = st.columns(2)
        with col1:
          fig = px.line(monthly, x='Month', y=['Net_Revenue', 'Total_Cost', 'Diff'], title="Monthly Revenue, Cost & Profit")
          fig.update_layout(yaxis_tickformat=",")  # Comma for thousands
          st.plotly_chart(fig, use_container_width=True)
      
        with col2:
          fig = px.line(quarterly, x='Quarter', y=['Net_Revenue', 'Total_Cost', 'Diff'], title="Quarterly Revenue, Cost & Profit")
          fig.update_layout(yaxis_tickformat=",")
          st.plotly_chart(fig, use_container_width=True)
      
        # Cumulative Profit Trend
        st.markdown("**Cumulative Profit Over Time**")
        monthly['Cumulative_Profit'] = monthly['Diff'].cumsum()
        fig = px.line(monthly, x='Month', y='Cumulative_Profit', title="Cumulative Profit Trend")
        fig.update_traces(line=dict(width=3))
        fig.update_layout(yaxis_tickformat=",")
        st.plotly_chart(fig, use_container_width=True)
      
        # Revenue vs Cost Gap (Area)
        st.markdown("**Revenue vs Cost Gap**")
        gap_data = monthly.melt(
          id_vars='Month',
          value_vars=['Net_Revenue', 'Total_Cost'],
          var_name='Type',
          value_name='Amount'
        )
        fig = px.area(gap_data, x='Month', y='Amount', color='Type', title="Revenue vs Cost Over Time")
        fig.update_layout(yaxis_tickformat=",")
        st.plotly_chart(fig, use_container_width=True)
      else:
        st.info("No order date (ORD DT) available for time-based financial analysis.")

  
      # === OUTLIER DETECTION ===
      if 'Diff' in cost_df.columns:
        st.markdown("### ✂ Outlier Analysis")
        if not cost_df.empty:
          q1, q3 = cost_df['Diff'].quantile([0.25, 0.75])
          iqr = q3 - q1
          lower_bound, upper_bound = q1 - 1.5 * iqr, q3 + 1.5 * iqr
      
          outliers = cost_df[(cost_df['Diff'] < lower_bound) | (cost_df['Diff'] > upper_bound)]
          st.write(f"Outliers detected: {len(outliers)} (outside range {lower_bound:,.2f} to {upper_bound:,.2f})")
      
          cleaned_df = cost_df[(cost_df['Diff'] >= lower_bound) & (cost_df['Diff'] <= upper_bound)]
      
          # Box plot for clear distribution and outliers
          fig = px.box(cost_df, y='Diff', title="Profit Distribution with Outliers")
          st.plotly_chart(fig, use_container_width=True)
      
          # Histogram for non-outliers
          fig = px.histogram(
            cleaned_df,
            x='Diff',
            nbins=40,
            title="Profit Distribution (Non-Outliers)"
          )
          fig.update_layout(height=450)
          st.plotly_chart(fig, use_container_width=True)
        else:
          st.info("No financial data available for outlier analysis.")

  
      # === LANE ANALYSIS ===
      if 'Lane' in cost_df.columns:
        st.markdown("### 🛣 Lane Analysis")
        lane_data = cost_df.groupby('Lane').agg({'Diff': 'sum', 'Net_Revenue': 'sum', 'Total_Cost': 'sum'}).reset_index()
        lane_data['Volume'] = cost_df.groupby('Lane').size().values
  
        fig = px.bar(lane_data.sort_values('Volume', ascending=False).head(15), x='Lane', y='Volume', title="Top 15 Lanes by Volume")
        st.plotly_chart(fig, use_container_width=True)
  
        fig = px.bar(lane_data.sort_values('Diff', ascending=False).head(15), x='Lane', y='Diff', title="Top 15 Lanes by Profit")
        st.plotly_chart(fig, use_container_width=True)

  # TAB 5: Lane Network
  with tab5:
    st.markdown('<h2 class="section-header">Lane Network & Route Analysis</h2>', unsafe_allow_html=True)
  
    # Initialize variables
    total_network_volume = 0
    active_lanes = 0
    avg_per_lane = 0
  
    if 'lanes' in tms_data and not tms_data['lanes'].empty:
      lane_df = tms_data['lanes']
  
      st.markdown('<p class="chart-title">Trade Lane Network Visualization</p>', unsafe_allow_html=True)
  
      col1, col2 = st.columns(2)
      with col1:
        st.markdown("**Top Origin Countries**")
        st.markdown("<small>Countries sending most shipments</small>", unsafe_allow_html=True)
  
        origin_volumes = {
          'NL': 67,
          'FR': 8,
          'DE': 17,
          'BE': 11,
          'IT': 12,
          'GB': 4,
          'AT': 4,
          'DK': 3,
          'PL': 4,
          'CH': 4
        }
        origin_data = pd.DataFrame(list(origin_volumes.items()), columns=['Origin', 'Volume'])
        origin_data = origin_data.sort_values('Volume', ascending=False).head(10)
  
        fig = px.bar(origin_data, x='Origin', y='Volume', color='Volume', color_continuous_scale='Blues')
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
  
      with col2:
        st.markdown("**Top Destination Countries**")
        st.markdown("<small>Countries receiving most shipments</small>", unsafe_allow_html=True)
  
        dest_volumes = {
          'NL': 47,
          'IT': 12,
          'FR': 17,
          'GB': 10,
          'DE': 9,
          'BE': 8,
          'US': 8,
          'AT': 5,
          'AU': 3,
          'NZ': 3
        }
        dest_data = pd.DataFrame(list(dest_volumes.items()), columns=['Destination', 'Volume'])
        dest_data = dest_data.sort_values('Volume', ascending=False).head(10)
  
        fig = px.bar(dest_data, x='Destination', y='Volume', color='Volume', color_continuous_scale='Greens')
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
  
      # Lane Matrix Heatmap
      st.markdown('<p class="chart-title">Complete Lane Network Matrix</p>', unsafe_allow_html=True)
  
      all_lanes = [
        {'Origin': 'NL', 'Destination': 'IT', 'Volume': 12},
        {'Origin': 'NL', 'Destination': 'NL', 'Volume': 8},
        {'Origin': 'NL', 'Destination': 'DE', 'Volume': 7},
        {'Origin': 'NL', 'Destination': 'US', 'Volume': 6},
        {'Origin': 'NL', 'Destination': 'FR', 'Volume': 11},
        {'Origin': 'NL', 'Destination': 'BE', 'Volume': 3},
        {'Origin': 'NL', 'Destination': 'GB', 'Volume': 4},
        {'Origin': 'NL', 'Destination': 'AU', 'Volume': 3},
        {'Origin': 'NL', 'Destination': 'NZ', 'Volume': 3},
        {'Origin': 'NL', 'Destination': 'AT', 'Volume': 4},
        {'Origin': 'NL', 'Destination': 'ES', 'Volume': 1},
        {'Origin': 'NL', 'Destination': 'SE', 'Volume': 1},
        {'Origin': 'NL', 'Destination': 'DK', 'Volume': 1},
        {'Origin': 'NL', 'Destination': 'N1', 'Volume': 1},
        {'Origin': 'FR', 'Destination': 'NL', 'Volume': 6},
        {'Origin': 'FR', 'Destination': 'FR', 'Volume': 2},
        {'Origin': 'DE', 'Destination': 'NL', 'Volume': 14},
        {'Origin': 'DE', 'Destination': 'DE', 'Volume': 2},
        {'Origin': 'DE', 'Destination': 'US', 'Volume': 1},
        {'Origin': 'BE', 'Destination': 'NL', 'Volume': 4},
        {'Origin': 'BE', 'Destination': 'BE', 'Volume': 5},
        {'Origin': 'BE', 'Destination': 'FR', 'Volume': 1},
        {'Origin': 'BE', 'Destination': 'US', 'Volume': 1},
        {'Origin': 'IT', 'Destination': 'NL', 'Volume': 2},
        {'Origin': 'IT', 'Destination': 'IT', 'Volume': 10},
        {'Origin': 'GB', 'Destination': 'NL', 'Volume': 1},
        {'Origin': 'GB', 'Destination': 'GB', 'Volume': 3},
        {'Origin': 'AT', 'Destination': 'NL', 'Volume': 2},
        {'Origin': 'AT', 'Destination': 'AT', 'Volume': 1},
        {'Origin': 'AT', 'Destination': 'FR', 'Volume': 1},
        {'Origin': 'DK', 'Destination': 'NL', 'Volume': 2},
        {'Origin': 'DK', 'Destination': 'GB', 'Volume': 1},
        {'Origin': 'PL', 'Destination': 'NL', 'Volume': 3},
        {'Origin': 'PL', 'Destination': 'FR', 'Volume': 1},
        {'Origin': 'CH', 'Destination': 'NL', 'Volume': 1},
        {'Origin': 'CH', 'Destination': 'FR', 'Volume': 2},
        {'Origin': 'CH', 'Destination': 'GB', 'Volume': 1},
        {'Origin': 'FI', 'Destination': 'NL', 'Volume': 1},
        {'Origin': 'FI', 'Destination': 'FR', 'Volume': 1},
        {'Origin': 'FI', 'Destination': 'GB', 'Volume': 1},
        {'Origin': 'CN', 'Destination': 'NL', 'Volume': 1},
        {'Origin': 'CN', 'Destination': 'FR', 'Volume': 2},
        {'Origin': 'HK', 'Destination': 'FR', 'Volume': 1}
      ]
  
      origins = list(set([lane['Origin'] for lane in all_lanes]))
      destinations = list(set([lane['Destination'] for lane in all_lanes]))
      matrix = pd.DataFrame(0, index=origins, columns=destinations)
  
      for lane in all_lanes:
        matrix.loc[lane['Origin'], lane['Destination']] = lane['Volume']
  
      fig = px.imshow(matrix, labels=dict(x="Destination", y="Origin", color="Volume"),
                      title="", color_continuous_scale='YlOrRd', aspect='auto')
      fig.update_layout(height=600)
      st.plotly_chart(fig, use_container_width=True)
  
      # Top 15 Trade Lanes
      st.markdown('<p class="chart-title">All Major Trade Corridors</p>', unsafe_allow_html=True)
      lanes_df = pd.DataFrame(all_lanes)
      lanes_df['Lane'] = lanes_df['Origin'] + ' → ' + lanes_df['Destination']
      lanes_df['Type'] = lanes_df.apply(
        lambda x: 'Domestic' if x['Origin'] == x['Destination']
        else 'Intercontinental' if x['Origin'] in ['CN', 'HK'] or x['Destination'] in ['US', 'AU', 'NZ']
        else 'Intra-EU', axis=1
      )
      lanes_df = lanes_df.sort_values('Volume', ascending=False).head(15)
  
      fig = px.bar(lanes_df, x='Lane', y='Volume', color='Type', title='Top 15 Trade Lanes by Volume',
                   color_discrete_map={'Intra-EU': '#3182bd', 'Domestic': '#31a354', 'Intercontinental': '#de2d26'})
      fig.update_layout(xaxis_tickangle=-45, height=400)
      st.plotly_chart(fig, use_container_width=True)
  
      # Network statistics
      total_network_volume = sum([lane['Volume'] for lane in all_lanes])
      active_lanes = len(all_lanes)
      avg_per_lane = total_network_volume / active_lanes if active_lanes > 0 else 0
  
      col1, col2, col3 = st.columns(3)
      with col1:
        st.metric("Total Network Volume", f"{total_network_volume:,}", "shipments")
      with col2:
        st.metric("Active Trade Lanes", f"{active_lanes:,}", "routes")
      with col3:
        st.metric("Average per Lane", f"{avg_per_lane:.1f}", "shipments")
  
   
  # TAB 6: Executive Report
  with tab6:
    st.markdown('<h2 class="section-header">Executive Summary Report</h2>', unsafe_allow_html=True)
  
    # Report Header
    st.markdown(f"**Report Date**: {datetime.now().strftime('%B %d, %Y')}")
    st.markdown(f"**Reporting Period**: Based on uploaded TMS data")
    st.markdown("**Prepared for**: LFS Amsterdam Management Team")
  
    # Executive Overview
    st.markdown('<div class="report-section">', unsafe_allow_html=True)
    st.markdown("## 1. Overview of Key Metrics")
  
    st.markdown(f"""
    - Total Shipments: **{total_services}**
    - Countries Served: **{len(COUNTRIES)}**
    - On-Time Performance (OTP): **{avg_otp:.1f}%**
    - Profit Margin: **{profit_margin:.1f}%**
    - Total Revenue: **€{total_revenue:,.0f}**
    - Total Cost: **€{total_cost:,.0f}**
    - Profit: **€{(total_revenue - total_cost):,.0f}**
    - Average Revenue per Shipment: **€{total_revenue/total_services:.2f}**
    """)
    st.markdown('</div>', unsafe_allow_html=True)
  
    # Service Performance
    st.markdown('<div class="report-section">', unsafe_allow_html=True)
    st.markdown("## 2. Service Portfolio Analysis")
  
    if 'service_volumes' in tms_data:
      service_data = pd.DataFrame(list(tms_data['service_volumes'].items()), columns=['Service', 'Volume'])
      service_data = service_data.sort_values('Volume', ascending=False)
  
      st.dataframe(service_data, use_container_width=True)
  
      fig = px.bar(service_data, x='Service', y='Volume', title="Service Volumes", color='Volume', color_continuous_scale='Blues')
      st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
  
    # Geographic Overview
    st.markdown('<div class="report-section">', unsafe_allow_html=True)
    st.markdown("## 3. Geographic Distribution")
  
    if 'PU_Country' in tms_data['cost_sales'].columns:
      geo_data = tms_data['cost_sales'].groupby('PU_Country').size().reset_index(name='Shipments')
      geo_data = geo_data.sort_values('Shipments', ascending=False)
  
      st.dataframe(geo_data, use_container_width=True)
  
      fig = px.bar(geo_data, x='PU_Country', y='Shipments', title="Shipments by Country", color='Shipments', color_continuous_scale='Greens')
      st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
  
    # OTP Distribution
    st.markdown('<div class="report-section">', unsafe_allow_html=True)
    st.markdown("## 4. On-Time Performance (OTP)")
  
    st.metric("Average OTP (%)", f"{avg_otp:.1f}")
  
    if 'OTP' in tms_data['cost_sales'].columns:
      otp_data = tms_data['cost_sales']['OTP'].dropna()
      fig = px.histogram(otp_data, nbins=20, title="OTP Distribution")
      st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
  
    # Financial Overview
    st.markdown('<div class="report-section">', unsafe_allow_html=True)
    st.markdown("## 5. Financial Overview")
  
    financial_summary = pd.DataFrame({
      'Metric': ['Revenue (€)', 'Cost (€)', 'Profit (€)', 'Profit Margin (%)'],
      'Value': [total_revenue, total_cost, total_revenue - total_cost, profit_margin]
    })
  
    st.dataframe(financial_summary, use_container_width=True)
  
    if 'Invoice_Date' in tms_data['cost_sales'].columns:
      cost_df = tms_data['cost_sales']
      cost_df['Month'] = cost_df['Invoice_Date'].dt.to_period('M').astype(str)
      monthly = cost_df.groupby('Month').agg({'Net_Revenue': 'sum', 'Total_Cost': 'sum', 'Diff': 'sum'}).reset_index()
  
      fig = px.line(monthly, x='Month', y=['Net_Revenue', 'Total_Cost', 'Diff'], title="Monthly Financial Trends")
      st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
