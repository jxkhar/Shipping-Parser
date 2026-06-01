import os
import sqlite3

def clean_project_database():
    db_name = "shipping_market.db"
    print("==================================================================")
    print("🧹 MARITIME DATABASE CLEANING SYSTEM")
    print("==================================================================\n")
    
    # Check if the database file exists in your project workspace directory
    if os.path.exists(db_name):
        try:
            # Drop the file completely from the hard drive
            os.remove(db_name)
            print(f"🗑️  Success: Removed '{db_name}' file from your system workspace disk.")
            print("✨ All junk records and duplication hashes have been completely cleared out.")
        except Exception as e:
            print(f"⚠️  Database file locked by an active process (Streamlit is likely running).")
            print("🔄 Switching to manual table truncation routing...\n")
            
            # Truncation fallback if Streamlit or VS Code debugger is keeping the file open
            try:
                with sqlite3.connect(db_name) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DROP TABLE IF EXISTS tonnage_records")
                    cursor.execute("DROP TABLE IF EXISTS cargo_vc_records")
                    cursor.execute("DROP TABLE IF EXISTS cargo_tc_records")
                    cursor.execute("DROP TABLE IF EXISTS processed_blocks")
                    conn.commit()
                print("✅ Success: Wiped all database rows and metadata tables clean.")
            except Exception as inner_error:
                print(f"❌ Critical Error: Could not clear data store tables: {inner_error}")
    else:
        print("ℹ️  No 'shipping_market.db' file was found in this folder. Your workspace is already clean.")

if __name__ == "__main__":
    clean_project_database()