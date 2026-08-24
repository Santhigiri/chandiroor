# Load Nakshatra names and boundaries
NAKSHATRA_NAMES = [
    "Aswathy", 
    "Bharani", 
    "Karthika", 
    "Rohini", 
    "Makayiram",
    "Thiruvathira", 
    "Punartham", 
    "Pooyam",
    "Aayilyam", 
    "Makam", 
    "Pooram", 
    "Uthram",
    "Atham",
    "Chithira",
    "Chothi",
    "Vishagam",
    "Anizham",
    "Thrikketta",
    "Moolam",
    "Pooradam",
    "Uthradam",
    "Thiruvonam",
    "Avittam",
    "Chathayam",
    "Poororuttathi",
    "Uthrattathi",
    "Revathi"
]
NAKSHATRA_NAMES_ML = [
    "അശ്വതി",
    "ഭരണി",
    "കാർത്തിക",
    "രോഹിണി",
    "മകയിരം",
    "തിരുവാതിര",
    "പുണർതം",
    "പൂയം",
    "ആയില്യം",
    "മകം",
    "പൂരം",
    "ഉത്രം",
    "അത്തം",
    "ചിത്തിര",
    "ചോതി",
    "വിശാഖം",
    "അനിഴം",
    "തൃക്കേട്ട",
    "മൂലം",
    "പൂരാടം",
    "ഉത്രാടം",
    "തിരുവോണം",
    "അവിട്ടം",
    "ചതയം",
    "പൂരുരുട്ടാതി",
    "ഉത്രട്ടാതി",
    "രേവതി"
]

NAKSHATRA_BOUNDARIES = [i*(360/27) for i in range(1,28)]


THITHI_NAMES = [
    # Shukla Paksha (Waxing Moon)
    "Prathama (Shukla Paksha)",
    "Dwitiya (Shukla Paksha)",
    "Tritiya (Shukla Paksha)",
    "Chaturthi (Shukla Paksha)",
    "Panchami (Shukla Paksha)",
    "Shashthi (Shukla Paksha)",
    "Saptami (Shukla Paksha)",
    "Ashtami (Shukla Paksha)",
    "Navami (Shukla Paksha)",
    "Dashami (Shukla Paksha)",
    "Ekadashi (Shukla Paksha)",
    "Dwadashi (Shukla Paksha)",
    "Trayodashi (Shukla Paksha)",
    "Chaturdashi (Shukla Paksha)",
    "Pournami",  # Full Moon (no Paksha suffix needed)

    # Krishna Paksha (Waning Moon)
    "Prathama (Krishna Paksha)",
    "Dwitiya (Krishna Paksha)",
    "Tritiya (Krishna Paksha)",
    "Chaturthi (Krishna Paksha)",
    "Panchami (Krishna Paksha)",
    "Shashthi (Krishna Paksha)",
    "Saptami (Krishna Paksha)",
    "Ashtami (Krishna Paksha)",
    "Navami (Krishna Paksha)",
    "Dashami (Krishna Paksha)",
    "Ekadashi (Krishna Paksha)",
    "Dwadashi (Krishna Paksha)",
    "Trayodashi (Krishna Paksha)",
    "Chaturdashi (Krishna Paksha)",
    "Amavasya"  # New Moon (no Paksha suffix needed)
]

THITHI_NAMES_ML = [
    # Shukla Paksha
    "പ്രഥമ (ശുക്ല പക്ഷം)",
    "ദ്വിതീയ (ശുക്ല പക്ഷം)",
    "തൃതീയ (ശുക്ല പക്ഷം)",
    "ചതുർത്ഥി (ശുക്ല പക്ഷം)",
    "പഞ്ചമി (ശുക്ല പക്ഷം)",
    "ഷഷ്ഠി (ശുക്ല പക്ഷം)",
    "സപ്തമി (ശുക്ല പക്ഷം)",
    "അഷ്ടമി (ശുക്ല പക്ഷം)",
    "നവമി (ശുക്ല പക്ഷം)",
    "ദശമി (ശുക്ല പക്ഷം)",
    "ഏകാദശി (ശുക്ല പക്ഷം)",
    "ദ്വാദശി (ശുക്ല പക്ഷം)",
    "ത്രയോദശി (ശുക്ല പക്ഷം)",
    "ചതുർദശി (ശുക്ല പക്ഷം)",
    "പൗർണമി",

    # Krishna Paksha
    "പ്രഥമ (കൃഷ്ണ പക്ഷം)",
    "ദ്വിതീയ (കൃഷ്ണ പക്ഷം)",
    "തൃതീയ (കൃഷ്ണ പക്ഷം)",
    "ചതുർത്ഥി (കൃഷ്ണ പക്ഷം)",
    "പഞ്ചമി (കൃഷ്ണ പക്ഷം)",
    "ഷഷ്ഠി (കൃഷ്ണ പക്ഷം)",
    "സപ്തമി (കൃഷ്ണ പക്ഷം)",
    "അഷ്ടമി (കൃഷ്ണ പക്ഷം)",
    "നവമി (കൃഷ്ണ പക്ഷം)",
    "ദശമി (കൃഷ്ണ പക്ഷം)",
    "ഏകാദശി (കൃഷ്ണ പക്ഷം)",
    "ദ്വാദശി (കൃഷ്ണ പക്ഷം)",
    "ത്രയോദശി (കൃഷ്ണ പക്ഷം)",
    "ചതുർദശി (കൃഷ്ണ പക്ഷം)",
    "അമാവാസി"
]


MALAYALAM_MONTH_ML = [
    "മേടം",
    "ഇടവം",
    "മിഥുനം",
    "കർക്കടകം",
    "ചിങ്ങം",
    "കന്നി",
    "തുലാം",
    "വൃശ്ചികം",
    "ധനു",
    "മകരം",
    "കുംഭം",
    "മീനം"
]

class Coordinates:
    SG_LATITUDE: float = 8.645
    SG_LONGITUDE: float = 76.938

DEFAULT_TIMEZONE = 'Asia/Kolkata'

NAKSHATRA_TRANSITION_STEP_DAYS = 0.01 # 0.01 for 2021-2027, 2029-2030 0.05 for 2028
