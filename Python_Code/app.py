"""Launch with: python -m streamlit run app.py"""
from dataclasses import replace
import io
import json
import zipfile
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from thermal_model import Parameters, solve, MESHES, mesh_comparison, PAPER_DOI, conductivity_values
from figures import (map_figure, profiles_figure, surface_figure, field_dataframe,
                     html_report, solution_npz, style, CONFIG, ORANGE, TEAL)

st.set_page_config(page_title="Ga₂O₃ | Thermal Lab", page_icon="🌡️", layout="wide")
st.markdown('''<style>
/* High-contrast light theme.  Keep Streamlit widgets readable even when the
   browser/OS reports a dark preferred color scheme. */
:root{
  --ink:#172b45;
  --muted:#50677f;
  --soft:#6a7f94;
  --panel:#ffffff;
  --page:#eef3f7;
  --line:#dbe5ed;
  --accent:#e54850;
}
.stApp{background:var(--page);color:var(--ink)}
.block-container{padding-top:2rem;max-width:1550px}

/* Core text */
.stApp p,.stApp li,.stApp label,.stApp .stMarkdown,.stApp [data-testid="stCaptionContainer"]{color:var(--ink)}
.stApp small,.stApp [data-testid="stCaptionContainer"] p{color:var(--muted)!important}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6{color:var(--ink)}

/* Sidebar */
[data-testid="stSidebar"]{background:#f9fbfd;border-right:1px solid #dce5ed}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span{color:var(--ink)}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{color:var(--muted)!important}

/* Metrics */
[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:12px;padding:18px 20px}
[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] *{color:var(--muted)!important;font-size:13px}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{color:var(--ink)!important;font-size:30px}
[data-testid="stMetricDelta"],[data-testid="stMetricDelta"] *{color:#52677d!important}
[data-testid="stMetricDelta"]{background:#edf1f5;border-radius:999px;padding:2px 7px;width:max-content}
[data-testid="stMetricDelta"] svg{display:none}

/* Alerts: explicitly control foreground and background instead of inheriting
   Streamlit/theme colors that can become low-contrast. */
div[data-testid="stAlert"]{border-radius:10px}
div[data-testid="stAlert"] p,div[data-testid="stAlert"] span,div[data-testid="stAlert"] div{color:inherit}
div[data-testid="stAlert"][data-baseweb="notification"]{color:var(--ink)}
.stAlert{color:var(--ink)}
[data-testid="stNotificationContentInfo"],div[role="alert"]:has(svg[data-testid="stIconInfo"]){background:#dceeff!important;color:#174f78!important;border-color:#a9cfea!important}
[data-testid="stNotificationContentWarning"],div[role="alert"]:has(svg[data-testid="stIconWarning"]){background:#fff3c4!important;color:#624900!important;border-color:#e1c15c!important}
/* Fallbacks for Streamlit versions without the specific notification test IDs. */
div[data-testid="stAlert"]:has([data-testid="stMarkdownContainer"]){color:var(--ink)}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:22px;margin-top:10px}
.stTabs [data-baseweb="tab"]{font-weight:600;color:#526b84!important}
.stTabs [data-baseweb="tab"] p,.stTabs [data-baseweb="tab"] span{color:inherit!important}
.stTabs [data-baseweb="tab"][aria-selected="true"]{color:#d93f47!important}

/* Inputs and option labels */
[data-testid="stRadio"] label,[data-testid="stCheckbox"] label,[data-testid="stSelectbox"] label,[data-testid="stNumberInput"] label,[data-testid="stSlider"] label{color:#31485f!important}
[data-testid="stRadio"] label p,[data-testid="stCheckbox"] label p{color:#31485f!important}
[data-baseweb="radio"]+div,[data-baseweb="checkbox"]+div{color:#31485f!important}

/* Hero remains intentionally dark. */
.hero{background:#12273e;border-bottom:4px solid #16a3ad;border-radius:14px;padding:27px 33px;margin-bottom:22px;color:white}
.hero small{color:#87d9df!important;font-weight:700;letter-spacing:2px;font-size:11px}
.hero h1{font-size:38px;letter-spacing:-1.4px;padding:10px 0;color:white!important}
.hero p{color:#d6e0ea!important;margin:0;line-height:1.65;font-size:15px}
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=40)
def cached_solve(p):
    return solve(p)


@st.cache_data(show_spinner=False, max_entries=8)
def cached_refinement(p):
    return mesh_comparison(p)


with st.sidebar:
    st.markdown("### Simulation controls")
    st.caption("Change the physical inputs, then run the model. Display controls update immediately.")
    with st.form("physical_inputs"):
        power = st.slider("Power density (W/cm²)", 0, 1500, 1500, 25)
        a_thick = st.number_input("Substrate A (μm)", 20., 1000., 630., 10.)
        b_thick = st.number_input("Substrate B (μm)", 20., 1000., 50., 10.)
        law_label = st.selectbox("Thermal conductivity", ["k(T) · Table I",
                   "k(300 K) · Table I", "Constant isotropic k"])
        mesh_label = st.select_slider("Mesh resolution", list(MESHES), value="Standard")
        with st.expander("Geometry and boundary conditions"):
            geom_label = st.selectbox("2D formulation", ["Axisymmetric r–z (circular diode)", "Planar x–z (symmetric strip)"])
            axis_label = st.selectbox("Lateral conductivity", ["Effective √(k[100] k[010])", "[100]", "[010]"])
            radius = st.number_input("Contact radius / half-width (μm)", 25., 1500., 500., 25.)
            extent = st.number_input("Outer radius / half-width (μm)", 50., 3000., 1000., 50.)
            drift = st.number_input("Drift-layer depth (μm)", 1., 50., 10., 1.)
            sink = st.number_input("Bottom sink (K)", 200., 500., 300., 1.)
            ambient = st.number_input("Ambient air (K)", 200., 500., 300., 1.)
            h = st.number_input("Top convection h (W/m²/K)", 0., 1000., 10., 5.)
            kconst = st.number_input("k for constant mode (W/m/K)", 1., 500., 14., 1.)
        submitted = st.form_submit_button("Run simulation", type="primary", width="stretch")
    st.caption("Local Python computation · no API keys, paid software, or browser plugins.")
    st.markdown(f"[Read the source paper]({PAPER_DOI})")

nx,nz,nd = MESHES[mesh_label]
law={"k(T) · Table I":"temperature", "k(300 K) · Table I":"frozen",
     "Constant isotropic k":"constant"}[law_label]
base=Parameters(substrate_um=a_thick,drift_um=drift,contact_radius_um=radius,domain_radius_um=extent,
    power_w_cm2=power,sink_k=sink,ambient_k=ambient,h_w_m2k=h,
    geometry="axisymmetric" if geom_label.startswith("Axisymmetric") else "planar",
    lateral_axis={"Effective √(k[100] k[010])":"effective","[100]":"100","[010]":"010"}[axis_label],
    conductivity=law,constant_k=kconst,nx=nx,nz_substrate=nz,nz_drift=nd)

st.markdown('''<div class="hero"><small>SEMICONDUCTOR HEAT TRANSFER · FIGURE 3 STUDY</small>
<h1>Ga₂O₃ Thermal Lab</h1><p>Follow the heat from the diode junction to the sink.<br>
An interactive Python reconstruction of substrate thinning, with transparent physical assumptions.</p></div>''',unsafe_allow_html=True)

try:
    with st.spinner("Solving the two steady temperature fields…"):
        solutions=[cached_solve(base), cached_solve(replace(base,substrate_um=b_thick))]
except (ValueError, RuntimeError) as e:
    st.error(str(e))
    st.info("Adjust the physical inputs and run again. Failed or unconverged fields are not displayed.")
    st.stop()

a,b=solutions
rise_a=a.temperature_k.max()-base.sink_k
rise_b=b.temperature_k.max()-base.sink_k
reduction=100*(1-rise_b/rise_a) if rise_a>1e-9 else None
c=st.columns(4)
c[0].metric(f"A · {a_thick:g} μm model peak",f"{a.peak_c:.1f} °C",f"{rise_a:.1f} K above sink",delta_color="off")
c[1].metric(f"B · {b_thick:g} μm model peak",f"{b.peak_c:.1f} °C",f"{rise_b:.1f} K above sink",delta_color="off")
c[2].metric("Rise reduction A → B",f"{reduction:.1f}%" if reduction is not None else "—", "ΔT relative to sink",delta_color="off")
c[3].metric("Generated heat · each case",f"{a.source_w.sum():.3f} {a.power_unit}",f"{power:,} W/cm²",delta_color="off")

st.info("Paper reference: 155 °C (630 μm) and 55 °C (50 μm), at 1500 W/cm². "
        "This thermal-only model uses an assumed uniform heat source and does not reproduce the authors’ full TCAD solution.")
if max(s.temperature_k.max() for s in solutions)>600 and law=="temperature":
    st.warning("The k(T) model reaches high temperatures. These outputs extrapolate the paper’s conductivity formulas under the stated assumptions; "
               "they are not validated device operating temperatures. Compare with the fixed-at-300-K option and the model notes.")

field_tab, profile_tab, sweep_tab, method_tab = st.tabs(["Temperature maps", "Profiles & 3D", "Parameter study", "Model & verification"])

with field_tab:
    controls=st.columns([1.4,1,1,1,1])
    colorscale=controls[0].selectbox("Palette",["Inferno","Cividis","Viridis","Turbo"],help="Inferno, Cividis, and Viridis give ordered colour scales. Turbo resembles traditional thermal maps.")
    shared=controls[1].checkbox("Shared colors",value=True,help="The same color means the same temperature in both panels.")
    zoom=controls[2].checkbox("Zoom each depth",value=True,help="Turn off to compare both wafers on the same depth range.")
    contours=controls[3].checkbox("Contour lines",value=True)
    units=controls[4].selectbox("Temperature unit",["°C","K"])
    true_aspect=st.checkbox("Equal physical x and z scale",value=False,
                            help="Shows true geometry; the 50 μm substrate becomes a thin strip.")
    st.caption("Gold line: contact footprint · cyan dotted: drift/substrate interface · teal line: fixed-temperature sink · white ×: hottest computed cell. "
               "Hover reads cells; contour lines interpolate between them. Display precision is not experimental accuracy.")
    chart=map_figure(solutions,colorscale,shared,zoom,contours,"C" if units=="°C" else "K",true_aspect=true_aspect)
    st.plotly_chart(chart,config=CONFIG,theme=None,width="stretch",key="map_chart")
    if zoom:
        st.caption("Each panel has its own depth range. Substrate thickness excludes the 10 μm drift layer (or your selected drift-layer depth).")
    st.markdown("#### Coordinate inspector")
    pcols=st.columns([1,1.2,1.2])
    which=pcols[0].selectbox("Inspect case",["A","B"])
    s=solutions[0 if which=="A" else 1]
    xp=pcols[1].number_input("Requested x/r (μm)",0.,float(base.domain_radius_um),0.,1.)
    zp=pcols[2].number_input("Requested depth (μm)",0.,float(s.parameters.substrate_um+base.drift_um),0.,1.,key=f"probe_depth_{which}_{s.parameters.substrate_um}_{base.drift_um}")
    if abs(zp-s.parameters.substrate_um-base.drift_um)<1e-9:
        st.success(f"Bottom boundary: T = {base.sink_k:.3f} K = {base.sink_k-273.15:.3f} °C (exact imposed condition).")
    else:
        i=int(np.argmin(np.abs(s.x_um-xp)));j=int(np.argmin(np.abs(s.z_um-zp)))
        kx,kz=conductivity_values(s.temperature_k,base)
        st.dataframe(pd.DataFrame([{"Cell x/r (μm)":s.x_um[i],"Cell depth (μm)":s.z_um[j],
            "T (°C)":s.temperature_c[j,i],"T (K)":s.temperature_k[j,i],
            "k lateral (W/m/K)":kx[j,i],"k [001] (W/m/K)":kz[j,i],
            "Layer":"drift" if s.z_um[j]<base.drift_um else "substrate"}]),hide_index=True,width="stretch")
        st.caption("Nearest computed cell shown; coordinates are reported explicitly. No hidden interpolation or false extra spatial resolution.")
    with st.expander("Download these results"):
        st.caption("The HTML preserves hover, zoom, and display buttons offline. New physical settings require this Python app. Raw data contain all cells.")
        if st.button("Prepare download files"):
            with st.spinner("Packaging figures and numerical data…"):
                fields=io.BytesIO()
                with zipfile.ZipFile(fields,"w",zipfile.ZIP_DEFLATED) as z:
                    for i,s in enumerate(solutions):
                        z.writestr(f"case_{i+1}_{s.parameters.substrate_um:g}um.csv",field_dataframe(s).to_csv(index=False,float_format="%.10g"))
                    z.writestr("metadata.json",json.dumps([s.summary() for s in solutions],indent=2))
                st.session_state["exports"]=(base,b_thick,html_report(solutions,colorscale),fields.getvalue(),solution_npz(solutions))
        export=st.session_state.get("exports")
        if export and export[:2]==(base,b_thick):
            dl=st.columns(3)
            dl[0].download_button("Interactive HTML",export[2],"Ga2O3_Interactive_Report.html","text/html",on_click="ignore")
            dl[1].download_button("Full-resolution CSV + metadata",export[3],"Ga2O3_Data.zip","application/zip",on_click="ignore")
            dl[2].download_button("NumPy arrays (.npz)",export[4],"Ga2O3_Fields.npz","application/octet-stream",on_click="ignore")

with profile_tab:
    st.plotly_chart(profiles_figure(solutions),config=CONFIG,theme=None,width="stretch")
    st.caption(f"Near-surface samples are at z = {a.z_um[0]:.3g} μm. Centreline samples are in the first lateral cell. The final point is the exact sink boundary.")
    st.markdown("#### Rotate the temperature surface")
    surface_case=st.radio("3D surface case",["A","B"],horizontal=True)
    st.caption("The vertical dimension below is temperature, not device height. Drag to rotate and scroll to zoom.")
    st.plotly_chart(surface_figure(solutions[0 if surface_case=="A" else 1]),config=CONFIG,theme=None,width="stretch")

with sweep_tab:
    st.markdown("#### Change one input and track the peak")
    mode=st.radio("Sweep variable",["Substrate thickness","Power density"],horizontal=True)
    st.caption("Sweeps use the Quick mesh and the other current physical settings. They show model sensitivity; use mesh refinement for final reported values.")
    if st.button("Run parameter study",type="primary"):
        rows=[]
        values=[50.,100.,150.,200.,350.,630.] if mode=="Substrate thickness" else [0.,250.,500.,750.,1000.,1250.,1500.]
        nxq,nzq,ndq=MESHES["Quick"]
        progress=st.progress(0)
        for i,value in enumerate(values):
            p=replace(base,nx=nxq,nz_substrate=nzq,nz_drift=ndq,
                **({"substrate_um":value} if mode=="Substrate thickness" else {"power_w_cm2":value}))
            try:
                ss=cached_solve(p)
                rows.append({"Input":value,"Peak (°C)":ss.peak_c,"Rise (K)":ss.temperature_k.max()-p.sink_k,"Status":"converged"})
            except RuntimeError as e:
                rows.append({"Input":value,"Peak (°C)":np.nan,"Rise (K)":np.nan,"Status":str(e)})
            progress.progress((i+1)/len(values))
        st.session_state["sweep"]=(base,mode,rows)
    sweep=st.session_state.get("sweep")
    if sweep and sweep[:2]==(base,mode):
        df=pd.DataFrame(sweep[2]);xlabel="Substrate thickness (μm)" if mode=="Substrate thickness" else "Power density (W/cm²)"
        fig=go.Figure(go.Scatter(x=df["Input"].tolist(),y=df["Peak (°C)"].tolist(),mode="lines+markers",
            line=dict(color=TEAL,width=3),marker=dict(size=9),connectgaps=False,
            hovertemplate=xlabel+" = %{x:g}<br>Peak = %{y:.3f} °C<extra></extra>"))
        style(fig,420);fig.update_layout(xaxis_title=xlabel,yaxis_title="Model peak (°C)")
        st.plotly_chart(fig,config=CONFIG,theme=None,width="stretch")
        st.dataframe(df.rename(columns={"Input":xlabel}),hide_index=True,width="stretch")
        st.download_button("Download sweep CSV",df.rename(columns={"Input":xlabel}).to_csv(index=False),"Ga2O3_Parameter_Study.csv","text/csv",on_click="ignore")

with method_tab:
    st.markdown("#### What is solved")
    st.latex(r"\frac{1}{r}\frac{\partial}{\partial r}\left(r k_r(T)\frac{\partial T}{\partial r}\right)+\frac{\partial}{\partial z}\left(k_{001}(T)\frac{\partial T}{\partial z}\right)+Q=0")
    st.write("The equation shown is the axisymmetric formulation. The planar option replaces the radial term with ∂/∂x(kₓ ∂T/∂x). "
             "A cell-centred finite-volume discretization conserves heat across each internal face. SciPy solves the sparse system; "
             "relaxed Picard iteration handles k(T). Heat capacity is unnecessary for this steady-state calculation.")
    st.markdown("#### Inputs and provenance")
    st.dataframe(pd.DataFrame([
        ["Substrates", "630 and 50 μm", "Paper, Figure 1 / Figure 3"],
        ["Drift layer", "10 μm", "Paper, Experimental / Figure 1"],
        ["Contact diameter", "1 mm", "Paper, Figure 3 discussion"],
        ["Heat generation", "Q = q″/d under contact, zero elsewhere", "Our thermal-source approximation"],
        ["Outer radius", "1000 μm", "Our domain assumption; adjustable"],
        ["Lateral boundaries", "Zero flux at centre and outer edge", "Symmetry / closed-cell approximation"],
        ["Top / bottom", "h = 10 W/m²/K; T∞ = Tsink = 300 K", "Paper, Table I and boundary paragraph"],
        ["Conductivity", "Table I; T in kelvin", "Radial effective k is our approximation"],
        ["Contacts / packaging", "Collapsed; no contact or package resistance", "Ideal thermal model"]],
        columns=["Quantity","Default / treatment","Source"]),hide_index=True,width="stretch")
    st.markdown("#### Solver diagnostics")
    diag=[]
    for s in solutions:
        d=s.summary()
        diag.append({"Substrate (μm)":d["substrate_um"],"Cells":d["cells"],"Iterations":d["iterations"],
            "Relative energy imbalance":d["energy_balance_relative"],"Relative residual":d["nonlinear_residual_relative"],
            "Last update (K)":d["last_update_K"],f"Heat to sink ({s.power_unit})":d["bottom_heat"],f"Heat to air ({s.power_unit})":d["top_heat"]})
    st.dataframe(pd.DataFrame(diag),hide_index=True,width="stretch")
    st.caption("Energy imbalance = |generated − bottom − top| / energy scale. For a planar section, heat is per metre of depth for the modeled symmetric half.")
    if st.button("Check mesh refinement for both cases"):
        with st.spinner("Solving Quick, Standard, and Fine grids…"):
            st.session_state["mesh_checks"]=(base,b_thick,[(s.parameters.substrate_um,cached_refinement(s.parameters)) for s in solutions])
    checks=st.session_state.get("mesh_checks")
    if checks and checks[:2]==(base,b_thick):
        for thick,rows in checks[2]:
            st.write(f"Substrate: {thick:g} μm")
            st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
    with st.expander("Why the model differs from Figure 3",expanded=True):
        st.write("The original work solves coupled electrical and thermal equations in Silvaco TCAD. It does not provide its deck, mesh, spatial Joule heating, "
            "or a fully specified implementation of its ‘recurrent’ side boundaries. A 2D axisymmetric approximation also cannot exactly represent unequal in-plane crystal conductivities. "
            "The source-area normalization, outer domain, and heat path strongly affect temperatures. We therefore report the computed fields and the paper's peaks separately; "
            "the reference temperatures are never inserted into the solution.")
        st.write("Figure 1 labels 100 nm contacts, whereas the fabrication prose lists micrometre metal thicknesses. It depicts a brass sink while Table I lists copper. "
            "This model follows the stated ideal 300 K wafer-bottom boundary and omits explicit metal and sink layers. It does not resolve these ambiguities by inventing material data.")
    st.markdown(f"Source: Chiang et al. (2024), *ECS J. Solid State Sci. Technol.*, **13**, 115001. [DOI]({PAPER_DOI}). "
                "See MODEL_NOTES.md and VALIDATION.md in the project for the derivation and checks.")
