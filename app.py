import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from charset_normalizer import from_bytes
import io

st.set_page_config(page_title="Wind Data Analyzer", layout="wide")

st.title("Wind Data Analyzer")
st.write("Upload your data file.")

# Enhanced function to generate Excel with TWO embedded charts
def to_excel_with_two_charts(data_frame, date_col_name, speed_cols, direction_col):
    output = io.BytesIO()
    # Use xlsxwriter as the engine
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # 1. Write the data to a 'Data' sheet
        data_frame.to_excel(writer, sheet_name='Data', index=False)
        
        # Get xlsxwriter objects to customize
        workbook  = writer.book
        worksheet_data = writer.sheets['Data']
        
        # Create a separate sheet for the Charts
        worksheet_chart = workbook.add_worksheet('Charts')
        
        # Determine column indexes (Date=0, Dir=1, Speeds=2,3,4,5)
        num_rows = len(data_frame)
        
        # --- CHART 1: Wind Speed Profiles ---
        chart_speed = workbook.add_chart({'type': 'line'})
        for i, col in enumerate(speed_cols):
            # Speed columns start at index 2
            chart_speed.add_series({
                'name':       ['Data', 0, i + 2],
                'categories': ['Data', 1, 0, num_rows, 0],
                'values':     ['Data', 1, i + 2, num_rows, i + 2],
            })
        chart_speed.set_title({'name': 'Wind Speed Profiles'})
        chart_speed.set_x_axis({'name': 'Date & Time', 'num_format': 'yyyy-mm-dd hh:mm'})
        chart_speed.set_y_axis({'name': 'Speed [m/s]'})
        chart_speed.set_size({'width': 960, 'height': 480})
        
        # Insert first chart
        worksheet_chart.insert_chart('B2', chart_speed)
        
        # --- CHART 2: Wind Direction ---
        chart_dir = workbook.add_chart({'type': 'line'})
        # Direction column is index 1
        chart_dir.add_series({
            'name':       ['Data', 0, 1],
            'categories': ['Data', 1, 0, num_rows, 0],
            'values':     ['Data', 1, 1, num_rows, 1],
        })
        chart_dir.set_title({'name': 'Wind Direction Profile'})
        chart_dir.set_x_axis({'name': 'Date & Time', 'num_format': 'yyyy-mm-dd hh:mm'})
        chart_dir.set_y_axis({'name': 'Direction [deg]', 'min': 0, 'max': 360})
        chart_dir.set_size({'width': 960, 'height': 480})
        
        # Insert second chart below the first one
        worksheet_chart.insert_chart('B30', chart_dir)
        
    return output.getvalue()

uploaded_file = st.file_uploader("Choose a CSV file", type=["csv", "txt"])

if uploaded_file is not None:
    try:
        with st.spinner("Decoding and processing data..."):
            raw_data = uploaded_file.read()
            detected = from_bytes(raw_data).best()
            
            if detected is None:
                st.error("Could not automatically detect file encoding.")
                st.stop()
                
            text_content = str(detected)
            
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
                
            clean_csv_io = io.StringIO("\n".join(clean_lines))
            df = pd.read_csv(clean_csv_io, sep=';')
            
            if df.empty:
                st.error("No valid data could be parsed from the file.")
                st.stop()
                
            total_cols = len(df.columns)
            if total_cols < 6:
                st.error(f"The file must have at least 6 columns. Found only {total_cols}.")
                st.stop()
            
            # --- Map Columns ---
            dt_col = df.columns[0]
            # Column 2 -> Wind Direction (keep this now!)
            raw_dir_col = df.columns[1]
            # Columns 3, 4, 5, 6 -> Wind speeds
            value_cols = list(df.columns[2:6])
            
            # Rename columns dynamically for legend
            new_dir_col_name = "Direction [deg]"
            rename_dict = {raw_dir_col: new_dir_col_name}
            for col in value_cols:
                short_name = col.replace("Environmental Conditions Wind Speed ", "")
                rename_dict[col] = short_name
            
            df = df.rename(columns=rename_dict)
            new_speed_cols = list(rename_dict.values())
            # Removing Direction from speed columns list
            new_speed_cols.remove(new_dir_col_name)
            
            # Convert first column to datetime
            df[dt_col] = pd.to_datetime(df[dt_col], errors='coerce')
            df = df.dropna(subset=[dt_col])
            df = df.sort_values(by=dt_col)
            
            # Set index for resampling
            df.set_index(dt_col, inplace=True)
            
            # Coerce direction and speed columns to numeric
            df[new_dir_col_name] = pd.to_numeric(df[new_dir_col_name], errors='coerce')
            for col in new_speed_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            # Downsample to 1-minute intervals USING '1min'
            # (Takes the first second of each minute for both Speed and Direction)
            df_resampled = df.resample('1min').first().dropna(how='all').reset_index()
            
            st.success("CSV file successfully cleaned from wrapping quotes and downsampled!")
            
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
                # --- INTERACTIVE WEB CHARTS SECTION ---
                
                # 1. Main Speed Chart (unchanged)
                st.subheader("Chart 1: Wind Speed Profiles")
                df_melted_speed = filtered_df.melt(
                    id_vars=[dt_col], 
                    value_vars=new_speed_cols, 
                    var_name="Measurement Type", 
                    value_name="Speed [m/s]"
                )
                
                fig_speed = px.line(
                    df_melted_speed,
                    x=dt_col,
                    y="Speed [m/s]",
                    color="Measurement Type",
                    labels={dt_col: "Date & Time"}
                )
                fig_speed.update_layout(hovermode="x unified")
                st.plotly_chart(fig_speed, use_container_width=True)
                
                # 2. SEPARATE Wind Direction Chart
                st.subheader(f"Chart 2: {new_dir_col_name} Profile")
                
                fig_dir = px.line(
                    filtered_df,
                    x=dt_col,
                    y=new_dir_col_name,
                    title=f"Wind Direction Profile ({selected_range[0].strftime('%Y-%m-%d %H:%M')} to {selected_range[1].strftime('%Y-%m-%d %H:%M')})",
                    labels={dt_col: "Date & Time"}
                )
                # Fix the Y axis to always show 0-360 degrees
                fig_dir.update_layout(yaxis_range=[0,360], hovermode="x unified")
                # Make the line style clearer for degrees
                fig_dir.update_traces(line=dict(color='darkred', width=2))
                st.plotly_chart(fig_dir, use_container_width=True)
                
                # --- EXCEL DOWNLOAD BUTTON SECTION ---
                st.subheader("Export Options")
                
                # Format datetime column for clear look in Excel
                excel_df = filtered_df.copy()
                excel_df[dt_col] = excel_df[dt_col].dt.strftime('%Y-%m-%d %H:%M')
                
                excel_data = to_excel_with_two_charts(excel_df, dt_col, new_speed_cols, new_dir_col_name)
                
                st.download_button(
                    label="📥 Download filtered data in Excel",
                    data=excel_data,
                    file_name=f"wind_direction_{selected_range[0].strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                # --------------------------------------
                
                with st.expander("View downsampled data table"):
                    st.dataframe(filtered_df)
            else:
                st.warning("No data available for the selected time range.")
                
    except Exception as e:
        st.error(f"An error occurred: {e}")
else:
    st.info("Awaiting wind data CSV file upload...")
