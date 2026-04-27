import streamlit as st
import pandas as pd
from datetime import timezone, timedelta, datetime
from supabase import create_client

# ================= CONFIG =================
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= GEAR LABEL =================
GEAR_LABELS = {
    "luc_chien":"Lực chiến","dps":"Dps","vu_khi":"Vũ khí","khien":"Khiên","non":"Nón",
    "vai":"Vai","giap":"Giáp","quan":"Quần","tay":"Tay","ao_choang":"Áo choàng",
    "giay":"Giầy","bong_tai_1":"Bông tai 1","bong_tai_2":"Bông tai 2",
    "day_chuyen":"Dây chuyền","nhan_1":"Nhẫn 1","nhan_2":"Nhẫn 2",
    "vong_tay_1":"Vòng tay 1","vong_tay_2":"Vòng tay 2"
}
GEAR_COLUMNS = list(GEAR_LABELS.keys())

# ================= SYSTEM STATE =================
def load_system_state():
    res = supabase.table("system_state").select("*").execute()
    if not res.data:
        supabase.table("system_state").insert({
            "id": 1,
            "last_nightmare_date": None,
            "last_trial_reset_date": None
        }).execute()
        return {"last_nightmare_date": None, "last_trial_reset_date": None}
    return res.data[0]

def update_system_state(data):
    supabase.table("system_state").update(data).eq("id", 1).execute()

# ================= LOAD =================
def safe_parse_time(col):
    parsed = pd.to_datetime(col, errors="coerce", utc=True)
    now = pd.Timestamp.now(tz=UTC7)
    parsed = parsed.fillna(now)
    return parsed.dt.tz_convert(UTC7)

def load_data():
    res = supabase.table("energy_tracker").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    df["last_update"] = safe_parse_time(df["last_update"])
    return df

# ================= SAVE =================
def save_row(row):
    utc_time = row["last_update"].astimezone(timezone.utc)

    supabase.table("energy_tracker").update({
        "energy": int(row["energy"]),
        "nightmare": int(row["nightmare"]),
        "trial": int(row["trial"]),
        "last_update": utc_time.isoformat()
    }).eq("id", int(row["id"])).execute()

# ================= TIME =================
def get_block_time(dt):
    dt = dt.astimezone(UTC7)
    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

# ================= ENERGY =================
def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = df.loc[i, "last_update"]
        last_block = get_block_time(last)

        diff_hours = int((now_block - last_block).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(df.loc[i, "energy"] + blocks * 15, MAX_ENERGY)
            df.loc[i, "last_update"] = last_block + pd.Timedelta(hours=blocks * 3)

    return df
# ================= HIGHLIGHT =================
def highlight_energy(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)

    if "energy" in df.columns:
        style["energy"] = df["energy"].apply(
            lambda v: "background-color:red;color:white"
            if v >= MAX_ENERGY else
            "background-color:yellow" if v >= MAX_ENERGY*0.8 else ""
        )

    if "nightmare" in df.columns:
        style["nightmare"] = df["nightmare"].apply(
            lambda v: "background-color:red;color:white"
            if v >= MAX_NIGHTMARE else
            "background-color:yellow" if v >= MAX_NIGHTMARE*0.8 else ""
        )

    return style
# ================= ALERT =================
def check_alert(df):
    full_e = df[df["energy"] >= MAX_ENERGY]["character"].tolist()
    warn_e = df[(df["energy"] >= MAX_ENERGY*0.8) & (df["energy"] < MAX_ENERGY)]["character"].tolist()

    full_n = df[df["nightmare"] >= MAX_NIGHTMARE]["character"].tolist()
    warn_n = df[(df["nightmare"] >= MAX_NIGHTMARE*0.8) & (df["nightmare"] < MAX_NIGHTMARE)]["character"].tolist()

    return full_e, warn_e, full_n, warn_n


# ================= AUTO SYSTEM =================
def auto_system(df):
    state = load_system_state()
    now = datetime.now(UTC7)
    today = str(now.date())

    # Nightmare
    if now.hour >= 3 and state["last_nightmare_date"] != today:
        df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)
        for i in df.index:
            save_row(df.loc[i])
        update_system_state({"last_nightmare_date": today})
        st.success("⚔️ Đã auto +2 Nightmare")

    # Reset Trial Thứ 4
    if now.weekday() == 2 and now.hour >= 3:
        if state["last_trial_reset_date"] != today:
            df["trial"] = 3
            for i in df.index:
                save_row(df.loc[i])
            update_system_state({"last_trial_reset_date": today})
            st.warning("🔁 Đã reset Trial")

    return df

