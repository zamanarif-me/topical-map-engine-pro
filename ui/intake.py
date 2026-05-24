"""Intake form — collects seed keyword + 8 intake answers."""

import streamlit as st
from models import (
    SeedInput, IntakeAnswers, GeoTargeting,
    BusinessFocus, SiteStage, GeoScope, ContentMix,
)
from ui.router import set_page, clear_run


STEPS = [
    "Seed Keyword",
    "Business Focus",
    "Audience & Services",
    "Geography",
    "Site Stage",
    "Positioning",
    "Focus Areas",
    "Content Mix",
]


def _step_dots(current: int):
    dots = ""
    for i in range(len(STEPS)):
        if i < current:
            cls = "done"
        elif i == current:
            cls = "active"
        else:
            cls = ""
        dots += f'<div class="step-dot {cls}"></div>'
    return f'<div class="step-indicator">{dots}</div>'


def render_intake():
    if "intake_step" not in st.session_state:
        st.session_state.intake_step = 0
    if "intake_data" not in st.session_state:
        st.session_state.intake_data = {}

    step = st.session_state.intake_step
    data = st.session_state.intake_data

    # Back to home
    if st.button("← Back", key="back_home"):
        set_page("home")
        st.rerun()

    st.markdown(f"### {STEPS[step]}")
    st.markdown(_step_dots(step), unsafe_allow_html=True)
    st.markdown(f"*Step {step + 1} of {len(STEPS)}*")
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Step 0: Seed keyword ──────────────────────────────────────────────────
    if step == 0:
        seed = st.text_input(
            "Enter your seed keyword",
            value=data.get("seed_keyword", ""),
            placeholder="e.g. WordPress website development and security service",
        )
        st.caption("The central topic your website will be authoritative about.")
        if st.button("Next →", disabled=not seed.strip()):
            data["seed_keyword"] = seed.strip()
            st.session_state.intake_step += 1
            st.rerun()

    # ── Step 1: Business focus ────────────────────────────────────────────────
    elif step == 1:
        options = {
            "Custom WordPress Development": BusinessFocus.CUSTOM_DEV,
            "WordPress Security Services": BusinessFocus.SECURITY,
            "Website Maintenance": BusinessFocus.MAINTENANCE,
            "Managed WordPress": BusinessFocus.MANAGED,
            "Agency for Businesses": BusinessFocus.AGENCY,
            "Personal Freelancer Brand": BusinessFocus.FREELANCER,
            "Enterprise WordPress": BusinessFocus.ENTERPRISE,
            "Other": BusinessFocus.OTHER,
        }
        selected = st.selectbox(
            "What best describes your business?",
            list(options.keys()),
            index=list(options.keys()).index(
                next((k for k, v in options.items() if v == data.get("business_focus")), list(options.keys())[0])
            )
        )
        detail = ""
        if selected == "Other":
            detail = st.text_input("Describe your business focus")

        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Prev"):
                st.session_state.intake_step -= 1
                st.rerun()
        with col2:
            if st.button("Next →"):
                data["business_focus"] = options[selected]
                data["business_focus_detail"] = detail
                st.session_state.intake_step += 1
                st.rerun()

    # ── Step 2: Audience & services ───────────────────────────────────────────
    elif step == 2:
        st.markdown("**Target Audience** *(select all that apply)*")
        audience_opts = ["local businesses", "e-commerce stores", "bloggers",
                         "startups", "enterprises", "agencies", "nonprofits",
                         "healthcare", "real estate", "restaurants"]
        audience = st.multiselect(
            "Who do you serve?",
            audience_opts,
            default=data.get("target_audience", []),
        )
        custom_audience = st.text_input(
            "Add custom audience (optional)",
            placeholder="e.g. SaaS companies",
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Revenue Services** *(what you get paid for)*")
        services = st.text_area(
            "List your main services (one per line)",
            value="\n".join(data.get("revenue_services", [])),
            placeholder="website builds\nspeed optimization\nsecurity audits",
            height=120,
        )

        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Prev"):
                st.session_state.intake_step -= 1
                st.rerun()
        with col2:
            full_audience = audience + ([custom_audience] if custom_audience.strip() else [])
            svcs = [s.strip() for s in services.split("\n") if s.strip()]
            if st.button("Next →", disabled=not full_audience or not svcs):
                data["target_audience"] = full_audience
                data["revenue_services"] = svcs
                st.session_state.intake_step += 1
                st.rerun()

    # ── Step 3: Geography ─────────────────────────────────────────────────────
    elif step == 3:
        scope_opts = {
            "Global": GeoScope.GLOBAL,
            "Country-specific": GeoScope.COUNTRY,
            "City / Local": GeoScope.LOCAL,
        }
        scope = st.selectbox(
            "Geographic targeting",
            list(scope_opts.keys()),
            index=list(scope_opts.keys()).index(
                next((k for k, v in scope_opts.items() if v == data.get("geo_scope")), "Country-specific")
            )
        )
        countries, cities = [], []
        if scope_opts[scope] == GeoScope.COUNTRY:
            countries_input = st.text_input(
                "Countries (comma separated)",
                value=", ".join(data.get("countries", [])),
                placeholder="USA, UK, Australia",
            )
            countries = [c.strip() for c in countries_input.split(",") if c.strip()]
        elif scope_opts[scope] == GeoScope.LOCAL:
            cities_input = st.text_input(
                "Cities (comma separated)",
                value=", ".join(data.get("cities", [])),
                placeholder="London, Manchester",
            )
            cities = [c.strip() for c in cities_input.split(",") if c.strip()]

        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Prev"):
                st.session_state.intake_step -= 1
                st.rerun()
        with col2:
            if st.button("Next →"):
                data["geo_scope"] = scope_opts[scope]
                data["countries"] = countries
                data["cities"] = cities
                st.session_state.intake_step += 1
                st.rerun()

    # ── Step 4: Site stage ────────────────────────────────────────────────────
    elif step == 4:
        stage_opts = {
            "Brand new site": SiteStage.BRAND_NEW,
            "Existing site with some blogs": SiteStage.HAS_BLOGS,
            "Established site with traffic": SiteStage.ESTABLISHED,
        }
        stage = st.radio(
            "Where are you now?",
            list(stage_opts.keys()),
            index=list(stage_opts.keys()).index(
                next((k for k, v in stage_opts.items() if v == data.get("site_stage")), "Brand new site")
            )
        )

        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Prev"):
                st.session_state.intake_step -= 1
                st.rerun()
        with col2:
            if st.button("Next →"):
                data["site_stage"] = stage_opts[stage]
                st.session_state.intake_step += 1
                st.rerun()

    # ── Step 5: Positioning ───────────────────────────────────────────────────
    elif step == 5:
        positioning_opts = [
            "seo_focused", "affordable", "enterprise_grade",
            "fast_turnaround", "local_seo_focused", "security_first",
            "performance_first", "design_focused", "full_service",
        ]
        positioning = st.multiselect(
            "How do you position yourself? (select 2-4)",
            positioning_opts,
            default=data.get("positioning", []),
        )

        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Prev"):
                st.session_state.intake_step -= 1
                st.rerun()
        with col2:
            if st.button("Next →", disabled=not positioning):
                data["positioning"] = positioning
                st.session_state.intake_step += 1
                st.rerun()

    # ── Step 6: Focus areas ───────────────────────────────────────────────────
    elif step == 6:
        focus = st.text_area(
            "Which 2-4 areas do you want to dominate first? (one per line)",
            value="\n".join(data.get("focus_areas", [])),
            placeholder="Elementor development\nPerformance optimization\nFirewall setup",
            height=120,
        )
        st.caption("These become your priority-1 pillars.")

        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Prev"):
                st.session_state.intake_step -= 1
                st.rerun()
        with col2:
            areas = [f.strip() for f in focus.split("\n") if f.strip()]
            if st.button("Next →", disabled=not areas):
                data["focus_areas"] = areas
                st.session_state.intake_step += 1
                st.rerun()

    # ── Step 7: Content mix ───────────────────────────────────────────────────
    elif step == 7:
        mix_opts = {
            "Mostly service pages": ContentMix.SERVICE_HEAVY,
            "Mostly informational blogs": ContentMix.BLOG_HEAVY,
            "Balanced authority site": ContentMix.BALANCED,
        }
        mix = st.radio(
            "What kind of site are you building?",
            list(mix_opts.keys()),
            index=list(mix_opts.keys()).index(
                next((k for k, v in mix_opts.items() if v == data.get("content_mix")), "Balanced authority site")
            )
        )

        # Settings
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        st.markdown("### Pipeline Settings")

        run_serp = st.toggle("Run SERP pull (Serper.dev)", value=True)
        st.caption("Collects PAA questions and related searches. Uses ~1 Serper call per pillar.")

        serp_geo = st.selectbox("SERP country", ["us", "gb", "au", "ca", "in"], index=0)

        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("← Prev"):
                st.session_state.intake_step -= 1
                st.rerun()
        with col2:
            if st.button("🚀  Generate Topical Map", type="primary", key="intake_generate_btn"):
                # Validate that every prior step actually saved its data.
                # If the user reloaded mid-intake, the form re-renders but
                # session_state.intake_data may be missing earlier answers.
                required_keys = [
                    "seed_keyword", "business_focus", "target_audience",
                    "revenue_services", "geo_scope", "site_stage",
                    "positioning", "focus_areas",
                ]
                missing = [k for k in required_keys if not data.get(k)]
                if missing:
                    st.error(
                        f"Some earlier steps were not saved: {', '.join(missing)}. "
                        f"Please go back through the steps with ← Prev and click Next on each."
                    )
                    st.stop()

                data["content_mix"] = mix_opts[mix]
                data["skip_serp"] = not run_serp
                data["serp_geo"] = serp_geo

                try:
                    seed_input = SeedInput(
                        seed_keyword=data["seed_keyword"],
                        intake=IntakeAnswers(
                            business_focus=data["business_focus"],
                            business_focus_detail=data.get("business_focus_detail"),
                            target_audience=data["target_audience"],
                            revenue_services=data["revenue_services"],
                            geo=GeoTargeting(
                                scope=data["geo_scope"],
                                countries=data.get("countries", []),
                                cities=data.get("cities", []),
                            ),
                            site_stage=data["site_stage"],
                            positioning=data["positioning"],
                            focus_areas=data["focus_areas"],
                            content_mix=data["content_mix"],
                        ),
                    )
                except Exception as e:
                    st.error(f"Could not build seed input: {e}")
                    with st.expander("Debug — intake_data snapshot"):
                        st.json(data)
                    st.stop()

                st.session_state.seed_input = seed_input
                st.session_state.pipeline_settings = {
                    "skip_serp": data["skip_serp"],
                    "serp_geo": data["serp_geo"],
                }
                # Fresh launch — no prior run id, force pipeline.py to mint one
                clear_run()
                st.session_state.pop("output", None)
                set_page("pipeline")
                st.rerun()
