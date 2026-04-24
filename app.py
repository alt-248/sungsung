import streamlit as st
import pandas as pd
from datetime import timezone, timedelta
from supabase import create_client

# ================= CONFIG =================
MAX_ENERGY = 840
MAX_NIGHTMARE = 14
UTC7 = timezone(timedelta(hours=7))

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= LOAD =================
def load_data():
    res = supabase.table("energy_tracker").select("*").execute()
    df = pd.DataFrame(res.data)

    if df.empty:
        st.error("❌ Không có dữ liệu trong Supabase")
        return pd.DataFrame()

    df["last_update"] = pd.to_datetime(df["last_update"], utc=True).dt.tz_convert(UTC7)
    return df

# ================= SAVE =================
def save_row(row):
    supabase.table("energy_tracker").update({
        "energy": int(row["energy"]),
        "nightmare": int(row["nightmare"]),
        "trial": int(row["trial"]),
        "last_update": row["last_update"].isoformat()
    }).eq("id", int(row["id"])).execute()

# ================= ENERGY =================
def get_block_time(dt):
    if dt.tzinfo is None:
        dt = dt.tz_localize(UTC7)
    else:
        dt = dt.tz_convert(UTC7)

    hour_block = (dt.hour // 3) * 3
    return dt.replace(hour=hour_block, minute=0, second=0, microsecond=0)

def update_energy(df):
    now = pd.Timestamp.now(tz=UTC7)
    now_block = get_block_time(now)

    for i in df.index:
        last = df.loc[i, "last_update"]

        diff_hours = int((now_block - last).total_seconds() // 3600)
        blocks = diff_hours // 3

        if blocks > 0:
            df.loc[i, "energy"] = min(df.loc[i, "energy"] + blocks * 15, MAX_ENERGY)
            df.loc[i, "last_update"] = last + pd.Timedelta(hours=blocks * 3)

    return df

# ================= INIT =================
if "df" not in st.session_state:
    st.session_state.df = load_data()

# ================= APP =================
st.title("⚡ Energy Tracker (Supabase)")

# update energy mỗi lần load
st.session_state.df = update_energy(st.session_state.df)

st.dataframe(st.session_state.df, use_container_width=True)

# ================= SELECT =================
idx = st.selectbox(
    "Character",
    st.session_state.df.index,
    format_func=lambda x: st.session_state.df.loc[x, "character"]
)

row = st.session_state.df.loc[idx]

energy = st.number_input("Energy", 0, MAX_ENERGY, int(row["energy"]))
nightmare = st.number_input("Nightmare", 0, MAX_NIGHTMARE, int(row["nightmare"]))
trial = st.number_input("Trial", 0, 10, int(row["trial"]))

# ================= SAVE =================
if st.button("💾 Save"):
    st.session_state.df.loc[idx, "energy"] = energy
    st.session_state.df.loc[idx, "nightmare"] = nightmare
    st.session_state.df.loc[idx, "trial"] = trial

    save_row(st.session_state.df.loc[idx])

    st.success("✅ Saved to Supabase!")
    st.rerun()

# ================= GLOBAL =================
st.subheader("🔧 Toàn server")

if st.button("🔁 Reset Trial = 3"):
    st.session_state.df["trial"] = 3
    for i in st.session_state.df.index:
        save_row(st.session_state.df.loc[i])
    st.rerun()

if st.button("⚔️ +2 Nightmare"):
    st.session_state.df["nightmare"] = (
        st.session_state.df["nightmare"] + 2
    ).clip(upper=MAX_NIGHTMARE)

    for i in st.session_state.df.index:
        save_row(st.session_state.df.loc[i])

    st.rerun()

# ================= ENERGY =================
if st.button("⚡ Update Energy Now"):
    st.session_state.df = update_energy(st.session_state.df)

    for i in st.session_state.df.index:
        save_row(st.session_state.df.loc[i])

    st.rerun()
