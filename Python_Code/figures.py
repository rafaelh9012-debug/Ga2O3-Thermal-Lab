"""Plotly charts, full-resolution CSV, and a self-contained HTML report."""
import io
import json
from html import escape
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.colors import get_colorscale
from thermal_model import conductivity_values, PAPER_DOI

INK = "#172B45"
MUTED = "#5A6F85"
ORANGE = "#DE7147"
TEAL = "#148D98"
CONFIG = {"displaylogo": False, "responsive": True, "scrollZoom": True,
          "toImageButtonOptions": {"format": "png", "filename": "Ga2O3_temperature_field",
                                   "width": 1800, "height": 950, "scale": 2}}


def scientific_palette(name):
    """Keep scientific colors literal: Streamlit reserves hex #000004, etc.

    Inferno's real near-black endpoint happens to equal a theme placeholder.
    Expressing the same colors as RGB prevents unintended frontend substitution.
    """
    out=[]
    for position,color in get_colorscale(name):
        if color.startswith("#") and len(color)==7:
            color="rgb({},{},{})".format(*(int(color[i:i+2],16) for i in (1,3,5)))
        out.append([position,color])
    return out


def style(fig, height=510):
    fig.update_layout(template="plotly_white", height=height,
                      font=dict(family="Arial, sans-serif", color=INK, size=13),
                      paper_bgcolor="white", plot_bgcolor="#F4F7FA",
                      margin=dict(l=64, r=54, t=75, b=62),
                      hoverlabel=dict(bgcolor=INK, font_color="white", font_size=13),
                      legend=dict(orientation="h", y=1.13, x=0),
                      modebar=dict(color=MUTED, activecolor=TEAL),
                      uirevision="preserve_view")
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="#BECAD6")
    fig.update_yaxes(showgrid=False, zeroline=False, linecolor="#BECAD6")
    return fig


