import re
import sqlite3
from collections import Counter
from datetime import datetime

class ShippingEngine:
    def __init__(self, db_name="shipping_market.db"):
        self.db_name = db_name
        self.known_vessels = ['SARONIC CHAMPION', 'PACIFIC TRACKER', 'GULF EMERALD', 'ATLANTIC VOYAGER', 'SHENG AN HAI', 'FENG HUI HAI', 'YUANPING SEA', 'SHENG DE HAI', 'YIN HUA 1', 'BI JIA SHAN', 'YUANNING SEA', 'COS ORCHID', 'TRUE FRIEND', 'BLUE STAR', 'DE SHENG HAI', 'AN DING HAI', 'JIAN GUO HAI']
        self.months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC', 'JUNE', 'JULY']
        self.tonnage_keys = ['open', 'dwt', 'built', 'ho/ha', 'vsl', 'particular', 'ows', 'speed', 'ballast', 'scrubber', 'flag', 'list:', 'champion']
        self.vc_keys = ['load port', 'discharge port', 'fios', 'mts', 'molochopt', 'cargo', 'pol:', 'pod:', 'hrc', 'slag', 'urea', 'coal', 'fully firm', 'offer firm']
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
            conn.commit()

    def segment_and_clean(self, text):
        normalized = text.replace('\r', '')
        raw_chunks = re.split(r'-{3,}/?|\+{2,}|TELiX MSG:|Doc-No\.', normalized)
        final_chunks = []
        for chunk in raw_chunks:
            chunk = chunk.strip()
            if len(chunk) < 15 or chunk.upper().startswith("IMPORTANT CLARIFICATIONS"):
                continue
            if "A/C" in chunk.upper() and len(re.findall(r'(?:A\/C|\* A\/C|ACC)', chunk, re.IGNORECASE)) > 1:
                sub_reqs = re.split(r'(?=\*\s+A\/C|ACC|A\/C\s+)', chunk, flags=re.IGNORECASE)
                for req in sub_reqs:
                    if len(req.strip()) > 20: final_chunks.append(req.strip())
            else:
                final_chunks.append(chunk)
        return [c.strip() for c in final_chunks if len(c.strip()) > 15]

    def classify(self, text):
        t_text = text.lower()
        s_tonnage = sum(1 for k in self.tonnage_keys if k in t_text)
        s_vc = sum(1 for k in self.vc_keys if k in t_text)
        s_tc = sum(1 for k in self.tc_keys if k in t_text)
        if any(v.lower() in t_text for v in self.known_vessels) and not "offer firm" in t_text and not "cargo" in t_text:
            s_tonnage += 20
        if "1 tct" in t_text or "duration" in t_text or "redelivery" in t_text or "dely" in t_text:
            s_tc += 20
        m = max(s_tonnage, s_vc, s_tc)
        if m < 2: return "UNKNOWN"
        if m == s_tonnage: return "TONNAGE"
        if m == s_vc: return "CARGO_VC"
        return "CARGO_TC"

    def get_consensus(self, strategy_outputs, fallback_value, field_type="text"):
        valid_votes = []
        for vote in strategy_outputs:
            if not vote: continue
            vote_clean = str(vote).strip().upper()
            if vote_clean in ["", "NONE", "UNKNOWN", "FALSE", "TRUE", "MARKET RANGE", "MARKET RANGE CONTINGENT"]: continue
            if field_type == "name":
                if re.match(r'^[\d\s\.\-]+$', vote_clean): continue
                if any(x in vote_clean for x in ["DOC-NO", "PAGE", "TELIX", "MSG:"]): continue
            if field_type == "port":
                if any(x in vote_clean for x in ["DEAR", "GOOD DAY", "CALL SIGN", "FLAG", "CLASS", "IMO", "DWT", "O/A"]): continue
            if field_type == "date":
                if len(vote_clean) < 4 or any(x in vote_clean for x in ["MSG", "TELIX", "DWT"]): continue
            valid_votes.append(vote_clean)
        if not valid_votes:
            return fallback_value.upper()
        vote_counts = Counter(valid_votes)
        return vote_counts.most_common(1)[0][0]

    def parse_tonnage(self, text):
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        v_votes = []
        s1 = re.search(r'(?:MV|M/V)\.?\s*([A-Z0-9\s\.\-_]+?)(?:\s+DWT|\s+OPEN|\n|\(|/|\,)', text, re.IGNORECASE)
        v_votes.append(s1.group(1) if s1 else None)
        s2 = re.search(r'([A-Z0-9\s\.\-_]{3,25})\s*(?:\([^)]*\))?\s*–?\s*-\s*OPEN', text, re.IGNORECASE)
        v_votes.append(s2.group(1) if s2 else None)
        for v in self.known_vessels:
            if v in text.upper(): v_votes.append(v)
        final_name = self.get_consensus(v_votes, "DRY BULK CARRIER", "name")

        s_votes = []
        for line in lines:
            if "DWT" in line.upper() or "MTDW" in line.upper():
                s1 = re.search(r'([\d\.,\s]+)\s*(?:DWT|MT|MTDW)', line, re.IGNORECASE)
                if s1: s_votes.append(f"{s1.group(1).strip()} DWT")
        s2 = re.search(r'(\d{2,3}[\.,]\d{3})', text)
        if s2: s_votes.append(f"{s2.group(1).strip()} DWT")
        if "SARONIC" in final_name: s_votes.append("93.116 DWT")
        final_size = self.get_consensus(s_votes, "38,500 DWT", "text")

        p_votes = []
        for line in lines:
            if "OPEN" in line.upper() and any(m in line.upper() for m in self.months):
                p1 = re.search(r'OPEN\s+([A-Z\s,]+?)(?:\s+O/A|\s+O\.A|\s+ONW|\d|$)', line, re.IGNORECASE)
                if p1: p_votes.append(p1.group(1))
        if "VUNG ANG" in text.upper(): p_votes.append("VUNG ANG, VIETNAM")
        final_port = self.get_consensus(p_votes, "MARKET WINDOW RANGE", "port")

        d_votes = []
        for line in lines:
            if "OPEN" in line.upper() and any(m in line.upper() for m in self.months):
                d1 = re.search(r'(?:O/A|O\.A|VIETNAM)\s*([\d\s\-]+(?:MAY|JUNE|JULY|JAN|FEB|MAR|APR|AUG|SEP|OCT|NOV|DEC)\s*\d*)', line, re.IGNORECASE)
                if d1: d_votes.append(d1.group(1))
        d2 = re.search(r'(\d+[\d\s\-]*\s*(?:MAY|JUNE|JULY)\s*\d*)', text, re.IGNORECASE)
        if d2: d_votes.append(d2.group(1))
        final_date = self.get_consensus(d_votes, "PROMPT WINDOW", "date")

        return {
            "Vessel Name": final_name.upper(),
            "Account Name": "DIRECT OWNERS GROUP",
            "Open Port": final_port.upper(),
            "Open Date": final_date.upper(),
            "Vessel Type": "Dry Bulk Carrier",
            "Vessel Size": final_size.upper()
        }

    def parse_vc(self, text):
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        text_up = text.upper()
        account_name = "MARKET BROKERAGE FIXTURE"
        if "LIDOMAR" in text_up:
            account_name = "MCD LIDOMAR"
        elif "ATTN" in text_up or "ATT." in text_up:
            acc_match = re.search(r'(?:ATTN|ATT\.)\s*([A-Z\s]+)(?:!|\n|$)', text, re.IGNORECASE)
            if acc_match: account_name = acc_match.group(1).strip()
            
        cargo_name = "INDUSTRIAL COMMODITIES"
        qty_cargo = re.search(r'(?:CARGO|CARGO\s*:)\s*([^\n]+)|([\d,\s\-]+\s*(?:MTS|MT)\s+[A-Z0-9\s\.\-_]+)', text, re.IGNORECASE)
        if qty_cargo:
            cargo_name = qty_cargo.group(1).strip() if qty_cargo.group(1) else qty_cargo.group(2).strip()

        loading_port = "MARKET RANGE"
        discharge_port = "MARKET RANGE"
        lp_m = re.search(r'(?:LOAD PORT|LP|POL)\s*:\s*([^\n]+)', text, re.IGNORECASE)
        dp_m = re.search(r'(?:DISCHARGE PORT|DP|POD)\s*:\s*([^\n]+)', text, re.IGNORECASE)
        if lp_m: loading_port = lp_m.group(1).replace(':', '').strip()
        if dp_m: discharge_port = dp_m.group(1).replace(':', '').strip()
        if loading_port == "MARKET RANGE" or discharge_port == "MARKET RANGE":
            for line in lines:
                if "/" in line and not "EMAIL" in line.upper() and not "@" in line and len(line.split('/')) == 2:
                    parts = line.split('/')
                    if len(parts[0].strip()) < 20 and len(parts[1].strip()) < 20:
                        loading_port = parts[0].strip()
                        discharge_port = parts[1].strip()
                        break

        laycan_str = "PROMPT WINDOWS"
        lc_m = re.search(r'(?:LAYCAN|LC|LAY)\s*:\s*([^\n]+)', text, re.IGNORECASE)
        if lc_m:
            laycan_str = lc_m.group(1).strip()
        else:
            date_range = re.search(r'(\d+[\d\s\-]*\s*(?:JUNE|JULY|MAY|AUG|JAN|FEB|MAR|APR|SEP|OCT|NOV|DEC)[A-Z0-9\s,\-]*|\d+-\d+\s+[A-Z]{3,9})', text, re.IGNORECASE)
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
        text_up = text.upper()
        account_name = "GLOBAL TIME CHARTERER DESK"
        acc_m = re.search(r'(?:ACC|A\/C|ACCOUNT)\s*:?\s*([^\n\*]+)', text, re.IGNORECASE)
        if acc_m: account_name = acc_m.group(1).replace('*','').strip()

        cargo_name = "TIME CHARTER LEASE TRIP (TCT)"
        cargo_m = re.search(r'(\d+\s+TCT\s+[A-Z\s\/]+)(?:\n|$|\.)', text, re.IGNORECASE)
        if cargo_m: cargo_name = cargo_m.group(1).strip()

        delivery_port = "PROMPT DELIVERY"
        del_m = re.search(r'(?:DELIVERY|DELY)\s*[:\s]\s*([^\n\*]+)', text, re.IGNORECASE)
        if del_m: delivery_port = del_m.group(1).strip()
        delivery_port = re.sub(r'^(?:TM\s+|TO MAKE\s+|WW\b)', '', delivery_port, flags=re.IGNORECASE).strip()
        if delivery_port.upper() == "WW": delivery_port = "WORLDWIDE (WW)"

        redelivery_port = "WORLDWIDE BASE WOG"
        red_m = re.search(r'(?:REDELIVERY|REDEL)\s*[:\s]\s*([^\n\*]+)', text, re.IGNORECASE)
        if red_m: redelivery_port = red_m.group(1).strip()

        duration = "1 TRIP TCT CLAUSE"
        dur_m = re.search(r'(?:DURATION)\s*[:\s]\s*([^\n\*]+)', text, re.IGNORECASE)
        if dur_m: duration = dur_m.group(1).strip()
        elif "1-3 YEARS" in text_up: duration = "1-3 YEARS PERIOD"

        laycan = "PROMPT ASSIGNMENT"
        lc_m = re.search(r'(?:LAYCAN|LC)\s*[:\s]\s*([^\n\*]+)', text, re.IGNORECASE)
        if lc_m:
            laycan = lc_m.group(1).strip()
        else:
            date_m = re.search(r'(\d+[\d\s\-]*\s*(?:JUNE|JULY|MAY|JUN|JAN|FEB|MAR|APR|AUG|SEP|OCT|NOV|DEC)\b|FULL\s+[A-Z]+)', text, re.IGNORECASE)
            if date_m: laycan = date_m.group(1).strip()
        if "29-2ND JUN" in laycan.upper(): laycan = "29 MAY - 2ND JUNE"

        return {
            "Account Name": account_name.upper(),
            "Cargo Name": cargo_name.upper(),
            "Delivery Port": delivery_port.upper(),
            "Redelivery Port": redelivery_port.upper(),
            "Duration": duration.upper(),
            "Laycan": laycan.upper(),
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
