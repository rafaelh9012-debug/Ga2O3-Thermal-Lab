"""Generate the HTML report, CSV/NPZ data and publication-style PNG/SVG figures."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import numpy as np
from thermal_model import Parameters, solve, MESHES
from figures import html_report, field_dataframe, solution_npz


def static_figure(solutions,path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.ticker import MaxNLocator
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,
                         "axes.labelcolor":"#172B45","text.color":"#172B45",
                         "axes.spines.top":False,"axes.spines.right":False})
    fig=plt.figure(figsize=(13.5,9),facecolor="#F5F8FB")
    gs=fig.add_gridspec(2,3,width_ratios=[1,1,.035],height_ratios=[1.35,1],
                       left=.065,right=.945,bottom=.19,top=.765,hspace=.58,wspace=.28)
    norm=Normalize(min(s.parameters.sink_k-273.15 for s in solutions),max(s.peak_c for s in solutions))
    colors=["#DE7147","#148D98"]
    for i,s in enumerate(solutions):
        ax=fig.add_subplot(gs[0,i]);p=s.parameters
        m=ax.pcolormesh(s.x_edges_m*1e6,s.z_edges_m*1e6,s.temperature_c,cmap="inferno",norm=norm,rasterized=True)
        if np.ptp(s.temperature_c)>1e-4:
            ax.contour(s.x_um,s.z_um,s.temperature_c,levels=10,colors="white",alpha=.28,linewidths=.5)
        ax.plot([0,p.contact_radius_um],[0,0],color="#E6AC49",lw=4,clip_on=False)
        ax.axhline(p.drift_um,color="#79E1DA",ls=":",lw=1)
        ax.set_ylim(p.substrate_um+p.drift_um,0);ax.set_xlim(0,p.domain_radius_um)
        ax.set_xlabel("Radius r (μm)" if p.geometry=="axisymmetric" else "Lateral x (μm)")
        ax.set_ylabel("Depth z (μm)")
        ax.set_title(f"{'A' if i==0 else 'B'}  |  {p.substrate_um:g} μm substrate\nModel peak {s.peak_c:.1f} °C",loc="left",fontweight="bold",pad=14)
        ax.yaxis.set_major_locator(MaxNLocator(5))
    cb=fig.colorbar(m,cax=fig.add_subplot(gs[0,2]));cb.set_label("Temperature (°C)");cb.outline.set_visible(False)
    for j,title in enumerate(["Near-surface temperature","Centreline to the sink"]):
        ax=fig.add_subplot(gs[1,j]);ax.set_facecolor("white")
        for s,color in zip(solutions,colors):
            p=s.parameters
            x=s.x_um if j==0 else np.r_[s.z_um,p.substrate_um+p.drift_um]
            y=s.temperature_c[0] if j==0 else np.r_[s.temperature_c[:,0],p.sink_k-273.15]
            ax.plot(x,y,color=color,lw=2.6,label=f"{p.substrate_um:g} μm")
        ax.set_title(title,loc="left",fontweight="bold",pad=12)
        ax.set_xlabel("Lateral coordinate (μm)" if j==0 else "Depth (μm)")
        ax.set_ylabel("Temperature (°C)");ax.grid(axis="y",color="#DCE5ED",lw=.6)
        ax.legend(frameon=False,fontsize=9)
    fig.text(.065,.95,"Ga₂O₃  /  THERMAL LAB",fontsize=24,fontweight="bold")
    fig.text(.065,.909,"Steady heat conduction · substrate thinning study inspired by Chiang et al. (2024)",fontsize=11,color="#5A6F85")
    p=solutions[0].parameters
    fig.text(.065,.868,f"{p.power_w_cm2:g} W/cm²  ·  {p.geometry}  ·  conductivity: {p.conductivity}  ·  bottom {p.sink_k:g} K",fontsize=11)
    fig.text(.065,.082,"MODEL OUTPUT — paper reference peaks: 155 °C and 55 °C at 1500 W/cm². The source distribution and radial conductivity are approximations.",fontsize=8.6)
    fig.text(.065,.053,"Shared temperature colors; separate depth ranges. Contacts and packaging are collapsed. High-temperature k(T) results are unvalidated extrapolations.",fontsize=8.6,color="#5A6F85")
    fig.savefig(path.with_suffix(".png"),dpi=220,facecolor=fig.get_facecolor())
    fig.savefig(path.with_suffix(".svg"),facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path(__file__).parent/"examples")
    parser.add_argument("--power",type=float,default=1500.,help="Power density in W/cm^2")
    parser.add_argument("--thickness-a",type=float,default=630.)
    parser.add_argument("--thickness-b",type=float,default=50.)
    parser.add_argument("--mesh",choices=list(MESHES),default="Standard")
    parser.add_argument("--conductivity",choices=["temperature","frozen","constant"],default="temperature")
    parser.add_argument("--geometry",choices=["axisymmetric","planar"],default="axisymmetric")
    parser.add_argument("--no-static",action="store_true",help="Skip Matplotlib PNG/SVG creation")
    args=parser.parse_args()
    nx,nz,nd=MESHES[args.mesh]
    p=Parameters(substrate_um=args.thickness_a,power_w_cm2=args.power,conductivity=args.conductivity,
        geometry=args.geometry,nx=nx,nz_substrate=nz,nz_drift=nd)
    solutions=[solve(p),solve(replace(p,substrate_um=args.thickness_b))]
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"Ga2O3_Interactive_Report.html").write_text(html_report(solutions),encoding="utf-8")
    (args.output/"parameters_and_diagnostics.json").write_text(json.dumps([s.summary() for s in solutions],indent=2),encoding="utf-8")
    for i,s in enumerate(solutions):
        field_dataframe(s).to_csv(args.output/f"case_{i+1}_{s.parameters.substrate_um:g}um.csv",index=False,float_format="%.10g")
        print(f"{s.parameters.substrate_um:g} μm: peak {s.peak_c:.6f} °C; energy error {s.balance_relative:.2e}; {s.iterations} iterations")
    (args.output/"Ga2O3_Fields.npz").write_bytes(solution_npz(solutions))
    if not args.no_static:
        static_figure(solutions,args.output/"Ga2O3_Figure3_Study")
    print(f"Saved results to {args.output.resolve()}")


if __name__=="__main__":
    main()