def map_figure(solutions, colorscale="Inferno", shared=True, zoom_layers=True,
               contours=True, units="C", probe=None, true_aspect=False):
    scale=scientific_palette(colorscale)
    labels = [f"{'A' if i == 0 else 'B'} · {s.parameters.substrate_um:g} μm substrate"
              f"<br><sup>Model peak {s.peak_c:.1f} °C · depth {s.parameters.substrate_um+s.parameters.drift_um:g} μm</sup>"
              for i, s in enumerate(solutions)]
    n = len(solutions)
    fig = make_subplots(rows=1, cols=n, horizontal_spacing=0.13,
                        subplot_titles=labels)
    fields = [s.temperature_c if units == "C" else s.temperature_k for s in solutions]
    lo = min(float(v.min()) for v in fields)
    lo = min(lo, min(s.parameters.sink_k - (273.15 if units == "C" else 0) for s in solutions))
    hi = max(float(v.max()) for v in fields)
    if hi-lo < 1e-8:
        hi = lo+1
    unit = "°C" if units == "C" else "K"
    for i, (s, field) in enumerate(zip(solutions, fields), 1):
        p = s.parameters
        kx, kz = conductivity_values(s.temperature_k, p)
        q = np.where((s.z_um[:, None] < p.drift_um) & (s.x_um[None, :] < p.contact_radius_um),
                     p.power_w_cm2 * 1e4 / (p.drift_um * 1e-6), 0)
        layer = np.broadcast_to(np.where(s.z_um[:, None] < p.drift_um, 0, 1), field.shape)
        data = np.stack((s.temperature_c, s.temperature_k, kx, kz, q, layer), axis=-1)
        axis = "r" if p.geometry == "axisymmetric" else "x"
        kwargs = dict(coloraxis="coloraxis") if shared else dict(
            colorscale=scale, zmin=float(field.min()), zmax=max(float(field.max()), float(field.min())+1e-6),
            colorbar=dict(title=unit, len=.77, thickness=12,
                          x=(.435 if n == 2 and i == 1 else 1.02)))
        # Actual cell edges preserve the nonuniform mesh; hover reports cell centres.
        fig.add_trace(go.Heatmap(x=(s.x_edges_m*1e6).tolist(), y=(s.z_edges_m*1e6).tolist(),
            z=field.tolist(), customdata=data.tolist(), zsmooth=False,
            hovertemplate=f"<b>{p.substrate_um:g} μm substrate</b><br>"
                +axis+" = %{x:.2f} μm<br>Depth = %{y:.2f} μm"
                +"<br><b>T = %{customdata[0]:.3f} °C</b> (%{customdata[1]:.3f} K)"
                +"<br>k lateral = %{customdata[2]:.3f} W/(m·K)"
                +"<br>k [001] = %{customdata[3]:.3f} W/(m·K)"
                +"<br>Q = %{customdata[4]:.4e} W/m³<extra></extra>",
            **kwargs), row=1, col=i)
        if contours and field.max()-field.min() > 1e-5:
            fig.add_trace(go.Contour(x=s.x_um.tolist(), y=s.z_um.tolist(), z=field.tolist(),
                contours=dict(coloring="none", showlabels=False), ncontours=12,
                line=dict(color="rgba(255,255,255,0.35)", width=.6),
                showscale=False, hoverinfo="skip"), row=1, col=i)
        depth = p.substrate_um+p.drift_um
        fig.add_shape(type="line", x0=0, x1=p.domain_radius_um, y0=p.drift_um, y1=p.drift_um,
                      line=dict(color="#7DE1DE", width=1.5, dash="dot"), row=1, col=i)
        fig.add_shape(type="line", x0=0, x1=p.contact_radius_um, y0=0, y1=0,
                      line=dict(color="#E6AC49", width=6), row=1, col=i)
        fig.add_shape(type="line", x0=0, x1=p.domain_radius_um, y0=depth, y1=depth,
                      line=dict(color=TEAL, width=3), row=1, col=i)
        j, k = np.unravel_index(field.argmax(), field.shape)
        fig.add_trace(go.Scatter(x=[float(s.x_um[k])], y=[float(s.z_um[j])], mode="markers",
            marker=dict(size=9, symbol="x", color="white", line_width=2),
            hoverinfo="skip", showlegend=False), row=1, col=i)
        if probe is not None:
            px, pz = probe
            if 0 <= px <= p.domain_radius_um and 0 <= pz <= depth:
                fig.add_trace(go.Scatter(x=[px], y=[pz], mode="markers",
                    marker=dict(symbol="circle-open", color="#45FFCF", size=14, line_width=2),
                    showlegend=False, hoverinfo="skip"), row=1, col=i)
        max_depth = depth if zoom_layers else max(v.parameters.substrate_um+v.parameters.drift_um for v in solutions)
        fig.update_xaxes(title=f"{'Radius r' if axis == 'r' else 'Lateral x'} (μm)", range=[0,p.domain_radius_um], row=1, col=i)
        fig.update_yaxes(title="Depth z (μm)" if i == 1 else None, range=[max_depth,0], row=1, col=i)
        if true_aspect:
            fig.update_yaxes(scaleanchor="x" if i == 1 else f"x{i}", scaleratio=1, row=1, col=i)
    style(fig, 540)
    fig.update_layout(showlegend=False,coloraxis=dict(colorscale=scale, cmin=lo, cmax=hi,
                                     colorbar=dict(title=unit, thickness=14, len=.88)),
                      margin=dict(l=62,r=62,t=75,b=62))
    return fig


