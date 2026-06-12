import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Wind Data Analyzer", layout="wide")

st.title("📊 Wind Speed Data Analyzer")
st.write("Upload your wind data file to downsample, filter, and visualize the readings.")

uploaded_file = st.file_uploader("Choose a file (CSV or Excel format)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        file_name = uploaded_file.name.lower()
        
        with st.spinner("Reading and processing data..."):
            if file_name.endswith(('.xlsx', '.xls')):
                try:
                    df = pd.read_excel(uploaded_file, header=None)
                except Exception:
                    uploaded_file.seek(0)
                    # Read without assuming the first line is a valid header
                    df = pd.read_csv(uploaded_file, sep=';', header=None, on_bad_lines='skip')
            else:
                # Read CSV without assuming the first line is a header
                df = pd.read_csv(uploaded_file, sep=';', header=None, on_bad_lines='skip')
            
            if df.empty:
                st.error("The uploaded file is empty.")
                st.stop()
            
            # Clean up: if there are metadata rows at the top, they will have NaN in other columns.
            # We drop rows that don't have at least 5 columns filled.
            df = df.dropna(thresh=5)
            
            if len(df.columns) < 6:
                st.error(f"The file format is incorrect. Found only {len(df.columns)} columns. "
                         f"Please ensure the file contains data separated by semicolons (;).")
                # Let's show the user what was actually read to help diagnose
                st.write("Preview of the raw data grabbed from file:")
                st.dataframe(df.head(10))
                st.stop()
            
            # Map columns by index safely now
            # Column 0: DateTime, Columns 2,3,4,5: Wind speeds
            dt_col = df.columns[0]
            value_cols = list(df.columns[2:6])
            
            # Rename columns for internal clarity
            df[dt_col] = pd.to_datetime(df[dt_col], errors='coerce')
            
            # Drop rows where datetime couldn't be parsed
            df = df.dropna(subset=[dt_col])
            df = df.sort_values(by=dt_col)
            
            # Downsample to 1-minute intervals
            df.set_index(dt_col, inplace=True)
            
            # Convert wind columns to numeric, replacing text errors with NaN
            for col in value_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            df_resampled = df.resample('1T').first().dropna(how='all').reset_index()
            
            # Rename columns for the chart legend dynamically
            rename_dict = {value_cols[i]: f"Sensor reading {i+1}" for i in range(len(value_cols))}
            df_resampled = df_resampled.rename(columns=rename_dict)
            new_value_cols = list(rename_dict.values())
            
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
            
            filtered_df = df_resampled[
                (df_resampled[dt_col] >= selected_range[0]) & 
                (df_resampled[dt_col] <= selected_range[1])
            ]
            
            if not filtered_df.empty:
                st.subheader("Wind Speed Chart")
                
                df_melted = filtered_df.melt(
                    id_vars=[dt_col], 
                    value_vars=new_value_cols, 
                    var_name="Measurement Type", 
                    value_name="Wind Speed"
                )
                
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
                
                with st.expander("View downsampled data table"):
                    st.dataframe(filtered_df)
            else:
                st.warning("No data available for the selected time range.")
                
    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")
else:
    st.info("Awaiting wind data file upload...")
