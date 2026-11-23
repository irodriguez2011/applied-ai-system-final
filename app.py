from pathlib import Path

import streamlit as st

from src.agent import RecommenderAgent
from src.catalog import SongCatalog
from src.main import BASELINE_PROFILE, build_llm
from src.recommender import load_songs, recommend_songs
from src.tools import Toolbox
from src.trace import TraceLogger
from src.user_io import ScriptedIO


ROOT = Path(__file__).resolve().parent
SONGS_CSV = ROOT / "data" / "songs.csv"


st.set_page_config(page_title="VibeMatch 2.0", page_icon="🎵", layout="centered")
st.title("🎵 VibeMatch 2.0")
st.write("Describe your mood and get five song recommendations.")

mode = st.radio("Mode", ["AI agent", "Baseline"], horizontal=True)
request = st.text_area(
    "What are you in the mood for?",
    value="something chill to study to",
)

if st.button("Find songs", type="primary"):
    if not request.strip():
        st.warning("Enter a music request first.")
    elif mode == "Baseline":
        songs = load_songs(str(SONGS_CSV))
        picks = recommend_songs(BASELINE_PROFILE, songs, k=5)
        st.subheader("Top 5 recommendations")
        for rank, (song, score, explanation) in enumerate(picks, start=1):
            st.markdown(f"**{rank}. {song['title']} — {song['artist']}**")
            st.caption(f"{song['genre']} · {song['mood']} · Score: {score:.2f}/100")
            st.write(explanation)
    else:
        catalog = SongCatalog.from_csv(str(SONGS_CSV))
        agent = RecommenderAgent(
            build_llm(),
            Toolbox(catalog, ScriptedIO()),
            TraceLogger(),
        )
        with st.spinner("Finding your vibe..."):
            result = agent.run(request.strip())

        if result.message:
            st.info(result.message)
        if result.used_fallback:
            st.warning(result.fallback_reason)

        st.subheader("Top 5 recommendations")
        for rank, (song, score, explanation) in enumerate(result.picks, start=1):
            st.markdown(f"**{rank}. {song['title']} — {song['artist']}**")
            st.caption(f"{song['genre']} · {song['mood']} · Score: {score:.2f}/100")
            st.write(explanation)

        st.caption(
            f"Confidence: {result.confidence} · Agent steps: {result.steps}"
        )
        if result.trace_path:
            st.caption(f"Trace log: {result.trace_path}")
