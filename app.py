# -*- coding: utf-8 -*-
"""
Created on Mon May 15 14:19:14 2023

@author: gabri
"""

###Dash for plots fo hexagons
import dash
from dash import dcc
from dash import html
import dash_auth
from dash.dependencies import Input, Output
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import h3
import plotly.express as px
from geojson.feature import *
import json
import geopandas as gpd
from shapely.geometry import Polygon
import os

coll=pd.read_csv("collision_reduced.csv")

sat_map="mapbox://styles/gabrielfuenmar/cla32e7tw00f414nxrhtsurkl"
plain_map="mapbox://styles/gabrielfuenmar/ckkmdsqrm4ngq17o21tnno1ce"

MAPBOX_TOKEN=os.environ.get('MAPBOX_TOKEN', None)

app = dash.Dash(__name__)
app.title="Collisions"
server = app.server

app.layout = html.Div(style={'display': 'flex', 'flex-wrap': 'wrap', 'justify-content': 'center', 'align-items': 'center', 'flex-direction': 'column'}, children=[
    
    html.Div(style={'display': 'flex', 'flex-wrap': 'wrap', 'justify-content': 'center', 'width': '100%'}, children=[
        html.H3("Collisions 1983-2021", style={'text-align': 'center', 'width': '100%'}),
        html.Div([
            dcc.Graph(id='graph2',),
        ], className='box'),

        html.Div([
            dcc.Graph(id='graph1', ),
        ], className='box'),
    ]),

    html.Div(style={'display': 'flex', 'flex-wrap': 'wrap', 'justify-content': 'center', 'width': '100%'}, children=[
        html.H3("Collisions 2016-2021", style={'text-align': 'center', 'width': '100%'}),
        html.Div([
            dcc.Graph(id='graph4'),
        ], className='box'),

        html.Div([
            dcc.Graph(id='graph3'),
        ], className='box'),
    ]),

    html.Div([
        html.H3("Resolution Slider", style={'text-align': 'center'}),
        dcc.Slider(
            id='my-slider',
            min=4,
            max=8,
            step=1,
            value=4,
            marks={4:{'label': '1'},5:{'label': '2'},6:{'label': '3'},
            7:{'label': '4'},8:{'label': '5'}},
        )
    ], style={'width': '50%', 'padding': '20px 0'}),

    html.Div([
        html.H3("Opacity Slider", style={'text-align': 'center'}),
        dcc.Slider(
            id='opacity-slider',
            min=0,
            max=1,
            step=0.1,
            value=1,
            marks={i/10: str(i/10) for i in range(0, 11)},
        )
    ], style={'width': '50%', 'padding': '20px 0'}),

    html.Div(id='selected-data', style={'padding': '20px', 'color': 'blue', 'font-size': '20px'}),
])

  

def hexagons_dataframe_to_geojson(df_hex, res_col,file_output = None):
    """
    Produce the GeoJSON for a dataframe that has a geometry column in geojson 
    format already, along with the columns hex_id and value
    
    Ex counts_by_hexagon(data)
    """    
   
    list_features = []
    
    for i,row in df_hex.iterrows():
        feature = Feature(geometry = row["geometry"] , id=row[res_col], properties = {"value" : row["value"]})
        list_features.append(feature)
        
    feat_collection = FeatureCollection(list_features)
    
    geojson_result = json.dumps(feat_collection)
    
    #optionally write to file
    if file_output is not None:
        with open(file_output,"w") as f:
            json.dump(feat_collection,f)
    
    return geojson_result 


