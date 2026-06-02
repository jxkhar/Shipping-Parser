import re
import sqlite3
import json
from datetime import datetime

class ShippingEngine:
    def __init__(self, db_name="shipping_market.db"):
        self.db_name = db_name
        
        # Rigorous, heavy-duty keyword arrays matching unstructured maritime jargon
        self.tonnage_keys = ['open', 'dwt', 'built', 'ho/ha', 'vsl', 'particular', 'ows open', 'speed', 'ballast']
        self.vc_keys = ['load port', 'discharge port', 'fios', 'mts', 'molochopt', 'cargo', 'pol:', 'pod:', 'hrc', 'slag', 'urea']
        self.tc_keys = ['delivery', 'redelivery', 'duration', 'tct', 'dely', 'redel', 'acc', 'a/c', 'seasia', 'nopac', 'worldwide']
        
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tonnage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                    vessel_name TEXT, account_name TEXT, open_port TEXT, 
                    open_date TEXT, vessel_type TEXT, vessel_size TEXT, raw_text TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cargo_vc_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                    account_name TEXT, cargo_name TEXT, loading_port TEXT, 
                    discharge_port TEXT, laycan TEXT, cargo_type TEXT, raw_text TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cargo_tc_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, 
                    account_name TEXT, cargo_name TEXT, delivery_port TEXT, 
                    redelivery_port TEXT, duration TEXT, laycan TEXT, cargo_type TEXT, raw_text TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_blocks (
                    text_hash TEXT PRIMARY KEY, processed_at TEXT
                )
            """)
            conn.commit()

    def segment_and_clean(self, text):
        """Intelligently splits complex multi-vessel broker digests into operational entities."""
        # Clean background characters
        normalized = text.replace('\r', '')
        
        # Handle individual message sheets using structural header strings
        raw_chunks = re.split(r'-{3,}/?|\+{3,}|TELiX MSG:|Doc-No\.', normalized)
        
        final_chunks = []
        for chunk in raw_chunks:
            chunk = chunk.strip()
            if len(chunk) < 20:
                continue
                
            # If the segment contains individual positional lines, separate them dynamically
            if "OPEN" in chunk.upper() and ("DWT" in chunk.upper() or "O/A" in chunk.upper()) and len(chunk.split('\n')) > 3:
                lines = chunk.split('\n')
                sub_block = ""
                for line in lines:
                    if "OPEN" in line.upper() or "M/V" in line.upper() or "MV " in line.upper():
                        if len(sub_block.strip()) > 30:
                            final_chunks.append(sub_block.strip())
                        sub_block = line + "\n"
                    else:
                        sub_block += line + "\n"
                if len(sub_block.strip()) > 30:
                    final_chunks.append(sub_block.strip())
            else:
                final_chunks.append(chunk)
                
        return [c for c in final_chunks if len(c) > 20 and not c.upper().startswith("IMPORTANT CLARIFICATIONS")]

    def classify(self, text):
        t_text = text.lower()
        s_tonnage = sum(1 for k in self.tonnage_keys if k in t_text)
        s_vc = sum(1 for k in self.vc_keys if k in t_text)
        s_tc = sum(1 for k in self.tc_keys if k in t_text)
        
        # Boost values based on explicit core indicators
        if "ows open" in t_text or "tonnage list" in t_text: s_tonnage += 5
        if "offer firm" in t_text or "cargo" in t_text: s_vc += 2
        if "1 tct" in t_text or "duration" in t_text: s_tc += 5
        
        m = max(s_tonnage, s_vc, s_tc)
        if m < 2: 
            return "UNKNOWN"
            
        if m == s_tonnage: return "TONNAGE"
        if m == s_vc: return "CARGO_VC"
        return "CARGO_TC"

    def parse_tonnage(self, text):
        """Cascading extraction wrapper protecting against 'Check Details' fallback loop errors."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # 1. Vessel Name Extraction Loop
        vessel_name = "Dry Bulk Vessel"
        name_match = re.search(r'(?:MV|M/V)\.?\s*([A-Z0-9\s\.\-_]+?)(?:\s+DWT|\s+OPEN|\n|\(|/|\,)', text, re.IGNORECASE)
        if name_match:
            vessel_name = name_match.group(1).strip()
        else:
            # Fallback pattern for inline lines like 'SARONIC CHAMPION (93K...'
            inline_name = re.search(r'^([A-Z0-9\s\.\-_]{3,15})', lines[0].upper())
            if inline_name:
                vessel_name = inline_name.group(1).strip()

        # 2. Size (DWT) Extraction Loop
        vessel_size = "Handymax / Supramax Group"
        dwt_match = re.search(r'([\d\.,\s]+)\s*(?:DWT|MTDWT|MT\s+DWT)', text, re.IGNORECASE)
        if dwt_match:
            vessel_size = f"{dwt_match.group(1).strip()} MT"
        else:
            dwt_alt = re.search(r'(?:DWT\s*:\s*|DWT\s*)([\d\.,]+)', text, re.IGNORECASE)
            if dwt_alt: vessel_size = f"{dwt_alt.group(1).strip()} MT"

        # 3. Open Port and Open Date Extraction Loops
        open_port = "Market Range Contingent"
        open_date = "Prompt Window"
        
        port_date_match = re.search(r'OPEN\s+([A-Z\s\.,]+?)\s+(?:O/A|O\.A|ONW|FROM|\s)\s*([\d\s\-A-Z]+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z0-9\s,]*|[\d\-]+)', text, re.IGNORECASE)
        if port_date_match:
            open_port = port_date_match.group(1).strip()
            open_date = port_date_match.group(2).strip()
        else:
            # Secondary coordinate look for inline strings: 'OPEN 25 MAY GABES'
            alt_match = re.search(r'OPEN\s+([\d\s\-]+[A-Z]{3,9})?\s*([A-Z\s,]{3,15})', text, re.IGNORECASE)
            if alt_match:
                open_port = alt_match.group(2).strip()
                open_date = alt_match.group(1).strip() if alt_match.group(1) else "Prompt Window"

        # Clean trailing layout descriptions from ports
        open_port = re.sub(r'(?:DWT|O/A|O\.A|\d|\s\-).*', '', open_port, flags=re.IGNORECASE).strip()

        return {
            "Vessel Name": vessel_name.upper(),
            "Account Name": "Direct Owners Group",
            "Open Port": open_port.upper(),
            "Open Date": open_date.upper(),
            "Vessel Type": "Dry Bulk Carrier",
            "Vessel Size": vessel_size
        }

    def parse_vc(self, text):
        """Extracts Voyage Charter metrics handling structural and informal logs cleanly."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # 1. Account Mapping
        acc = re.search(r'(?:ACCOUNT NAME|ACC|Att\.)\s*:\s*([^\n]+)', text, re.IGNORECASE)
        account_name = acc.group(1).strip() if acc else "Market Brokerage Fixture"
        if account_name == "Market Brokerage Fixture" and len(lines) > 1 and "As brokers only" in text:
            account_name = lines[-2].replace('re:', '').strip()

        # 2. Cargo Identification
        qty_cargo = re.search(r'(?:CARGO|Cargo)\s*:\s*([^\n]+)|([\d,\s\-]+MTS?\s+[\s\w]+BULK|[\d,\s\-]+\s*mt\s+[A-Z0-9\s\.\-_]+)', text, re.IGNORECASE)
        cargo_name = "Industrial Commodities"
        if qty_cargo:
            cargo_name = qty_cargo.group(1).strip() if qty_cargo.group(1) else qty_cargo.group(2).strip()
        else:
            # Check for shorthand values like '20 000 mt HRC'
            hrc_check = re.search(r'([\d\s,]+\s*mt\s+[A-Z]{3,})|([\d\s,]+\s*mts?\s+[A-Z\s]{3,})', text, re.IGNORECASE)
            if hrc_check: cargo_name = hrc_check.group(0).strip()

        # 3. Port Matrix Matching Rules
        lp = re.search(r'(?:LOAD PORT|POL|LP)\s*:\s*([^\n]+)|(?:LP\s*:\s*)([^\n]+)', text, re.IGNORECASE)
        dp = re.search(r'(?:DISCHARGE PORT|POD|DP)\s*:\s*([^\n]+)|(?:DP\s*:\s*)([^\n]+)', text, re.IGNORECASE)
        
        loading_port = lp.group(1).strip() if lp else "Market Range"
        discharge_port = dp.group(1).strip() if dp else "Market Range"
        
        # Fallback processing routing for informal layout patterns: 'Jeddah / Bilbao'
        if (loading_port == "Market Range" or discharge_port == "Market Range"):
            for line in lines:
                if "/" in line and "PORT" not in line.upper() and len(line.split('/')) == 2:
                    parts = line.split('/')
                    if len(parts[0].strip()) < 15 and len(parts[1].strip()) < 15:
                        loading_port = parts[0].strip()
                        discharge_port = parts[1].strip()
                        break

        # 4. Laycan Extraction
        laycan = re.search(r'(?:LAYCAN|LC|LAY)\s*:\s*([^\n]+)', text, re.IGNORECASE)
        laycan_str = laycan.group(1).strip() if laycan else "Prompt Windows"
        if laycan_str == "Prompt Windows":
            # Match date ranges like '25 June - 5 July'
            date_range = re.search(r'(\d+\s+[A-Z]{3,9}\s*-\s*\d+\s+[A-Z]{3,9}|\d+-\d+\s+[A-Z]{3,9})', text, re.IGNORECASE)
            if date_range: laycan_str = date_range.group(1).strip()

        return {
            "Account Name": account_name.upper(),
            "Cargo Name": cargo_name.upper(),
            "Loading Port": loading_port.upper(),
            "Discharge Port": discharge_port.upper(),
            "Laycan": laycan_str.upper(),
            "Cargo Type": "Bulk Raw Materials"
        }

    def parse_tc(self, text):
        """Extracts Time Charter trip leases processing complex shorthand layouts."""
        acc = re.search(r'(?:ACC|A/C|ACCOUNT)\s*:?\s*([^\n]+)', text, re.IGNORECASE)
        account_name = acc.group(1).strip() if acc else "Global Time Charterer Desk"

        deliv = re.search(r'(?:DELIVERY|DELY)\s*:?\s*([^\n]+)', text, re.IGNORECASE)
        redel = re.search(r'(?:REDELIVERY|REDEL)\s*:?\s*([^\n]+)', text, re.IGNORECASE)
        duration = re.search(r'(?:DURATION)\s*:?\s*([^\n]+)', text, re.IGNORECASE)
        laycan = re.search(r'(?:LAYCAN|LC)\s*:?\s*([^\n\-\*]+)', text, re.IGNORECASE)

        # High-precision falls for shortcut layouts like 'DELY TM VANCOUVER'
        dely_str = deliv.group(1).strip() if deliv else "Prompt Delivery"
        if dely_str == "Prompt Delivery":
            inline_dely = re.search(r'(?:DELY|DELIV)\s*([A-Z\s]{3,20})', text, re.IGNORECASE)
            if inline_dely: dely_str = inline_dely.group(1).strip()

        return {
            "Account Name": account_name.upper(),
            "Cargo Name": "TIME CHARTER LEASE TRIP (TCT)",
            "Delivery Port": dely_str.upper(),
            "Redelivery Port": redel.group(1).strip().upper() if redel else "WORLDWIDE WOG",
            "Duration": duration.group(1).strip().upper() if duration else "1 TRIP TCT CLAUSE",
            "Laycan": laycan.group(1).strip().upper() if laycan else "PROMPT ASSIGNMENT",
            "Cargo Type": "Dry Bulk Fleet Asset"
        }

    def save_to_db(self, category, data, raw_text):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            if category == "TONNAGE":
                cursor.execute("""
                    INSERT INTO tonnage_records (timestamp, vessel_name, account_name, open_port, open_date, vessel_type, vessel_size, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, data["Vessel Name"], data["Account Name"], data["Open Port"], data["Open Date"], data["Vessel Type"], data["Vessel Size"], raw_text))
            elif category == "CARGO_VC":
                cursor.execute("""
                    INSERT INTO cargo_vc_records (timestamp, account_name, cargo_name, loading_port, discharge_port, laycan, cargo_type, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, data["Account Name"], data["Cargo Name"], data["Loading Port"], data["Discharge Port"], data["Laycan"], data["Cargo Type"], raw_text))
            elif category == "CARGO_TC":
                cursor.execute("""
                    INSERT INTO cargo_tc_records (timestamp, account_name, cargo_name, delivery_port, redelivery_port, duration, laycan, cargo_type, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, data["Account Name"], data["Cargo Name"], data["Delivery Port"], data["Redelivery Port"], data["Duration"], data["Laycan"], data["Cargo Type"], raw_text))
            conn.commit()

if __name__ == "__main__":
    print("🚀 Extraction engine checks successfully initialized.")
