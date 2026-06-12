import streamlit as st
import pandas as pd
import plotly.express as px
from charset_normalizer import from_bytes
import io

st.set_page_config(page_title="Wind Data Analyzer", layout="wide")

st.title("📊 Wind Speed Data Analyzer")
st.write("Upload your semicolon-separated CSV file to downsample, filter, and visualize.")

uploaded_file = st.file_uploader("Choose a CSV file", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        with st.spinner("Decoding and processing CSV file..."):
            # 1. Read raw bytes and automatically detect encoding (Windows vs Mac vs Linux)
            raw_data = uploaded_file.read()
            detected = from_bytes(raw_data).best()
            
            if detected is None:
                st.error("Could not automatically detect file encoding. Please check the file.")
                st.stop()
                
            # Decode bytes to string
            text_content = str(detected)
            
            # 2. Process line by line to clean up any weird spaces/empty lines
            clean_lines = []
            for line in text_content.splitlines():
                stripped = line.strip()
                if stripped:  # Skip empty lines
                    clean_lines.append(stripped)
            
            if not clean_lines:
                st.error("The uploaded file appears to be empty.")
                st.stop()
                
            # 3. Convert clean lines back into a file-like object for Pandas
            clean_csv_io = io.StringIO("\n".join(clean_lines))
            
            # Read CSV enforcing Semicolon separator and string/object types initially
            df = pd.read_csv(clean_csv_io, sep=';', header=None, on_bad_lines='skip')
            
            if df.empty:
                st.error("No valid data could be parsed from the file.")
                st.stop()
                
            total_cols = len(df.columns)
            
            # 4. Troubleshooting: If it still finds 1 column, show exactly what it looks like
            if total_cols < 2:
                st.error(f"The system still detected only 1 column. Separator check failed.")
                st.write("Here is exactly how the first 5 lines of your file look to the server:")
                st.code("\n".join(clean_lines[:5]))
                st.stop()
                
            if total_cols < 6:
                st.warning(f"Expected at least 6 columns, but found {total_cols}. Plotting available speed columns.")
            
            # 5. Map columns safely by position index
            dt_col = df.columns[0]
            
            # Take from 3rd column (index 2) up to 6th column (index 6) depending on what exists
            max_val_idx = min(6, total_cols)
            value_cols = list(df.columns[2:max_val_idx])
            
            if not value_cols:
                st.error("Not enough columns found to extract wind speed data (columns 3-6 missing).")
                st.stop()
            
            # Convert first column to datetime (coerce errors to NaT)
            df[dt_col] = pd.to_datetime(df[dt_col], errors='coerce')
            df = df.dropna(subset=[dt_col])
            df = df.sort_values(by=dt_col)
            
            # Set datetime as index for resampling
            df.set_index(dt_col, inplace=True)
            
            # Force speed columns to be numeric
            for col in value_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            # Downsample to 1-minute intervals (takes the first reading of each minute)
            df_resampled = df.resample('1T').first().dropna(how='all').reset_index()
            
            # Dynamically rename columns for the legend
            rename_dict = {value_cols[i]: f"Wind Speed Profile {i+1}" for i in range(len(value_cols))}
            df_resampled = df_resampled.rename(columns=rename_dict)
            new_value_cols = list(rename_dict.values())
            
            st.success("CSV file successfully decoded, parsed, and downsampled to 1-minute intervals!")
            
            # 6. Filter Range Slider
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
                
                # Reshape for multi-line Plotly express chart
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
        st.error(f"An error occurred: {e}")
else:
    st.info("Awaiting CSV file upload...")