# Functions to generate choropleth map
def generate_map(df_hex, opacity, mapbox_style,  res_col):
    
    layout_map = dict(
    autosize=True,
    paper_bgcolor='#175A7F',
    plot_bgcolor='#30333D',
    margin=dict(l=10, r=10, b=10, t=10),
    hovermode="closest",
    font=dict(family="HelveticaNeue",size=17,color="#F8F8F8"),
    legend=dict(font=dict(size=10), orientation="h"),
    mapbox=dict(
        accesstoken=MAPBOX_TOKEN,
        style=mapbox_style,
        center=dict(lon=5, lat=60),
        zoom=5,
    ),
    showlegend=False,
    )
    df_hex.rename(columns={"month":"value"},inplace=True)  
    geojson_data = json.loads(hexagons_dataframe_to_geojson(df_hex,res_col))
    
    hovertemplate = "<b>Longitude:</b> %{customdata[0]:,.2f}<br><b>Latitude:</b> %{customdata[1]:,.2f}<br><b>Collisions:</b> %{z:,.2f}<extra></extra>\
                     <br><b>Hex:</b> %{customdata[2]}"

    ##plot on map
    initial_map=go.Choroplethmapbox(geojson=geojson_data,
                                    locations=df_hex[res_col].tolist(),
                                    z=df_hex["value"].round(2).tolist(),
                                    customdata=np.stack((df_hex["lon"], df_hex["lat"], df_hex[res_col]), axis=-1), # add customdata here
                                    colorscale="Reds",
                                    marker_line_width=1,
                                    marker_opacity=opacity,
                                    colorbar = dict(thickness=20, ticklen=3,title="Collisions"),
                                    hovertemplate = hovertemplate)
    
    initial_map=go.Figure(data=initial_map,layout=layout_map)
    
    return initial_map
    
### H3 hexagons count

def mapbox_plan(name_res,opacity):
    
    size=int(name_res.split("_")[-1])
    coll[name_res]=coll.apply(lambda x: h3.geo_to_h3(x.position_latitude, x.position_longitude, size),axis=1)
    
    hex_count=coll.groupby(name_res).count().reset_index()
    hex_count=hex_count[hex_count[name_res]!="0"]
    hex_count=gpd.GeoDataFrame(hex_count,geometry=hex_count[name_res].apply(lambda x: Polygon(h3.h3_to_geo_boundary(x, geo_json=True))))
    
    hex_last_5=coll[coll.year>=2016].groupby(name_res).count().reset_index()
    hex_last_5=hex_last_5[hex_last_5[name_res]!="0"]
    hex_last_5=gpd.GeoDataFrame(hex_last_5,geometry=hex_last_5[name_res].apply(lambda x: Polygon(h3.h3_to_geo_boundary(x, geo_json=True))))
    
    hex_count["lat"] = hex_count[name_res].apply(lambda x: h3.h3_to_geo(x)[0])
    hex_count["lon"] = hex_count[name_res].apply(lambda x: h3.h3_to_geo(x)[1])
    
    hex_last_5["lat"] = hex_last_5[name_res].apply(lambda x: h3.h3_to_geo(x)[0])
    hex_last_5["lon"] = hex_last_5[name_res].apply(lambda x: h3.h3_to_geo(x)[1])

    # 5) Choroplethmapbox with h3 hexagons plotted from hex_count for both sat_map and plain_map
    graph1=generate_map(hex_count, opacity, sat_map, name_res)
    graph2=generate_map(hex_count, opacity, plain_map, name_res)
    
    # 6) Choroplethmapbox with h3 hexagons plotted from hex_last_5 for both sat_map and plain_map
    graph3=generate_map(hex_last_5, opacity, sat_map, name_res)
    graph4=generate_map(hex_last_5, opacity, plain_map, name_res)
    
    return graph1,graph2,graph3,graph4

@app.callback(
    [Output('graph1', 'figure'),
      Output('graph2', 'figure'),
      Output('graph3', 'figure'),
      Output('graph4', 'figure')],
    [Input('my-slider', 'value'),
     Input('opacity-slider', 'value')])

def update_output(res_value, opacity_value):


    graph1, graph2, graph3, graph4 = mapbox_plan("res_{}".format(res_value),opacity_value)
    
    return graph1, graph2, graph3, graph4

@app.callback(
    Output('selected-data', 'children'),
    [Input('graph1', 'selectedData'),
     Input('graph2', 'selectedData'),
     Input('graph3', 'selectedData'),
     Input('graph4', 'selectedData')])
def display_selected_data(selected_data1, selected_data2, selected_data3, selected_data4):
    # Combine the selected data from all graphs into a list
    all_selected_data = [selected_data1, selected_data2, selected_data3, selected_data4]
    
    # Initialize an empty list to store the hexagon names
    hexagon_names = []
    
    # Iterate over all selected data
    for selected_data in all_selected_data:
        if selected_data is not None:
            # Iterate over all selected points
            for point in selected_data['points']:
                # Here we add the id (hexagon name) to the list
                hexagon_names.append("'"+point['location']+"'")
    
    # Combine the hexagon names into a single string
    combined_data = ', '.join(hexagon_names)
    
    return 'Selected hexagons: {}'.format(combined_data)

if __name__ == '__main__':
    app.run_server(debug=True)
