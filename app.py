import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Wind Data Analyzer", layout="wide")

st.title("📊 Wind Speed Data Analyzer")
st.write("Upload your wind data file to downsample, filter, and visualize the readings.")

# File uploader (accepts .csv, .xlsx, .xls)
uploaded_file = st.file_uploader("Choose a file (CSV or Excel format)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        file_name = uploaded_file.name.lower()
        
        with st.spinner("Reading and processing data..."):
            # Try reading as CSV first (handles CSVs disguised with .xlsx/.xls extensions)
            if file_name.endswith(('.xlsx', '.xls')):
                try:
                    # Explicitly try semicolon first, as seen in your data log
                    df = pd.read_csv(uploaded_file, sep=';', engine='python')
                    # If it failed to split (only 1 column found), try with comma
                    if len(df.columns) < 2:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, sep=',', engine='python')
                except Exception:
                    # Fallback to standard Excel reader if it is a native Excel file
                    df = pd.read_excel(uploaded_file)
            else:
                # Standard CSV handling with fallback
                df = pd.read_csv(uploaded_file, sep=';', engine='python')
                if len(df.columns) < 2:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',', engine='python')
            
            if df.empty:
                st.error("The uploaded file is empty.")
                st.stop()
                
            if len(df.columns) < 6:
                st.error(f"The file must have at least 6 columns. Found only {len(df.columns)}. "
                         f"Please check if the separator in your file is a semicolon (;) or comma (,).")
                st.stop()
            
            # Map columns by their position index:
            # 1st column [0] -> DateTime
            # 2nd column [1] -> Wind direction (skipped)
            # 3rd to 6th columns [2:6] -> Wind speed parameters (e.g., gust, mean)
            dt_col = df.columns[0]
            value_cols = list(df.columns[2:6])
            
            # Keep only the required columns to preserve memory
            df = df[[dt_col] + value_cols].copy()
            
            # Convert first column to datetime (handling mixed formats and trailing milliseconds)
            df[dt_col] = pd.to_datetime(df[dt_col], errors='coerce')
            
            # Drop rows where datetime parsing failed
            df = df.dropna(subset=[dt_col])
            df = df.sort_values(by=dt_col)
            
            # Downsample from seconds to 1-minute intervals (takes the 1st record of each minute)
            df.set_index(dt_col, inplace=True)
            df_resampled = df.resample('1T').first().dropna(how='all').reset_index()
            
            st.success("File processed and downsampled to 1-minute intervals successfully!")
            
            # Time Range Filtering Slider
            min_date = df_resampled[dt_col].min()
            max_date = df_resampled[dt_col].max()
            
            st.subheader("Filter Time Range")
            selected_range = st.slider(
                "Select date and time range:",
                min_value=min_date.to_pydatetime(),
                max_value=max_date.to_pydatetime(),
                value=(min_date.to_pydatetime(), max_date.to_pydatetime()),
                format="YYYY-MM-DD HH:mm"
            )
            
            # Filter the dataframe based on slider selection
            filtered_df = df_resampled[
                (df_resampled[dt_col] >= selected_range[0]) & 
                (df_resampled[dt_col] <= selected_range[1])
            ]
            
            if not filtered_df.empty:
                st.subheader("Wind Speed Chart")
                
                # Reshape data to long format for Plotly Express (plots multiple lines natively)
                df_melted = filtered_df.melt(
                    id_vars=[dt_col], 
                    value_vars=value_cols, 
                    var_name="Measurement Type", 
                    value_name="Wind Speed"
                )
                
                # Generate line chart
                fig = px.line(
                    df_melted,
                    x=dt_col,
                    y="Wind Speed",
                    color="Measurement Type",
                    title=f"Wind Speed Profiles ({selected_range[0].strftime('%Y-%m-%d %H:%M')} to {selected_range[1].strftime('%Y-%m-%d %H:%M')})",
                    labels={dt_col: "Date & Time", "Wind Speed": "Speed"}
                )
                
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
                
                # Optional: view the table data
                with st.expander("View downsampled data table"):
                    st.dataframe(filtered_df)
            else:
                st.warning("No data available for the selected time range.")
                
    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
else:
    st.info("Awaiting wind data file upload...")
