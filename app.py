import streamlit as st
import pandas as pd
import plotly.express as px
from charset_normalizer import from_bytes
import io

st.set_page_config(page_title="Wind Data Analyzer", layout="wide")

st.title("Wind Speed Data Analyzer")
st.write("Upload your wind data file to filter and visualize.")

uploaded_file = st.file_uploader("Choose a CSV file", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        with st.spinner("Cleaning quotes and processing data..."):
            # 1. Read raw bytes and detect encoding
            raw_data = uploaded_file.read()
            detected = from_bytes(raw_data).best()
            
            if detected is None:
                st.error("Could not automatically detect file encoding.")
                st.stop()
                
            text_content = str(detected)
            
            # 2. STRIP WRAPPING QUOTES from each line
            clean_lines = []
            for line in text_content.splitlines():
                stripped = line.strip()
                if stripped:
                    if stripped.startswith('"') and stripped.endswith('"'):
                        stripped = stripped[1:-1]
                    clean_lines.append(stripped)
            
            if not clean_lines:
                st.error("The uploaded file appears to be empty.")
                st.stop()
                
            # 3. Pass clean lines to Pandas
            clean_csv_io = io.StringIO("\n".join(clean_lines))
            df = pd.read_csv(clean_csv_io, sep=';')
            
            if df.empty:
                st.error("No valid data could be parsed from the file.")
                st.stop()
                
            total_cols = len(df.columns)
            
            if total_cols < 6:
                st.error(f"The file must have at least 6 columns. Found only {total_cols}.")
                st.write("Current columns detected:", list(df.columns))
                st.stop()
            
            # 4. Map columns by position
            dt_col = df.columns[0]
            value_cols = list(df.columns[2:6])
            
            # Clean up column names for the legend
            rename_dict = {}
            for col in value_cols:
                short_name = col.replace("Environmental Conditions Wind Speed ", "")
                rename_dict[col] = short_name
            
            df = df.rename(columns=rename_dict)
            new_value_cols = list(rename_dict.values())
            
            # Convert first column to datetime
            df[dt_col] = pd.to_datetime(df[dt_col], errors='coerce')
            df = df.dropna(subset=[dt_col])
            df = df.sort_values(by=dt_col)
            
            # Set index and downsample to 1-minute intervals USING '1min'
            df.set_index(dt_col, inplace=True)
            for col in new_value_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            # TUTAJ NASTĄPIŁA POPRAWKA: '1min' zamiast '1T'
            df_resampled = df.resample('1min').first().dropna(how='all').reset_index()
            
            st.success("CSV file successfully cleaned from wrapping quotes and downsampled!")
            
            # 5. Time Range Filtering Slider
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
                
                # Reshape for multi-line Plotly chart
                df_melted = filtered_df.melt(
                    id_vars=[dt_col], 
                    value_vars=new_value_cols, 
                    var_name="Measurement Type", 
                    value_name="Wind Speed [m/s]"
                )
                
                fig = px.line(
                    df_melted,
                    x=dt_col,
                    y="Wind Speed [m/s]",
                    color="Measurement Type",
                    title=f"Wind Speed Profiles ({selected_range[0].strftime('%Y-%m-%d %H:%M')} to {selected_range[1].strftime('%Y-%m-%d %H:%M')})",
                    labels={dt_col: "Date & Time"}
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
