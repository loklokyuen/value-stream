import streamlit as st

st.set_page_config(layout="wide")
st.title("🔥 Trending Market Items — Gaps in Your Catalogue")

if "missed_trends" not in st.session_state:
    st.warning("Load the main dashboard first.")
    st.stop()

missed_trends = st.session_state["missed_trends"]

if not missed_trends:
    st.write("You have matching products for all current trending items.")
    st.stop()

for item in missed_trends[:15]:
    asin = item["asin"]
    title = item["title"]
    rank = item["current_rank"]

    # Rank history
    history = [
        item.get("rank_3_days_ago"),
        item.get("rank_2_days_ago"),
        item.get("rank_yesterday"),
        rank,
    ]
    history_str = " → ".join(str(r) for r in history if r is not None)

    # Daily change indicator
    try:
        change = int(item["daily_change"])
        if change >= 10:
            change_str = ":green[📈 **+{} — surging**]".format(change)
        elif change > 0:
            change_str = ":green[📈 +{}]".format(change)
        elif change < 0:
            change_str = ":red[📉 {}]".format(change)
        else:
            change_str = ":blue[— steady]"
    except (ValueError, TypeError):
        change_str = ":gray[—]"

    cols = st.columns([1, 3])

    with cols[0]:
        st.image(
            f"https://images-na.ssl-images-amazon.com/images/P/{asin}.01.LZZZZZZZ.jpg",
            width=150
        )

    with cols[1]:
        st.markdown(f"### {title}")
        st.caption(f"Amazon rank **#{rank}** {change_str} | {history_str}")
        st.link_button("View on Amazon 🔗", f"https://www.amazon.co.uk/dp/{asin}")

    st.markdown("---")