def profiles_figure(solutions):
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=.14,
                        subplot_titles=["Near-surface profile", "Centreline through the wafer"])
    for s, color in zip(solutions, [ORANGE, TEAL]):
        p = s.parameters
        label = f"{p.substrate_um:g} μm"
        fig.add_trace(go.Scatter(x=s.x_um.tolist(), y=s.temperature_c[0].tolist(),
            mode="lines", name=label, legendgroup=label, line=dict(color=color,width=3),
            hovertemplate="x/r = %{x:.2f} μm<br>T = %{y:.3f} °C<extra>"+label+"</extra>"), row=1,col=1)
        # End at the known physical sink boundary, with an explicit Dirichlet endpoint.
        z = np.r_[s.z_um, p.substrate_um+p.drift_um]
        t = np.r_[s.temperature_c[:,0], p.sink_k-273.15]
        fig.add_trace(go.Scatter(x=z.tolist(),y=t.tolist(),mode="lines",name=label,
            showlegend=False,legendgroup=label,line=dict(color=color,width=3),
            hovertemplate="Depth = %{x:.2f} μm<br>T = %{y:.3f} °C<extra>"+label+"</extra>"),row=1,col=2)
    style(fig,410)
    fig.update_layout(legend=dict(orientation="h",x=0,y=1.25,yanchor="bottom"),margin=dict(t=100))
    fig.update_xaxes(title="Lateral coordinate (μm)", row=1,col=1)
    fig.update_xaxes(title="Depth (μm)",row=1,col=2)
    fig.update_yaxes(title="Temperature (°C)",gridcolor="#E5EAF0",showgrid=True)
    fig.update_layout(hovermode="x unified")
    return fig


def surface_figure(s):
    fig=go.Figure(go.Surface(x=s.x_um.tolist(),y=s.z_um.tolist(),z=s.temperature_c.tolist(),
                            colorscale=scientific_palette("Inferno"),colorbar=dict(title="°C"),
                            hovertemplate="x/r = %{x:.2f} μm<br>Depth = %{y:.2f} μm<br>T = %{z:.3f} °C<extra></extra>"))
    style(fig,550)
    fig.update_layout(scene=dict(xaxis_title="x/r (μm)",yaxis_title="Depth (μm)",
        zaxis_title="Temperature (°C)",aspectmode="manual",aspectratio=dict(x=1.4,y=1,z=.8),
        camera=dict(eye=dict(x=1.45,y=-1.75,z=1.05))), margin=dict(l=0,r=0,t=15,b=0))
    return fig


def field_dataframe(s):
    x,z=np.meshgrid(s.x_um,s.z_um)
    kx,kz=conductivity_values(s.temperature_k,s.parameters)
    p=s.parameters
    source=np.where((z<p.drift_um)&(x<p.contact_radius_um),p.power_w_cm2*1e4/(p.drift_um*1e-6),0.)
    return pd.DataFrame({"x_or_r_um":x.ravel(),"depth_um":z.ravel(),
        "T_C":s.temperature_c.ravel(),"T_K":s.temperature_k.ravel(),
        "k_lateral_W_mK":kx.ravel(),"k_001_W_mK":kz.ravel(),
        "Q_W_m3":source.ravel(),
        "layer":np.where(z.ravel()<s.parameters.drift_um,"drift","substrate")})


def solution_npz(solutions):
    data={}
    for i,s in enumerate(solutions):
        data.update({f"case{i}_temperature_K":s.temperature_k,
                     f"case{i}_x_edges_m":s.x_edges_m,f"case{i}_z_edges_m":s.z_edges_m,
                     f"case{i}_metadata_json":np.array(json.dumps(s.summary()))})
    buf=io.BytesIO()
    np.savez_compressed(buf,**data)
    return buf.getvalue()