# ================= GEAR =================
def load_gear():
    res = supabase.table("gear_tracker").select("*").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame(columns=["character"] + GEAR_COLUMNS)
    return df

def save_gear(character, data):
    payload = {"character": character}
    for col in GEAR_COLUMNS:
        payload[col] = int(data[col]) if data[col] else None
    supabase.table("gear_tracker").upsert(payload).execute()

def calc_gear_score(row):
    return sum([row[c] for c in GEAR_COLUMNS[2:] if pd.notna(row.get(c))])

def highlight_gear(df):
    style = pd.DataFrame("", index=df.index, columns=df.columns)
    for col in GEAR_COLUMNS[2:]:
        min_val = df[col].min(skipna=True)
        style[col] = df[col].apply(
            lambda v: "background-color:red;color:white"
            if pd.notna(v) and v == min_val else ""
        )
    return style

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()

# ================= RUN =================
st.session_state.df = update_energy(st.session_state.df)
st.session_state.df = auto_system(st.session_state.df)

# ================= UI =================
st.title("⚡ Energy Tracker PRO")
# ================= ALERT UI =================
full_e, warn_e, full_n, warn_n = check_alert(st.session_state.df)

if full_e:
    st.error(f"⚡ Full Energy: {', '.join(full_e)}")
if warn_e:
    st.warning(f"⚡ Energy 80%+: {', '.join(warn_e)}")
if full_n:
    st.error(f"💀 Full Nightmare: {', '.join(full_n)}")
if warn_n:
    st.warning(f"💀 Nightmare 80%+: {', '.join(warn_n)}")

# ================= TABLE =================
display_df = st.session_state.df.drop(columns=["id","last_update"], errors="ignore")

styled_df = display_df.style.apply(
    lambda x: highlight_energy(display_df),
    axis=None
)

st.dataframe(styled_df, use_container_width=True)

# ================= SELECT =================
idx = st.selectbox(
    "Character",
    st.session_state.df.index,
    format_func=lambda x: st.session_state.df.loc[x, "character"]
)

row = st.session_state.df.loc[idx]
character_name = row["character"]

# ================= INPUT =================
energy = st.number_input("Energy", 0, MAX_ENERGY, int(row["energy"]))
nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(row["nightmare"]))
trial = st.number_input("Trial", 0, 10, int(row["trial"]))

if st.button("💾 Save"):
    st.session_state.df.loc[idx, ["energy","nightmare","trial"]] = [energy,nightmare,trial]
    st.session_state.df.loc[idx, "last_update"] = get_block_time(pd.Timestamp.now(tz=UTC7))
    save_row(st.session_state.df.loc[idx])
    st.rerun()

# ================= GEAR UI =================
st.subheader("🛡️ Gear")

gear_df = load_gear()
gear_row = gear_df[gear_df["character"] == character_name]

gear_data = {}
cols = st.columns(4)

for i, col in enumerate(GEAR_COLUMNS):
    val = gear_row.iloc[0][col] if not gear_row.empty else 0
    with cols[i % 4]:
        gear_data[col] = st.number_input(
            GEAR_LABELS[col],
            value=int(val) if pd.notna(val) else 0,
            key=f"{character_name}_{col}"
        )

if st.button("💾 Save Gear"):
    save_gear(character_name, gear_data)
    st.rerun()

# ================= ALERT GEAR =================
if not gear_row.empty:
    rowg = gear_row.iloc[0]

    missing = [GEAR_LABELS[c] for c in GEAR_COLUMNS[2:] if pd.isna(rowg.get(c)) or rowg.get(c)==0]
    weak = []

    for col in GEAR_COLUMNS[2:]:
        min_val = gear_df[col].min(skipna=True)
        if rowg.get(col) == min_val:
            weak.append(GEAR_LABELS[col])

    if missing:
        st.warning(f"⚠️ Thiếu gear: {', '.join(missing)}")

    if weak:
        st.error(f"🔻 Gear yếu: {', '.join(weak)}")

