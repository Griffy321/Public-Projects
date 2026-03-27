import pandas as pd

def log_operation(user_input, result):
    log_entry = {"operation": user_input, "result": result, "created_at": pd.Timestamp.now(tz="UTC")}
    log_entry_df = pd.DataFrame([log_entry])
    try:
        log_entry_df.to_csv("calc_log.csv", mode="a", header=not pd.io.common.file_exists("calc_log.csv"), index=False)
    except Exception as e:
        print(f"Error logging operation: {e}")