def html_report(solutions, colorscale="Inferno"):
    """Self-contained offline figure; changing physical parameters requires Python."""
    mapfig=map_figure(solutions,colorscale=colorscale)
    maxdepth=max(s.parameters.substrate_um+s.parameters.drift_um for s in solutions)
    ownranges={f"yaxis{i+1 if i else ''}.range":[s.parameters.substrate_um+s.parameters.drift_um,0]
               for i,s in enumerate(solutions)}
    sharedranges={key:[maxdepth,0] for key in ownranges}
    buttons=[dict(label="Zoom each depth",method="relayout",args=[ownranges]),
             dict(label="Common depth",method="relayout",args=[sharedranges])]
    mapfig.update_layout(updatemenus=[dict(type="buttons",direction="right",buttons=buttons,
            x=0,y=1.25,xanchor="left",yanchor="top",font=dict(size=12))],margin=dict(t=115))
    maphtml=mapfig.to_html(full_html=False,include_plotlyjs=True,config=CONFIG,div_id="thermal-map")
    profilehtml=profiles_figure(solutions).to_html(full_html=False,include_plotlyjs=False,config=CONFIG)
    a,b=solutions
    rise_a=a.temperature_k.max()-a.parameters.sink_k
    reduction=(f"{100*(1-(b.temperature_k.max()-b.parameters.sink_k)/rise_a):.1f}%" if rise_a>1e-9 else "—")
    model="temperature-dependent k(T)" if a.parameters.conductivity=="temperature" else ("k fixed at 300 K" if a.parameters.conductivity=="frozen" else f"constant k={a.parameters.constant_k:g} W/(m·K)")
    summary=json.dumps([s.summary() for s in solutions],indent=2)
    rows="".join(f"<tr><td>{s.parameters.substrate_um:g} μm</td><td>{s.peak_c:.3f} °C</td>"
        f"<td>{s.source_w.sum():.6g} {s.power_unit}</td><td>{s.balance_relative:.2e}</td>"
        f"<td>{s.temperature_k.size:,}</td></tr>" for s in solutions)
    warning=("The nonlinear model reaches temperatures far above the paper's reference values. "
        "These are extrapolations of the assumed model; the paper does not supply a validity range for these laws. "
        if max(s.temperature_k.max() for s in solutions)>600 else "")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ga₂O₃ | Thermal Lab</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#edf2f6;color:{INK};font-family:Arial,sans-serif}}
