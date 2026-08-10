# investing.com internal stock IDs, carried over from your original scraper.
STOCK_IDS = {
    "ADH": "13230", "ADI": "13231", "AFI": "19062", "AFM": "962402",
    "AGM": "13233", "AKT": "1198377", "ALM": "13234", "ARD": "1168946",
    "ATH": "13238", "ATL": "13236", "ATW": "13237", "BAL": "13239",
    "BCI": "13243", "BCP": "13240", "BOA": "13242", "CDM": "13244",
    "CFG": "1209572", "CIH": "13246", "CMA": "13287", "CMG": "1224439",
    "CMT": "13247", "COL": "13248", "CRS": "13249", "CSR": "13250",
    "CTM": "13251", "DHO": "13253", "DRI": "13252", "DWY": "19064",
    "DYT": "1193602", "EQD": "13256", "FBR": "13257", "GAZ": "13232",
    "HPS": "13260", "IAM": "13261", "IBC": "13262", "IMO": "1118022",
    "INV": "13263", "JET": "19065", "LBV": "13266", "LES": "13267",
    "LHM": "13264", "M2M": "13269", "MAB": "13270", "MDP": "13279",
    "MIC": "13272", "MLE": "13273", "MNG": "13274", "MOX": "13278",
    "MSA": "986125", "MUT": "1116047", "NEJ": "13275", "NKL": "19067",
    "OUL": "13277", "PRO": "13280", "RDS": "943412", "REB": "13281",
    "RIS": "13282", "S2M": "941682", "SAH": "19063", "SBM": "13284",
    "SID": "13293", "SLF": "13288", "SMI": "13289", "SNA": "13290",
    "SNP": "13291", "SOT": "13294", "SRM": "13295", "STR": "19068",
    "TGC": "1182995", "TMA": "955692", "TQM": "941193", "UMR": "13298",
    "WAA": "13299", "ZDJ": "13300",
}

# investing.com's internal ID for the MASI index itself. Find it the same
# way you found the stock IDs: open the MASI page on investing.com, open
# your browser's Network tab, filter for "historical", and look at the
# request URL — it ends in /historical/<id>. Paste that number below.
MASI_INDEX_ID = "13228"