# ================= GEAR TABLE =================
# ================= GEAR TABLE =================
st.subheader("📊 Gear Table")

if not gear_df.empty:

    # ===== DATA TÍNH TOÁN (GIỮ SỐ) =====
    calc_df = gear_df.copy()

    for col in calc_df.columns:
        if col != "character":
            calc_df[col] = pd.to_numeric(calc_df[col], errors="coerce")

    calc_df["gear_score"] = calc_df.apply(calc_gear_score, axis=1)

    # ===== DATA HIỂN THỊ (FORMAT ĐẸP) =====
    display_gear_df = calc_df.copy()

    for col in display_gear_df.columns:
        if col != "character":
            display_gear_df[col] = display_gear_df[col].apply(
                lambda x: f"{int(x):,}" if pd.notna(x) else ""
            )

    display_gear_df = display_gear_df.rename(columns=GEAR_LABELS)

    # ===== HIGHLIGHT (DÙNG calc_df) =====
def highlight_gear_display(df_calc, df_display):
    style = pd.DataFrame("", index=df_display.index, columns=df_display.columns)

    for col_key, col_label in GEAR_LABELS.items():

        # bỏ lực chiến + dps
        if col_key in ["luc_chien", "dps"]:
            continue

        if col_key not in df_calc.columns:
            continue

        series = df_calc[col_key].dropna()

        if series.empty:
            continue

        max_val = series.max()
        min_val = series.min()

        # tất cả bằng nhau → bỏ
        if max_val == min_val:
            continue

        # ===== xanh lá (max) =====
        for idx in df_display.index:
            val = df_calc.loc[idx, col_key]
            if pd.notna(val) and val == max_val:
                style.loc[idx, col_label] = "background-color:lightgreen"

        # ===== tính yếu =====
        threshold = int(max_val * 0.9)

        weak_candidates = df_calc[col_key][df_calc[col_key] < threshold]

        if not weak_candidates.empty:
            min_weak = weak_candidates.min()
            min_weak_count = (df_calc[col_key] == min_weak).sum()
            total = df_calc[col_key].count()

            # rule < 60%
            if total > 0 and (min_weak_count / total) < 0.6:

                for idx in df_display.index:
                    val = df_calc.loc[idx, col_key]

                    if pd.notna(val) and val == min_weak:
                        style.loc[idx, col_label] = "background-color:red;color:white"

    return style

styled = display_gear_df.style.apply(
    lambda x: highlight_gear_display(calc_df, display_gear_df),
    axis=None
)

st.dataframe(styled, use_container_width=True)

from streamlit import column_config

# ================= RANKING =================
st.subheader("🏆 Ranking")

if not gear_df.empty:

    # ===== DATA TÍNH =====
    calc_df = gear_df.copy()

    for col in calc_df.columns:
        if col != "character":
            calc_df[col] = pd.to_numeric(calc_df[col], errors="coerce")

    calc_df["gear_score"] = calc_df.apply(calc_gear_score, axis=1)

    # ===== DATA HIỂN THỊ =====
    display_df = calc_df.copy()

    for col in display_df.columns:
        if col != "character":
            display_df[col] = display_df[col].apply(
                lambda x: f"{int(x):,}" if pd.notna(x) else ""
            )

    # ===== HÀM THÊM ICON =====
    def add_rank_icon(df):
        df = df.reset_index(drop=True)
        icons = ["🥇", "🥈", "🥉"]

        df.insert(0, "Top", "")

        for i in range(min(3, len(df))):
            df.loc[i, "Top"] = icons[i]

        return df

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write("⚔️ Lực chiến")
        df_power = display_df.sort_values("luc_chien", ascending=False)[["character","luc_chien"]]
        st.dataframe(add_rank_icon(df_power), use_container_width=True)

    with col2:
        st.write("💥 DPS")
        df_dps = display_df.sort_values("dps", ascending=False)[["character","dps"]]
        st.dataframe(add_rank_icon(df_dps), use_container_width=True)

    with col3:
        st.write("🛡️ Gear Score")
        df_gear = display_df.sort_values("gear_score", ascending=False)[["character","gear_score"]]
        st.dataframe(add_rank_icon(df_gear), use_container_width=True)