header{{background:#12273e;color:#fff;padding:38px max(24px,calc((100vw - 1220px)/2)) 34px;border-bottom:4px solid #16a3ad}}
.eyebrow{{font-size:12px;letter-spacing:2px;color:#87d9df;font-weight:bold}}h1{{font-size:38px;letter-spacing:-1.5px;margin:12px 0}}
header p{{color:#c8d4e1;max-width:850px;line-height:1.65;margin-bottom:0}}main{{max-width:1268px;margin:auto;padding:24px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.card,.panel{{background:white;border:1px solid #dce4ec;border-radius:12px}}
.card{{padding:22px}}.label{{font-size:12px;color:{MUTED};letter-spacing:.6px}}.value{{font-size:30px;font-weight:bold;margin:10px 0 5px}}.small{{font-size:13px;color:{MUTED};line-height:1.6}}
.panel{{margin-top:18px;padding:22px;overflow:hidden}}h2{{font-size:20px;margin:0 0 9px}}.note{{border-left:4px solid #dfa25a;background:#fff9ed;padding:14px 18px;margin-top:18px;font-size:14px;line-height:1.65}}
#probe{{background:#e8f5f4;padding:14px 18px;border-radius:8px;margin:14px 0;font-size:14px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:13px 10px;border-bottom:1px solid #e3eaf0;text-align:left}}a{{color:#137581}}details{{line-height:1.7;margin-top:14px}}pre{{white-space:pre-wrap;font-size:12px;background:#f4f7fa;padding:18px;max-height:400px;overflow:auto}}button{{cursor:pointer}}.footer{{margin:25px 0;color:{MUTED};font-size:12px;line-height:1.8}}
@media(max-width:700px){{.stats{{grid-template-columns:repeat(2,1fr)}}main{{padding:12px}}.panel{{padding:12px}}h1{{font-size:30px}}.value{{font-size:25px}}}}
</style></head><body><header><div class="eyebrow">SEMICONDUCTOR HEAT TRANSFER · PYTHON STUDY</div><h1>Ga₂O₃ Thermal Lab</h1><p>Explore how substrate thickness changes the steady temperature field. A conservative 2D thermal reconstruction inspired by Figure 3 of Chiang et al. (2024).</p></header><main>
<div class="stats"><div class="card"><div class="label">{a.parameters.substrate_um:g} μm · model peak</div><div class="value">{a.peak_c:.1f} °C</div><div class="small">{a.temperature_k.max()-a.parameters.sink_k:.1f} K rise above sink</div></div>
<div class="card"><div class="label">{b.parameters.substrate_um:g} μm · model peak</div><div class="value">{b.peak_c:.1f} °C</div><div class="small">{b.temperature_k.max()-b.parameters.sink_k:.1f} K rise above sink</div></div>
<div class="card"><div class="label">Rise reduction A → B</div><div class="value">{reduction}</div><div class="small">Calculated from ΔT, not Celsius ratios</div></div>
<div class="card"><div class="label">Power density</div><div class="value">{a.parameters.power_w_cm2:,.0f}</div><div class="small">W/cm² · {model}</div></div></div>
<div class="note"><b>Model interpretation.</b> The paper reports 155 °C and 55 °C at 1500 W/cm². These are reference values, not outputs of this model. Its TCAD heat source and full boundary implementation are unavailable. {warning}This report uses {escape(a.parameters.geometry)} geometry, uniform drift-layer heating, and an ideal bottom sink.</div>
<section class="panel"><h2>Temperature field</h2><div class="small">Hover for full numerical values. Drag to zoom; double-click to reset. The toolbar saves a PNG. Gold: contact footprint · cyan dotted: drift interface · teal: ideal sink. Shared temperature scale; panel depth axes are zoomed independently by default.</div>
<div id="probe" aria-live="polite">POINT INSPECTOR · Hover over either temperature map to inspect a computed cell.</div>{maphtml}</section>
<section class="panel"><h2>Follow the heat through the device</h2><div class="small">Profiles use finite-volume cell centres. The centreline includes the exact imposed sink temperature at the bottom face.</div>{profilehtml}</section>
<section class="panel"><h2>Numerical record</h2><table><thead><tr><th>Substrate</th><th>Peak</th><th>Generated heat</th><th>Energy imbalance</th><th>Cells</th></tr></thead><tbody>{rows}</tbody></table>
<details><summary>Physical assumptions and interpretation</summary><p>Source: Q = q″/d in the 10 μm drift layer beneath the 500 μm contact radius; zero elsewhere. Bottom: T = {a.parameters.sink_k:g} K. Top: convection, h = {a.parameters.h_w_m2k:g} W/(m²·K), ambient {a.parameters.ambient_k:g} K. Centre and outer edge: zero lateral flux. The default outer radius is an assumed 1000 μm. Contacts and heat-sink bulk are collapsed into boundaries.</p><p>Default radial conductivity is √(k[100]k[010]); this is an explicit effective-medium assumption, not an exact representation of the in-plane anisotropy of β-Ga₂O₃. The alternative planar model can use either crystal direction. The conductivity laws are taken from Table I with T in kelvin.</p><p>The maps show computed cell values without visual smoothing. Decimal places describe solver output, not experimental accuracy. Contour lines interpolate between cell centres. Open the Python app to change physical parameters or probe exact coordinates.</p></details>
<details><summary>Reproducibility metadata</summary><pre>{escape(summary)}</pre></details></section>
<div class="footer">Reference: Chiang, C.-C., Li, J.-S., Wan, H.-H., Ren, F., &amp; Pearton, S. J. (2024). <i>Effect of Substrate Thinning on Temperature Rise in Ga₂O₃ Rectifiers.</i> ECS Journal of Solid State Science and Technology, 13, 115001. <a href="{PAPER_DOI}">DOI: 10.1149/2162-8777/ad89fa</a><br>Self-contained HTML generated in Python with Plotly. Works offline after download; physical parameter changes require the included Python app.</div></main>
<script>document.getElementById('thermal-map').on('plotly_hover',function(e){{const p=e.points.find(v=>v.data.type==='heatmap');if(!p||!p.customdata)return;const d=p.customdata;document.getElementById('probe').textContent='POINT INSPECTOR · '+(p.xaxis._id==='x'?'Case A':'Case B')+' · x/r '+p.x.toFixed(2)+' μm · depth '+p.y.toFixed(2)+' μm · '+d[0].toFixed(3)+' °C ('+d[1].toFixed(3)+' K) · '+(d[5]===0?'drift layer':'substrate')+' · k lateral '+d[2].toFixed(3)+' W/(m·K)';}});</script></body></html>'''
