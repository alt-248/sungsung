import streamlit as st
import pandas as pd
from datetime import timezone, timedelta

# ================= CONFIG =================
FILE_PATH = "data_character.csv"
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

# ================= INIT =================
def init_data():
    return pd.DataFrame({
        "character": [
            "Buff", "Thương", "Kiếm khiên", "Đại kiếm",
            "Cung", "Sách", "Sát thủ", "Cầu"
        ],
        "nightmare": [0]*8,
        "trial": [0]*8,
        "energy": [0]*8,
        "last_update": [pd.Timestamp.now(tz=UTC7)]*8
    })

# ================= LOAD / SAVE =================
def load_data():
    try:
        df = pd.read_csv(FILE_PATH)
        df["last_update"] = pd.to_datetime(df["last_update"], errors="coerce")
    except:
        df = init_data()
    return df

def save_data(df):
    df.to_csv(FILE_PATH, index=False)

# ================= TIME BLOCK =================
def get_block_time(dt):
    if dt.tzinfo is None:
        dt = dt.tz_localize(UTC7)
    else:
        dt = dt.tz_convert(UTC7)

    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

# ================= ENERGY UPDATE =================
def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = pd.to_datetime(df.loc[i, "last_update"], errors="coerce")

        if pd.isna(last):
            df.loc[i, "last_update"] = now_block
            continue

        if last.tzinfo is None:
            last = last.tz_localize(UTC7)
        else:
            last = last.tz_convert(UTC7)

        diff_hours = int((now_block - last).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(df.loc[i, "energy"] + blocks * 15, MAX_ENERGY)
            df.loc[i, "last_update"] = last + pd.Timedelta(hours=blocks * 3)

    return df

# ================= CHECK ALERT =================
def check_alert(df):
    full_energy = df[df["energy"] >= MAX_ENERGY]["character"].tolist()
    full_nightmare = df[df["nightmare"] >= MAX_NIGHTMARE]["character"].tolist()
    return full_energy, full_nightmare

# ================= UI =================
st.set_page_config(page_title="Energy Tracker PRO", layout="wide")
st.title("⚡ Energy Tracker PRO (UTC+7)")

df = load_data()
df = update_energy(df)
save_data(df)

# ================= ALERT =================
full_energy, full_nightmare = check_alert(df)

if full_energy or full_nightmare:
    st.warning("⚠️ Cảnh báo trạng thái đầy!")

if full_energy:
    st.error(f"🔥 Full Energy: {', '.join(full_energy)}")

if full_nightmare:
    st.error(f"💀 Full Nightmare: {', '.join(full_nightmare)}")
    
# ================= HIGHLIGHT =================
def highlight_status(df):
    def color_energy(val):
        if val >= MAX_ENERGY:
            return "background-color: red; color: white"
        elif val >= MAX_ENERGY * 0.8:
            return "background-color: yellow"
        return ""

    def color_nightmare(val):
        if val >= MAX_NIGHTMARE:
            return "background-color: red; color: white"
        elif val >= MAX_NIGHTMARE * 0.8:
            return "background-color: yellow"
        return ""

    style = pd.DataFrame("", index=df.index, columns=df.columns)

    style["energy"] = df["energy"].apply(color_energy)
    style["nightmare"] = df["nightmare"].apply(color_nightmare)

    return style
    
# ================= TABLE =================
st.subheader("📊 Bảng dữ liệu")

styled_df = df.style.apply(lambda x: highlight_status(df), axis=None)

st.dataframe(styled_df, use_container_width=True)

# ================= SELECT CHARACTER =================
st.subheader("🎮 Chọn nhân vật")

idx = st.selectbox(
    "Character",
    df.index,
    format_func=lambda x: df.loc[x, "character"]
)

# ================= MULTI UPDATE =================
st.subheader("✏️ Cập nhật theo ý muốn")

col1, col2, col3 = st.columns(3)

with col1:
    use_energy = st.checkbox("Energy")
    energy_val = st.number_input("Giá trị Energy", 0, MAX_ENERGY, 0, disabled=not use_energy)

with col2:
    use_nightmare = st.checkbox("Nightmare")
    nightmare_val = st.number_input("Giá trị Nightmare", 0, MAX_NIGHTMARE, 0, disabled=not use_nightmare)

with col3:
    use_trial = st.checkbox("Trial")
    trial_val = st.number_input("Giá trị Trial", 0, 10, 0, disabled=not use_trial)

if st.button("💾 Cập nhật"):
    if use_energy:
        df.loc[idx, "energy"] = min(energy_val, MAX_ENERGY)

    if use_nightmare:
        df.loc[idx, "nightmare"] = min(nightmare_val, MAX_NIGHTMARE)

    if use_trial:
        df.loc[idx, "trial"] = trial_val

    save_data(df)
    st.success("Đã cập nhật!")
    st.rerun()

# ================= GLOBAL ACTIONS =================
st.subheader("🔧 Toàn server")

c1, c2 = st.columns(2)

with c1:
    if st.button("🔁 Reset Trial = 3 (All)"):
        df["trial"] = 3
        save_data(df)
        st.success("Reset trial xong!")
        st.rerun()

with c2:
    if st.button("⚔️ +2 Nightmare (All)"):
        df["nightmare"] = (df["nightmare"] + 2).clip(upper=MAX_NIGHTMARE)
        save_data(df)
        st.success("Nightmare +2 xong!")
        st.rerun()

# ================= ENERGY MANUAL UPDATE =================
st.subheader("⚡ Energy System")

if st.button("Update Energy Now"):
    df = update_energy(df)
    save_data(df)
    st.success("Đã update energy!")
    st.rerun()
