"""Pipeline page — runs the engine and shows live progress."""

import sys
import io
import os
import streamlit as st


def render_pipeline():
    st.markdown("## 🔄 Generating Topical Map")

    seed = st.session_state.get("seed_input")
    settings = st.session_state.get("pipeline_settings", {})

    if not seed:
        st.error("No seed input found. Please start from the intake form.")
        if st.button("← Back to form"):
            st.session_state.page = "intake"
            st.rerun()
        return

    st.markdown(f"**Seed:** `{seed.seed_keyword}`")
    st.markdown(f"**Business:** {seed.intake.business_focus.value} | "
                f"**Geo:** {seed.intake.geo.scope.value} | "
                f"**SERP:** {'Enabled' if not settings.get('skip_serp') else 'Skipped'}")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # Check API keys
    missing_keys = []
    for key in ["ANTHROPIC_API_KEY", "SERPER_API_KEY"]:
        if not os.environ.get(key):
            missing_keys.append(key)

    if missing_keys:
        st.error(f"Missing API keys: {', '.join(missing_keys)}")
        st.info("Set them in your environment or in a `.env` file before running.")

        with st.expander("How to set API keys"):
            st.code("""
# In your terminal before running streamlit:
export ANTHROPIC_API_KEY=sk-ant-...
export SERPER_API_KEY=...
export GEMINI_API_KEY=...

# Or create a .env file in the project root:
ANTHROPIC_API_KEY=sk-ant-...
SERPER_API_KEY=...
GEMINI_API_KEY=...
            """)
        if st.button("← Back to form"):
            st.session_state.page = "intake"
            st.rerun()
        return

    # Progress UI
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.empty()
    logs = []

    def update_log(msg: str, progress: float = None):
        logs.append(msg)
        log_html = "<div class='log-box'>" + "<br>".join(
            f"<span style='color:{'#43e97b' if '[pipeline]' in l else '#6b6b8a'}'>{l}</span>"
            for l in logs[-20:]
        ) + "</div>"
        log_container.markdown(log_html, unsafe_allow_html=True)
        if progress is not None:
            progress_bar.progress(progress)
        status_text.markdown(f"*{msg}*")

    # Run pipeline
    if not st.session_state.get("output"):
        update_log("[pipeline] Starting...", 0.05)

        # Monkey-patch print to capture pipeline logs
        original_print = print
        captured = []

        def capture_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            captured.append(msg)
            update_log(msg)
            original_print(*args, **kwargs)

        import builtins
        builtins.print = capture_print

        try:
            # Load dotenv if available
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except ImportError:
                pass

            from pipeline import run_pipeline
            import tempfile, pathlib

            output_dir = pathlib.Path("streamlit_output") / seed.seed_keyword[:30].replace(" ", "_")

            update_log("[pipeline] Stage 2: Extracting central entity...", 0.15)
            output = run_pipeline(
                seed=seed,
                output_dir=output_dir,
                skip_serp=settings.get("skip_serp", False),
                skip_validation=False,
                serp_geo=settings.get("serp_geo", "us"),
                serp_lang="en",
            )
            st.session_state.output = output
            # Use session directory if auto-saved
            session_id = getattr(output, "_session_id", None)
            if session_id:
                from ui.session_manager import get_session_output_dir
                st.session_state.output_dir = get_session_output_dir(session_id)
            else:
                st.session_state.output_dir = str(output_dir)
            progress_bar.progress(1.0)
            status_text.markdown("✅ **Pipeline complete!**")

        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            import traceback
            st.code(traceback.format_exc())
            return
        finally:
            builtins.print = original_print

    else:
        progress_bar.progress(1.0)
        status_text.markdown("✅ **Results already available.**")
        update_log("[pipeline] Using cached output from this session.", 1.0)

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊  View Results", use_container_width=True):
            st.session_state.page = "results"
            st.rerun()
    with col2:
        if st.button("← Run Again", use_container_width=True):
            st.session_state.output = None
            st.session_state.page = "intake"
            st.rerun()
