"""Report-aligned Streamlit interface. Run: python -m streamlit run app.py"""
from dataclasses import asdict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model import Parameters, SCENARIOS, average_cost, dust, optimize


st.set_page_config(page_title='Dynamiq | Solar cleaning planner',page_icon='☀️',layout='wide')
st.markdown('''<style>
.block-container { max-width:1320px; padding-top:2.3rem; }
h1,h2,h3 { letter-spacing:-.025em; }
.eyebrow { color:#087e78; font-size:.8rem; font-weight:750; letter-spacing:.17em; margin-bottom:.6rem; }
.hero-title { font-size:2.65rem; font-weight:750; line-height:1.08; margin:0 0 .65rem; color:#172d3c; }
.hero-copy { color:#60717e; max-width:760px; font-size:1.05rem; margin-bottom:1.4rem; }
.pill { display:inline-block; padding:.35rem .7rem; border-radius:20px; color:#42606b;
background:#e9f0f3; margin:0 .4rem .45rem 0; font-size:.78rem; }
div[data-testid="stMetric"] { background:white; border:1px solid #e1e8ed; border-radius:14px;
padding:1rem 1.1rem; box-shadow:0 3px 12px #17304405; }
div[data-testid="stMetricValue"] { color:#172d3c; }
div[data-testid="stSidebar"] { border-right:1px solid #e1e8ed; }
</style>''',unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def calculate(params,H,lower):
    return optimize(params,H,lower)


@st.cache_data(show_spinner=False)
def comparison(p,K,alpha,H,lower):
    records=[]
    for name,row in SCENARIOS.items():
        params=Parameters(a=row['a'],r=row['r'],E0=row['E0'],p=p,K=K,alpha=alpha)
        result=optimize(params,H,lower)
        message={'minimum':'Minimum found',
                 'not_bracketed':'No stationary point found in search range',
                 'sosc_not_positive':'Second derivative test not positive'}[result.status]
        records.append({'Scenario':name,'Wind': 'Low' if row['wind']==3 else 'High',
                        'Dust':row['dust'],'Humidity':'Low' if row['rh']==20 else 'High',
                        'Solar yield':row['solar'],'a (g/m²/day)':params.a,'r (1/day)':params.r,
                        'E0 (kWh/day)':params.E0,'Continuous T* (days)':result.continuous_days,
                        'Chosen interval (days)':result.recommended_days,
                        'Cost at chosen interval (AED/day)':result.daily_cost,'Result':message})
    return pd.DataFrame(records)


def style_chart(fig,ytitle,xtitle='Days since complete cleaning'):
    fig.update_layout(template='plotly_white',height=330,margin=dict(l=10,r=15,t=25,b=15),
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='white',
                      font=dict(family='Arial',color='#304854'),xaxis_title=xtitle,
                      yaxis_title=ytitle,hovermode='x unified',showlegend=False)
    fig.update_xaxes(gridcolor='#edf1f4',zeroline=False)
    fig.update_yaxes(gridcolor='#edf1f4',zeroline=False)
    return fig


with st.sidebar:
    st.markdown('### Configure your model')
    st.caption('Choose one of the 16 report scenarios, then edit the model parameters if needed.')
    preset=st.selectbox('Scenario preset',list(SCENARIOS),index=5)
    base=SCENARIOS[preset]
    st.caption(f"{base['dust']} dust · {base['rh']}% humidity · {base['wind']} m/s wind · {base['solar'].lower()} solar yield")
    with st.form('report_parameters'):
        st.markdown('**Scenario parameters**')
        a=st.number_input('Deposition a · g/m²/day',min_value=.000001,max_value=10.0,
                          value=base['a'],step=.001,format='%.6f',key=f'report_{preset}_a')
        r=st.number_input('Natural removal r · 1/day',min_value=.000001,max_value=10.0,
                          value=base['r'],step=.001,format='%.6f',key=f'report_{preset}_r',
                          help='Report presets use assumed removal coefficients. This implementation requires r > 0.')
        E0=st.number_input('Clean daily energy yield E₀ · kWh/day',min_value=1.0,max_value=1e9,
                           value=base['E0'],step=1000.0,format='%.0f',key=f'report_{preset}_E0',
                           help='Total yield of the installation. Report defaults refer to 10 MWp.')
        st.markdown('**Shared parameters**')
        p=st.number_input('Electricity selling price p · AED/kWh',min_value=.000001,max_value=100.0,
                          value=.06,step=.01,format='%.6f',key='report_p',
                          help='Enter AED, not fils: 6 fils/kWh = 0.06 AED/kWh.')
        K=st.number_input('Cost per complete cleaning K · AED',min_value=.01,max_value=1e9,
                          value=1000.0,step=100.0,format='%.2f',key='report_K',
                          help='The cleaning cost must refer to the same installation as E₀.')
        alpha=st.number_input('Energy yield sensitivity α · m²/g',min_value=.000001,max_value=10.0,
                              value=.017,step=.001,format='%.6f',key='report_alpha')
        lower=st.number_input('Search lower bound · days',min_value=1,max_value=36499,value=1,key='report_lower',
                              help='Earliest cleaning interval included in the numerical root search.')
        H=st.number_input('Search upper limit H · days',min_value=2,max_value=36500,value=365,key='report_H',
                          help='The code searches C′(T)=0 between the selected lower bound and H. This does not calculate an annual total-cost objective.')
        submitted=st.form_submit_button('Run model',type='primary',use_container_width=True)
    st.caption('Each cycle starts clean: D(0)=0. Cleaning is fully effective, and weather inputs stay constant within a scenario.')


if submitted or 'report_run_v3' not in st.session_state:
    candidate=Parameters(a=a,r=r,E0=E0,p=p,K=K,alpha=alpha)
    try:
        with st.spinner('Calculating the optimal cleaning interval…'):
            outcome=calculate(candidate,H,lower)
    except (ValueError,OverflowError,ArithmeticError,TypeError) as exc:
        st.error(f'Please check the inputs: {exc}')
        st.stop()
    st.session_state['report_run_v3']=(candidate,lower,H,preset,outcome)

params,search_lower,search_limit,saved_preset,result=st.session_state['report_run_v3']
st.markdown('<div class="eyebrow">D Y N A M I Q</div>',unsafe_allow_html=True)
st.markdown('<div class="hero-title">A clearer time to clean.</div>',unsafe_allow_html=True)
st.markdown('<div class="hero-copy">Compare cleaning expenditure with energy revenue lost to dust, using the model and scenarios from our report.</div>',unsafe_allow_html=True)
st.markdown(f'<span class="pill">{saved_preset} chosen scenario</span><span class="pill">16 weather scenarios</span><span class="pill">Complete, early-morning cleaning</span><span class="pill">AED per day</span>',unsafe_allow_html=True)
st.caption('Results use the last submitted inputs. Select Run model after making changes.')

if result.status=='minimum':
    st.success(f'Under this constant scenario, the selected whole-day cleaning interval is {result.recommended_days} days.')
elif result.status=='not_bracketed':
    st.info(f'No stationary point was found between {search_lower:,} and {search_limit:,} days. '
            'This search alone does not establish that there is no finite optimum outside the range.')
else:
    st.warning('A stationary point was found, but the second derivative test did not confirm a strict minimum.')

c1,c2,c3=st.columns(3)
c1.metric('Selected cleaning interval',f'{result.recommended_days} days' if result.recommended_days else 'Not found')
c2.metric('Cost at selected interval · AED/day',f'{result.daily_cost:,.2f}' if result.daily_cost is not None else '—')
c3.metric('Stationary point · days (rounded)',f'{result.continuous_days:.0f}' if result.continuous_days is not None else '—')

overview,all_cases,details=st.tabs(['Your results','All 16 scenarios','Model from the report'])

with overview:
    if result.status=='minimum':
        st.caption(f'Second derivative at the continuous stationary point: {result.second_derivative:.6g} AED/day³, which is positive. '
                   'The selected whole-day interval has the lower cost of the allowed floor and ceiling choices.')
    st.markdown('#### Average daily cost versus cleaning interval')
    grid=np.unique(np.r_[np.geomspace(search_lower,search_limit,120),result.recommended_days or search_lower])
    values=[average_cost(float(T),params) for T in grid]
    fig=go.Figure(go.Scatter(x=grid,y=values,mode='lines',line=dict(color='#087e78',width=3)))
    if result.recommended_days:
        fig.add_vline(x=result.recommended_days,line_dash='dot',line_color='#087e78')
        fig.add_trace(go.Scatter(x=[result.recommended_days],y=[result.daily_cost],mode='markers',marker=dict(size=10,color='#087e78')))
    st.plotly_chart(style_chart(fig,'C(T) · AED/day','Cleaning interval T · days'),use_container_width=True)

    duration=result.recommended_days or search_limit
    t=np.linspace(0,duration,250)
    loading=dust(t,params)
    left,right=st.columns(2)
    with left:
        st.markdown('#### Dust accumulation from clean panels')
        f=go.Figure(go.Scatter(x=t,y=loading,mode='lines',fill='tozeroy',
                   line=dict(color='#087e78',width=3),fillcolor='rgba(8,126,120,.08)'))
        st.plotly_chart(style_chart(f,'Dust loading D(t) · g/m²'),use_container_width=True)
    with right:
        st.markdown('#### Daily energy yield')
        g=go.Figure(go.Scatter(x=t,y=params.E0*np.exp(-params.alpha*loading),mode='lines',
                              line=dict(color='#496f9b',width=3)))
        st.plotly_chart(style_chart(g,'Energy yield E(t) · kWh/day'),use_container_width=True)
    st.caption('The curves show the report’s clean-start solution between cleaning events. '
               'They do not simulate an annual sequence of weather changes or rainfall.')

with all_cases:
    st.markdown('#### Compare the report scenarios')
    st.caption('Uses the original 16 sets of a, r and E₀ with the last submitted shared p, K, α and search bounds. '
               'Edits to a, r or E₀ affect only the selected-case calculation above.')
    try:
        with st.spinner('Calculating the 16 report scenarios…'):
            frame=comparison(params.p,params.K,params.alpha,search_limit,search_lower)
        # Format only the display copy: the model keeps numerical values and full precision.
        display=frame.copy()
        formats={'Continuous T* (days)':'.0f','Chosen interval (days)':'.0f',
                 'Cost at chosen interval (AED/day)':'.2f'}
        for column,fmt in formats.items():
            display[column]=frame[column].map(lambda value,f=fmt:'—' if pd.isna(value) else format(value,f))
        display=display.rename(columns={'Continuous T* (days)':'Continuous T* (days, rounded)'})
        st.dataframe(display,hide_index=True,use_container_width=True,height=610)
    except (ValueError,OverflowError,ArithmeticError,TypeError) as exc:
        st.error(f'The comparison could not be calculated: {exc}')

with details:
    st.markdown('#### Dust accumulation and cleaning')
    st.latex(r'\frac{dD}{dt}=a-rD,\qquad D(0)=0')
    st.latex(r'D(t)=\frac{a}{r}(1-e^{-rt})')
    st.latex(r'D(t_i^+)=(1-\eta_i)D(t_i^-),\qquad \eta_i=1')
    st.write('The calculation covers one constant-weather cycle starting immediately after complete cleaning.')
    st.markdown('#### Energy yield and revenue loss')
    st.latex(r'E(t)=E_0 e^{-\alpha D(t)}')
    st.latex(r'L(t)=pE_0[1-e^{-\alpha D(t)}]')
    st.markdown('#### Average daily cost and optimization')
    st.latex(r'C(T)=\frac{K}{T}+\frac{pE_0}{T}\int_0^T[1-e^{-\alpha D(t)}]dt')
    st.latex(r"C'(T^*)=0,\qquad C''(T^*)>0")
    st.write('As in the supplied code, SymPy constructs and differentiates the cost expression, '
             'Brent’s method searches for a stationary point between the selected bounds, and numerical quadrature '
             'evaluates the floor and ceiling cleaning intervals. The second derivative is checked at the continuous root.')
    st.markdown('#### Scope of this implementation')
    st.write('The model minimizes average daily cost under sustained scenario conditions. '
             'It does not optimize the report’s general annual total-cost objective J or accept an existing dust load.')
    st.write('The report assumes a 10 MWp installation, 25° panel tilt, complete cleaning and negligible cleaning downtime. '
             'Tilt is already represented in the preset deposition rates, so it is not an independent control here. '
             'Removal coefficients are assumptions; the fixed settling approximation neglects wind and humidity effects on deposition.')
    st.write('Our report considers rainfall above 3mm as a full cleaning, and neglects lighter rain. Hence, '
             'this web-app does not include a rain-related parameter input.')
    st.markdown('#### Last submitted inputs')
    st.json({**asdict(params),'lower_search_days':search_lower,'H_search_days':search_limit})

st.caption('Dynamiq · Constant-weather scenario analysis · Results are conditional on the report’s model assumptions.')
