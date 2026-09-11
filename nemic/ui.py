"""Shared trading-workspace components adapted from dashboard-ui-template."""
from dash import html,dcc
import numpy as np
import plotly.graph_objects as go

CYAN='#49d9d0';ORANGE='#ffb76b';PURPLE='#b29cff';TEXT='#e7edf5';MUTED='#8898ae'
COLORS=[CYAN,ORANGE,PURPLE,'#6ca9ff','#e17799','#a4c786']
GRAPH_CONFIG={'displayModeBar':'hover','displaylogo':False,'responsive':True,'scrollZoom':False}

def theme(fig,height=350):
    fig.update_layout(template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
      height=height,font=dict(family='Inter, Segoe UI, sans-serif',color=MUTED,size=12),
      margin=dict(l=55,r=25,t=20,b=40),colorway=COLORS,hovermode='x unified',
      legend=dict(orientation='h',y=1.07,x=0,font=dict(size=12)),
      hoverlabel=dict(bgcolor='#1b2535',font=dict(color=TEXT,size=12)))
    fig.update_xaxes(gridcolor='#1a2331',zerolinecolor='#344155',showgrid=False)
    fig.update_yaxes(gridcolor='#1a2331',zerolinecolor='#344155',gridwidth=1)
    return fig

def panel(title,content,subtitle=None,extra=None):
    return html.Section([html.Div([html.Div([html.H3(title),html.P(subtitle) if subtitle else None]),extra],className='panel-heading'),content],className='panel')

def graph(fig):return dcc.Graph(figure=fig,config=GRAPH_CONFIG,className='chart')

def stat(label,value,detail,tone=''):
    return html.Div([html.Span(label,className='stat-label'),html.Div(value,className='stat-number '+tone),html.Span(detail,className='stat-detail')],className='stat-card')

def fmt(x,unit='',digits=0):
    return '—' if x is None or not np.isfinite(float(x)) else f'{x:,.{digits}f}'+unit

def table(columns,rows):
    return html.Div(html.Table([html.Thead(html.Tr([html.Th(c) for c in columns])),html.Tbody([html.Tr([html.Td(v) for v in row]) for row in rows])],className='data-table'),className='table-scroll')

def notice(text):return html.Div(text,className='notice')
