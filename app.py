"""Run with: python -m streamlit run app.py"""
from dataclasses import asdict, replace
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model import Parameters, SCENARIOS, cost_components, dust, optimize, remaining_wait


st.set_page_config(page_title='Dynamiq | Solar cleaning planner', page_icon='☀️', layout='wide')
st.markdown('''<style>
.block-container { max-width: 1320px; padding-top: 2.3rem; }
h1,h2,h3 { letter-spacing: -.025em; }
.eyebrow { color:#087e78; font-size:.8rem; font-weight:750; letter-spacing:.17em; margin-bottom:.6rem; }
.hero-title { font-size:2.65rem; font-weight:750; line-height:1.08; margin:0 0 .65rem; color:#172d3c; }
.hero-copy { color:#60717e; max-width:760px; font-size:1.05rem; margin-bottom:1.4rem; }
.pill { display:inline-block; padding:.35rem .7rem; border-radius:20px; color:#42606b;
background:#e9f0f3; margin:0 .4rem .45rem 0; font-size:.78rem; }
div[data-testid="stMetric"] { background:white; border:1px solid #e1e8ed; border-radius:14px;
padding:1rem 1.1rem; box-shadow:0 3px 12px #17304405; }
div[data-testid="stMetricValue"] { color:#172d3c; }
div[data-testid="stSidebar"] { border-right:1px solid #e1e8ed; }
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def calculate(params, lower, upper):
    return optimize(params, lower, upper)


@st.cache_data(show_spinner=False)
def comparison(p, K, alpha, lower, upper):
    records = []
    for name, row in SCENARIOS.items():
        params = Parameters(a=row['a'], r=row['r'], E0=row['E0'], p=p, K=K, alpha=alpha)
        result = optimize(params, lower, upper)
        status = {'finite':'Finite optimum', 'below_range':'Minimum allowed interval',
                  'no_cleaning':'No finite scheduled optimum', 'beyond_range':'Optimum beyond search range'}[result.status]
        records.append({'Scenario':name, 'Dust':row['dust'], 'Humidity (%)':row['rh'],
                        'Wind (m/s)':row['wind'], 'Solar yield':row['solar'],
                        'a (g/m²/day)':params.a, 'r (1/day)':params.r, 'E0 (kWh/day)':params.E0,
                        'Continuous optimum (days)':result.continuous_days,
                        'Recommended interval (days)':result.recommended_days,
                        'Daily cost (AED/day)':result.daily_cost,
                        'No-cleaning cost (AED/day)':result.no_cleaning_daily, 'Result':status})
    return pd.DataFrame(records)


def chart_style(fig, ytitle, xtitle='Days since complete cleaning'):
    fig.update_layout(template='plotly_white', height=330, margin=dict(l=10,r=15,t=25,b=15),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='white',
                      font=dict(family='Arial',color='#304854'),
                      xaxis_title=xtitle, yaxis_title=ytitle,
                      legend=dict(orientation='h',y=1.14,x=0), hovermode='x unified')
    fig.update_xaxes(gridcolor='#edf1f4',zeroline=False)
    fig.update_yaxes(gridcolor='#edf1f4',zeroline=False)
    return fig


with st.sidebar:
    st.markdown('### Configure your model')
    st.caption('Choose a report scenario, then adjust any input. Defaults refer to a 10 MWp installation.')
    choice = st.selectbox('Scenario preset', list(SCENARIOS)+['Custom'], index=5,
                          help='Changing the preset loads a different set of a, r and E₀. Press Run model to apply.')
    base = SCENARIOS.get(choice, SCENARIOS['S06'])
    if choice != 'Custom':
        st.caption(f"{base['dust']} dust · {base['rh']}% humidity · {base['wind']} m/s wind · {base['solar'].lower()} solar yield")
    with st.form('parameters'):
        st.markdown('**Dust and energy**')
        a = st.number_input('Deposition a · g/m²/day', min_value=0.0, max_value=10.0,
                            value=base['a'], step=.001, format='%.5f', key=f'{choice}_a')
        r = st.number_input('Natural removal r · 1/day', min_value=0.0, max_value=10.0,
                            value=base['r'], step=.001, format='%.5f', key=f'{choice}_r',
                            help='A coefficient applied to existing dust. The report presets are sensitivity assumptions. Zero means no natural removal.')
        E0 = st.number_input('Clean energy yield E₀ · kWh/day', min_value=1.0, max_value=1e9,
                             value=base['E0'], step=1000.0, format='%.0f', key=f'{choice}_E0',
                             help='Total daily yield of the installation, not one panel.')
        alpha = st.number_input('Dust sensitivity α · m²/g', min_value=.000001, max_value=10.0,
                                value=.017, step=.001, format='%.6f', key='shared_alpha')
        st.markdown('**Economics**')
        p = st.number_input('Electricity selling price p · AED/kWh', min_value=.000001, max_value=100.0,
                            value=.06, step=.01, format='%.6f', key='shared_p',
                            help='Enter AED, not fils: 6 fils/kWh = 0.06 AED/kWh. Use the facility selling price or a clearly stated valuation assumption.')
        K = st.number_input('Cost per complete cleaning K · AED', min_value=.01, max_value=1e9,
                            value=1000.0, step=100.0, format='%.2f', key='shared_K',
                            help='Cleaning cost must cover the same installation as E₀.')
        st.markdown('**Allowed cycle lengths**')
        lo, hi = st.columns(2)
        minimum = lo.number_input('Shortest · days', min_value=1, max_value=36500, value=1, key='min_days')
        maximum = hi.number_input('Longest · days', min_value=1, max_value=36500, value=365, key='max_days')
        st.caption('These are search bounds, not an annual planning horizon.')
        st.markdown('**Optional current dust**')
        D0 = st.number_input('Current loading D₀ · g/m²', min_value=0.0, max_value=10000.0,
                             value=0.0, step=.1, format='%.3f', key='current_dust',
                             help='Used only for the remaining-time threshold policy. It does not change the repeating clean-start cost function.')
        submitted = st.form_submit_button('Run model', type='primary', use_container_width=True)

    st.caption('Complete cleaning and constant conditions are assumed. Rainfall and forecasts are not simulated automatically.')


if submitted or 'run' not in st.session_state:
    candidate = Parameters(a=a,r=r,E0=E0,p=p,K=K,alpha=alpha)
    try:
        outcome = calculate(candidate, minimum, maximum)
    except (ValueError, OverflowError, ArithmeticError) as exc:
        st.error(f'Please check your inputs: {exc}')
        st.stop()
    st.session_state['run'] = (candidate, minimum, maximum, D0, choice, outcome)

params, lower, upper, initial, saved_choice, result = st.session_state['run']
st.markdown('<div class="eyebrow">D Y N A M I Q</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">A clearer time to clean.</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-copy">Balance the value of recovered solar energy against the cost of cleaning. Explore your assumptions, compare conditions, and see the trade-off.</div>', unsafe_allow_html=True)
st.markdown(f'<span class="pill">{saved_choice} inputs</span><span class="pill">Complete cleaning</span><span class="pill">Constant conditions</span><span class="pill">AED per day</span>', unsafe_allow_html=True)
st.caption('Results use the last submitted inputs. Change values in the sidebar and select Run model to update.')

if result.status == 'no_cleaning':
    st.info('No finite economic cleaning interval under these assumptions. The long-run average cost decreases toward the no-scheduled-cleaning limit. This is a model result, not a claim that cleaning is never operationally necessary.')
    if initial > 0:
        st.caption('The long-run verdict does not decide whether an unusually large initial dust load should be cleaned once now. That decision needs a separate finite-horizon comparison.')
elif result.status == 'beyond_range':
    st.warning(f'A finite optimum exists beyond {upper:,} days. Increase the longest cycle length to locate it. The app has not classified this as “no cleaning.”')
elif result.status == 'below_range':
    st.warning(f'The continuous optimum is shorter than the allowed minimum of {lower} days. The recommendation is the best allowed whole-day interval.')
else:
    st.success(f'Under sustained conditions, clean approximately every {result.recommended_days:,} days.')

interval_text = f'{result.recommended_days:,} days' if result.recommended_days else 'Not located' if result.status=='beyond_range' else 'No schedule'
daily_text = f'AED {result.daily_cost:,.2f}' if result.daily_cost is not None else 'Not located'
m1,m2,m3 = st.columns(3)
m1.metric('Recommended interval', interval_text)
m2.metric('Average daily cost', daily_text)
m3.metric('No scheduled cleaning · AED/day', f'{result.no_cleaning_daily:,.2f}')

overview, all_cases, details = st.tabs(['Your results', 'Compare all 16 scenarios', 'Model and assumptions'])
with overview:
    if result.recommended_days:
        diff = result.no_cleaning_daily-result.daily_cost
        st.caption(f'Continuous optimum: {result.continuous_days:.3f} days. Whole-day choice compares floor and ceiling within the allowed bounds. '
                   f'Difference versus no scheduled cleaning: AED {diff:,.2f}/day (positive means savings).')
        left,right = st.columns([1.1,1])
        with left:
            st.markdown('#### Where the daily cost goes')
            breakdown = pd.DataFrame({'Component':['Cleaning','Energy lost to dust','Total'],
                                      'AED/day':[result.cleaning_daily,result.dust_daily,result.daily_cost]})
            st.dataframe(breakdown,hide_index=True,use_container_width=True,
                         column_config={'AED/day':st.column_config.NumberColumn(format='%.2f')})
        with right:
            st.markdown('#### With dust already on the panels')
            wait, threshold = remaining_wait(params,result.recommended_days,initial)
            if wait == 0:
                st.write('**The threshold policy recommends cleaning now.**')
            else:
                st.write(f'**Approximately {wait:.1f} days until the cleaning threshold.**')
            st.caption(f'Current dust: {initial:.3f} g/m² · Threshold: {threshold:.3f} g/m². '
                       'This is a threshold extension of the clean-start cycle, not a new optimization with weather forecasts.')

    st.markdown('#### The cost of waiting')
    grid = np.unique(np.r_[np.geomspace(lower,upper,120), result.recommended_days or lower])
    costs = np.array([cost_components(float(T),params) for T in grid])
    fig = go.Figure()
    for i,label,color,dash in [(2,'Total cost','#087e78','solid'),(0,'Cleaning','#c78a24','dash'),(1,'Lost energy value','#496f9b','dash')]:
        fig.add_trace(go.Scatter(x=grid,y=costs[:,i],name=label,mode='lines',line=dict(color=color,width=3 if i==2 else 2,dash=dash)))
    fig.add_hline(y=result.no_cleaning_daily,line_dash='dot',line_color='#8a969e',
                  annotation_text='No-scheduled-cleaning limit',annotation_position='top left')
    if result.recommended_days:
        fig.add_vline(x=result.recommended_days,line_dash='dot',line_color='#087e78')
        fig.add_trace(go.Scatter(x=[result.recommended_days],y=[result.daily_cost],mode='markers',name='Recommended',marker=dict(size=10,color='#087e78')))
    st.plotly_chart(chart_style(fig,'Average cost · AED/day','Cleaning interval · days'),use_container_width=True)

    duration = result.recommended_days or min(upper,180)
    t = np.linspace(0,duration,250)
    loading = dust(t,params)
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('#### Dust between cleanings')
        f = go.Figure(go.Scatter(x=t,y=loading,mode='lines',name='From clean panels',fill='tozeroy',line=dict(color='#087e78',width=3),fillcolor='rgba(8,126,120,.08)'))
        if initial>0:
            f.add_trace(go.Scatter(x=t,y=dust(t,params,initial),mode='lines',name='From current dust',line=dict(color='#c78a24',dash='dash')))
        st.plotly_chart(chart_style(f,'Dust loading · g/m²','Elapsed days'),use_container_width=True)
    with c2:
        st.markdown('#### Energy yield relative to clean panels')
        g = go.Figure(go.Scatter(x=t,y=100*np.exp(-params.alpha*loading),mode='lines',name='Clean-start cycle',line=dict(color='#496f9b',width=3)))
        if initial>0:
            g.add_trace(go.Scatter(x=t,y=100*np.exp(-params.alpha*dust(t,params,initial)),mode='lines',name='From current dust',line=dict(color='#c78a24',dash='dash')))
        g.update_yaxes(range=[0,102])
        st.plotly_chart(chart_style(g,'Clean-panel yield retained · %','Elapsed days'),use_container_width=True)
    st.caption('These curves show one uninterrupted accumulation period. Scheduled cleaning resets dust to zero; that jump occurs at the end of a cycle.')

    summary = {**asdict(params), 'scenario':saved_choice,'min_days':lower,'max_days':upper,
               'initial_dust_g_m2':initial, **asdict(result)}
    st.download_button('Download this result as CSV',pd.DataFrame([summary]).to_csv(index=False),
                       file_name='dynamiq_result.csv',mime='text/csv')

with all_cases:
    st.markdown('#### One model, sixteen conditions')
    st.caption('Uses the report’s preset a, r and E₀ values with your last submitted p, K, α and search bounds. '
               'Custom a, r, E₀ and current dust do not replace the preset inputs in this comparison.')
    frame = comparison(params.p,params.K,params.alpha,lower,upper)
    st.dataframe(frame,hide_index=True,use_container_width=True,height=610,
                 column_config={name:st.column_config.NumberColumn(format='%.2f')
                                for name in ['Continuous optimum (days)','Daily cost (AED/day)','No-cleaning cost (AED/day)']})
    st.download_button('Download all scenarios as CSV',frame.to_csv(index=False),
                       file_name='dynamiq_all_scenarios.csv',mime='text/csv')

with details:
    st.markdown('#### Equations used')
    st.latex(r'\frac{dD}{dt}=a-rD,\qquad D(0)=0')
    st.latex(r'D(t)=\frac{a}{r}(1-e^{-rt}),\quad r>0;\qquad D(t)=at,\quad r=0')
    st.latex(r'C(T)=\frac{K+pE_0\int_0^T[1-e^{-\alpha D(t)}]dt}{T}')
    st.latex(r'C_{\infty}=pE_0[1-e^{-\alpha a/r}],\quad r>0')
    st.write('The app evaluates the analytical first-order condition with numerical quadrature and Brent’s method. '
             'It checks whether a finite optimum exists before searching, checks the curvature at the continuous root, '
             'and compares nearby allowed whole-day intervals. No repeated symbolic integration is needed.')
    if result.second_derivative is not None:
        st.write(f'Second derivative at the continuous stationary point: {result.second_derivative:.6g} AED/day³.')
    st.markdown('#### What the recommendation means')
    st.write('This is a long-run average daily cost model. The maximum search interval is not a planning horizon, '
             'and the app does not minimize a finite calendar year’s total cost. All cleanings are complete. '
             'Current dust is used only for a threshold-based remaining-time estimate.')
    st.write('Scenario removal coefficients are assumptions rather than site-calibrated measurements. '
             'The preset deposition rates exclude particles above PM₁₀ and keep settling velocity and tilt fixed. '
             'Humidity and wind change removal only in these presets. Electricity value and cleaning cost are editable assumptions.')
    st.markdown('#### Rainfall and installation size')
    st.write('There is no automatic weather connection. If you adopt the report’s effective-rainfall rule and a qualifying '
             'rain event fully cleans the panels, enter current dust as zero and rerun for the prevailing conditions. '
             'No rain-cleaning cost is added. The 3 mm threshold is a transferred assumption, not a universal guarantee.')
    st.write('Default E₀ and K refer to a 10 MWp installation. For another installation, enter its own total clean daily yield '
             'and total cleaning cost. Panel tilt and cleaning effectiveness are not exposed as active inputs: '
             'tilt is already reflected in a, and partial cleaning requires a different cycle model.')
    st.markdown('#### Last submitted inputs')
    st.json(asdict(params))

st.caption('Dynamiq · Scenario-based mathematical model · Validate assumptions with site measurements before operational use.')
