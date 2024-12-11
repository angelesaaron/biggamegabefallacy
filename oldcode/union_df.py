def union_all_dataframes_in_folder():
    # Get a list of all CSV files in the folder
    folder_path = 'data/playerData/2024_week14'
    csv_files = [file for file in os.listdir(folder_path) if file.endswith('.csv')]
    output_file = 'data/playerData/2024_week14/roster_game_logs.csv'
    
    if not csv_files:
        print("No CSV files found in the folder.")
        return pd.DataFrame()  # Return an empty DataFrame if no files are found

    combined_dataframes = []
    
    for file in csv_files:
        file_path = os.path.join(folder_path, file)
        try:
            df = pd.read_csv(file_path)
            combined_dataframes.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    # Combine all dataframes into one
    if combined_dataframes:
        combined_df = pd.concat(combined_dataframes, ignore_index=True)
        try:
            combined_df.to_csv(output_file, index=False)
            print(f"Combined DataFrame saved to {output_file}")
        except Exception as e:
            print(f"Error saving combined DataFrame to {output_file}: {e}")
        return combined_df
    else:
        print("No valid CSV files could be loaded.")
        return pd.DataFrame()
