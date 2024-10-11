# -*- coding: utf-8 -*-
"""
Created on Fri Oct 11 09:16:41 2024

@author: gabri
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import pyarrow.parquet as pq
import s3fs
import os

# Dash App Layout
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title="Americas Energy by Sea"
server = app.server

# Load your data
AWS_KEY= os.environ.get('AWS_KEY', None)
AWS_SECRET  = os.environ.get('AWS_SECRET', None)

s3 = s3fs.S3FileSystem(key=AWS_KEY,secret=AWS_SECRET)
# # ###Dataframes

ene=pq.ParquetDataset(os.environ.get('BASE_PATH', None), filesystem=s3).read_pandas().to_pandas()

ene = ene.assign(total_ene=ene.sum_me_ene + ene.sum_ab_ene + ene.sum_ae_ene)

ene=ene[ene.origin_departure_time<"2024-09-01"]

# Add year and month columns for further grouping/analysis
ene = ene.assign(year=ene.origin_departure_time.dt.year,
                 month=ene.origin_departure_time.dt.month)

ene = ene.assign(month_year=ene.apply(lambda x: "{}-{}".format(x["month"], x["year"]), axis=1))

# Your custom Mapbox token
MAPBOX_ACCESS_TOKEN=os.environ.get('MAPBOX_KEY', None)

## Create the Mapbox figure using plotly.graph_objects
# Create the Mapbox figure using plotly.graph_objects
def create_map(data, filter_value, selected_lat=None, selected_lon=None, map_zoom=1):
    if filter_value == 'inbound':
        country_energy = data.groupby(['destination_country', "dest_lon", "dest_lat", "destination_country_name"])['total_ene'].sum().reset_index()
        lat_col = 'dest_lat'
        lon_col = 'dest_lon'
        name_col = 'destination_country_name'
    elif filter_value == 'outbound':
        country_energy = data.groupby(['origin_country', 'origin_lat', 'origin_lon', 'origin_country_name'])['total_ene'].sum().reset_index()
        lat_col = 'origin_lat'
        lon_col = 'origin_lon'
        name_col = 'origin_country_name'
    else:
        inbound = data.groupby(['destination_country', "dest_lon", "dest_lat", 'destination_country_name'])['total_ene'].sum().reset_index()
        outbound = data.groupby(['origin_country', 'origin_lat', 'origin_lon', 'origin_country_name'])['total_ene'].sum().reset_index()
        country_energy = pd.merge(inbound, outbound, left_on='destination_country', right_on='origin_country', how='outer', suffixes=('_inbound', '_outbound'))
        country_energy['lat'] = country_energy['dest_lat'].fillna(country_energy['origin_lat'])
        country_energy['lon'] = country_energy['dest_lon'].fillna(country_energy['origin_lon'])
        country_energy['country_name'] = country_energy['destination_country_name'].fillna(country_energy['origin_country_name'])
        country_energy['total_ene'] = country_energy['total_ene_inbound'].fillna(0) + country_energy['total_ene_outbound'].fillna(0)
        lat_col = 'lat'
        lon_col = 'lon'
        name_col = 'country_name'

    max_energy = country_energy['total_ene'].max()
    marker_size_scale = 50

    country_energy['formatted_total_energy'] = country_energy['total_ene'] / 1e6

    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        lat=country_energy[lat_col],
        lon=country_energy[lon_col],
        mode='markers',
        marker=go.scattermapbox.Marker(
            size=country_energy['total_ene'] / max_energy * marker_size_scale,
            color=country_energy['total_ene'],
            colorscale='Viridis',
            showscale=True
        ),
        hovertext = country_energy.apply(
            lambda row: f"{row[name_col]}<br>Total Energy: {row['formatted_total_energy']:,.2f} x 10^6 kWh", axis=1
        ),
        hoverinfo='text'

    ))

    fig.update_layout(
        mapbox=dict(
            accesstoken=MAPBOX_ACCESS_TOKEN,
            style="mapbox://styles/gabrielfuenmar/cm1kg7cy800c801qrfb8u4kvp",
            zoom=map_zoom,
            center={"lat": selected_lat or 0, "lon": selected_lon or 0}
        ),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        title=f"Americas Energy Demand Map ({'Inbound' if filter_value == 'inbound' else 'Outbound'})"
    )
    return fig

# Create line graph function
def create_line_graph(data):
    monthly_data = data.groupby(['year', 'month'])['total_ene'].sum().reset_index()
    monthly_data['month_year'] = monthly_data['year'].astype(str) + '-' + monthly_data['month'].astype(str).str.zfill(2)
    monthly_data = monthly_data.sort_values(['year', 'month'])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly_data['month_year'], y=monthly_data['total_ene'], mode='lines+markers', name='Energy Demand'))
    fig.update_layout(title="Energy Demand Over Time", xaxis_title='Month-Year', yaxis_title='Total Energy', xaxis=dict(type='category'))
    return fig

# Bar chart functions for inbound, outbound, origin port, and destination port
def create_inbound_bar(data, selected_country=None):
    if selected_country:
        # Exclude the selected country from the inbound data
        data = data[data['destination_country_name'] != selected_country]

    top_inbound = data.groupby(['destination_country', 'destination_country_name'])['total_ene'].sum().reset_index()
    top_inbound = top_inbound.groupby(['destination_country_name'])['total_ene'].sum().nlargest(10).reset_index()
    top_inbound = top_inbound.sort_values('total_ene', ascending=True)

    fig = px.bar(top_inbound, x='total_ene', y='destination_country_name', orientation='h', title="Top 10 Destination Countries")
    fig.update_layout(xaxis_title='Total Energy', yaxis_title='Country')
    return fig

def create_outbound_bar(data, selected_country=None):
    if selected_country:
        # Exclude the selected country from the outbound data
        data = data[data['origin_country_name'] != selected_country]

    top_outbound = data.groupby(['origin_country', 'origin_country_name'])['total_ene'].sum().reset_index()
    top_outbound = top_outbound.groupby(['origin_country_name'])['total_ene'].sum().nlargest(10).reset_index()
    top_outbound = top_outbound.sort_values('total_ene', ascending=True)

    fig = px.bar(top_outbound, x='total_ene', y='origin_country_name', orientation='h', title="Top 10 Origin Countries")
    fig.update_layout(xaxis_title='Total Energy', yaxis_title='Country')
    return fig

def create_origin_port_bar(data, selected_country=None):
    data['origin_port_country'] = data['origin_port'] + ' (' + data['origin_country_name'] + ')'
    
    if selected_country:
        # Exclude the ports related to the selected country
        data = data[data['origin_country_name'] != selected_country]

    top_origin_ports = data.groupby(['origin_port_country'])['total_ene'].sum().nlargest(10).reset_index()
    top_origin_ports = top_origin_ports.sort_values('total_ene', ascending=True)

    fig = px.bar(top_origin_ports, x='total_ene', y='origin_port_country', orientation='h', title="Top 10 Origin Ports")
    fig.update_layout(xaxis_title='Total Energy', yaxis_title='Port (Country)')
    
    return fig

def create_destination_port_bar(data, selected_country=None):
    data['destination_port_country'] = data['destination_port'] + ' (' + data['destination_country_name'] + ')'
    
    if selected_country:
        # Exclude the ports related to the selected country
        data = data[data['destination_country_name'] != selected_country]

    top_destination_ports = data.groupby(['destination_port_country'])['total_ene'].sum().nlargest(10).reset_index()
    top_destination_ports = top_destination_ports.sort_values('total_ene', ascending=True)

    fig = px.bar(top_destination_ports, x='total_ene', y='destination_port_country', orientation='h', title="Top 10 Destination Ports")
    fig.update_layout(xaxis_title='Total Energy', yaxis_title='Port (Country)')
    return fig

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H4("Filters"),
            html.Label("Select Date Range"),
            dcc.DatePickerRange(
                id='date-picker',
                start_date=ene['origin_departure_time'].min(),
                end_date=ene['destination_arrival_time'].max(),
                display_format='YYYY-MM-DD',
                className='form-control'
            ),
            html.Br(),
            html.Label("Select Inbound/Outbound"),
            dcc.Dropdown(
                id='inbound-outbound',
                options=[
                    {'label': 'Inbound to Country', 'value': 'inbound'},
                    {'label': 'Outbound from Country', 'value': 'outbound'},
                    {'label': 'Both (Inbound & Outbound)', 'value': 'both'}
                ],
                value='both'
            ),
            html.Br(),
            html.Button("Reset to Default", id="reset-button", href="https://energydemand-f7940dd21a52.herokuapp.com/",color="primary", className="m-2"),
            html.Br(),
            # Buttons with URLs
            dbc.Button("Energy per Year All", id="home-button", href="https://logistikk.io/energyproject/plot_energy_per_year.html", color="secondary", className="m-2"),
            html.Br(),
            dbc.Button("Network Degree Centrality (Country level)", id="info-button_val1", href="https://logistikk.io/energyproject/network_country_degree_centrality.html", color="secondary", className="m-2"),
            dbc.Button("Network EigenVector Centrality (Country level)", id="info-button_val2", href="https://logistikk.io/energyproject/network_country_eigenvector_centrality.html", color="secondary", className="m-2"),
            html.Br(),
            dbc.Button("Network Degree Centrality (Port level)", id="info-button_val3", href="https://logistikk.io/energyproject/network_port_degree_centrality.html", color="secondary", className="m-2"),
            dbc.Button("Network EigenVector Centrality (Port level)", id="info-button_val4", href="https://logistikk.io/energyproject/network_port_eigenvector_centrality.html", color="secondary", className="m-2"),
        ], width=4),
        dbc.Col([
            html.H2("Americas Energy Demand Map"),
            dcc.Graph(id='energy-map')  
        ], width=8),
    ]),
    dbc.Row(dbc.Col( html.H4(id="test"))),
    dbc.Row([
        dbc.Col([dcc.Graph(id='line-graph')], width=4),
        dbc.Col([dcc.Graph(id='inbound-bar')], width=4),
        dbc.Col([dcc.Graph(id='outbound-bar')], width=4),
    ]),
    dbc.Row([
        dbc.Col([dcc.Graph(id='origin-port-bar')], width=6),
        dbc.Col([dcc.Graph(id='destination-port-bar')], width=6),
    ])
])

@app.callback(
    [Output('energy-map', 'figure'),
     Output('line-graph', 'figure'),
     Output('inbound-bar', 'figure'),
     Output('outbound-bar', 'figure'),
     Output('origin-port-bar', 'figure'),
     Output('destination-port-bar', 'figure'),
     Output("test","children")],
   [Input('inbound-outbound', 'value'),
     Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date'),
     Input('energy-map', 'clickData'),
     Input('reset-button', 'n_clicks')],
    [State('energy-map', 'figure')]  # To store previous state of the map if needed
)
def update_graphs(filter_value, start_date, end_date, clickData, reset_clicks, current_map):
    # If reset button is clicked, reset everything to default
    if reset_clicks:
        # Reset all variables to default values
        selected_country = None
        selected_lat = None
        selected_lon = None
        map_zoom = 1  # Default zoom level

        # Default state: no country is selected, all data is shown
        filtered_data = ene[
            (ene['origin_departure_time'] >= start_date) &
            (ene['destination_arrival_time'] <= end_date)
        ]

        return (create_map(filtered_data, filter_value, selected_lat, selected_lon, map_zoom),
                create_line_graph(filtered_data),
                create_inbound_bar(filtered_data),
                create_outbound_bar(filtered_data),
                create_origin_port_bar(filtered_data),
                create_destination_port_bar(filtered_data),
                selected_country)

    # If no reset, continue with the previous behavior of map click selection
    filtered_data = ene[
        (ene['origin_departure_time'] >= start_date) &
        (ene['destination_arrival_time'] <= end_date)
    ]

    selected_country = None
    selected_lat = None
    selected_lon = None
    map_zoom = 1  # Default zoom level

    if clickData is not None:
        # Extract the country name from clickData
        selected_country = clickData['points'][0]['hovertext'].split("<br>")[0]
        selected_lat = clickData['points'][0]['lat']
        selected_lon = clickData['points'][0]['lon']
        map_zoom = 4  # Zoom in when a country is clicked

        # Filter data for the selected country
        if filter_value == 'inbound':
            filtered_data = filtered_data[filtered_data['destination_country_name'] == selected_country]
        elif filter_value == 'outbound':
            filtered_data = filtered_data[filtered_data['origin_country_name'] == selected_country]
        else:
            filtered_data = filtered_data[
                (filtered_data['origin_country_name'] == selected_country) |
                (filtered_data['destination_country_name'] == selected_country)
            ]

    # Update all graphs and the map
    return (create_map(filtered_data, filter_value, selected_lat, selected_lon, map_zoom),
            create_line_graph(filtered_data),
            create_inbound_bar(filtered_data, selected_country),
            create_outbound_bar(filtered_data, selected_country),
            create_origin_port_bar(filtered_data, selected_country),
            create_destination_port_bar(filtered_data, selected_country),
            selected_country)

if __name__ == '__main__':
    app.run_server(debug=True)
