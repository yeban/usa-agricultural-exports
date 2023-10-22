import pandas as pd
import plotly.express as px
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
from dash import Dash, dcc, html, Input, Output, State, callback, no_update, ALL

app = Dash(__name__,
           suppress_callback_exceptions=True,
           external_stylesheets=[dbc.themes.BOOTSTRAP])

df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/Dash-Course/US-Exports/2011_us_ag_exports.csv')
# df = pd.read_csv('./2011_us_ag_exports.csv')

# Remove the useless category column - it is the same for all the rows.
df = df.drop(['category'], axis=1)

# Rename total veggies and total fruits columns so they will line up
# when sorted.
df = df.rename(columns={
    'total veggies': 'veggies total',
    'total fruits': 'fruits total',
})

# Take note of id and variable columns. Sort the category columns
# alphabetically, but put 'total exports' first.
id_cols = ['code', 'state']
ct_cols = ['total exports']
ct_cols = ct_cols + sorted(set(df.columns) - set(id_cols + ct_cols))

# Create a colour map for categories that we will use to create per-state
# exports breakdown pie chart. This is needed to make sure categories
# have the same colour in different pie charts.
ct_col_scl = px.colors.sample_colorscale(
    px.colors.qualitative.Set3, len(ct_cols))
ct_col_map = dict(zip(ct_cols, ct_col_scl))

app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1('USA Agricultural Exports'))),
    dbc.Row([
        dbc.Col('Category', width=1),
        dbc.Col(dmc.ChipGroup(
            [dmc.Chip(ct, value=ct) for ct in ct_cols],
            id='category-selector',
            value='total exports',
        ))
    ]),
    dbc.Row([
        dbc.Col(id='choropleth-container', children=[]),
        dbc.Col(id='breakdown-container', children=[])
    ]),
    dcc.Store(id='store', data={
        'selected_state_codes': []
    })
], fluid=True)

@callback(
    Output('choropleth-container', 'children'),
    Input('category-selector', 'value'),
    Input('store', 'data'),
)
def create_or_update_choropleth(selected_category, stored_data):
    marker_line_widths = [1] * df.shape[0]
    marker_line_colors = ['#444'] * df.shape[0]

    selected_state_codes = stored_data['selected_state_codes']
    for idx in df.index[df['code'].isin(selected_state_codes)]:
        marker_line_widths[idx] = 3
        marker_line_colors[idx] = 'orange'

    fig = px.choropleth(df, locationmode='USA-states', scope='usa', locations='code',
                        color=selected_category, color_continuous_scale='blues',
                        title=f'Exports across country: {selected_category}')
    fig.update_traces(marker_line_width=marker_line_widths,
                      marker_line_color=marker_line_colors,
                      showlegend=False)
    fig.update_layout(coloraxis_showscale=False)

    return dcc.Graph(id='choropleth', figure=fig, config={
        'modeBarButtonsToRemove': ['pan2d', 'select2d', 'lasso2d'],
        'displaylogo': False,
    })

@callback(
    Output('store', 'data'),
    Input('choropleth', 'clickData'),
    State('store', 'data'),
    prevent_initial_call=True
)
def update_selected_states(click_data, stored_data):
    if not click_data:
        return no_update

    selected_state_codes = stored_data['selected_state_codes']
    clicked_state_code = click_data['points'][0]['location']
    if clicked_state_code in selected_state_codes:
        selected_state_codes.remove(clicked_state_code)
    else:
        selected_state_codes.append(clicked_state_code)

    return {
        'selected_state_codes': selected_state_codes
    }

@callback(
    Output('breakdown-container', 'children'),
    Input('store', 'data'),
    Input('category-selector', 'value'),
    Input({'type': 'exports-breakdown', 'code': ALL}, 'hoverData'),
    prevent_initial_call=True
)
def generate_or_update_exports_breakdown(stored_data, selected_category, hover_data):
    if len(stored_data['selected_state_codes']) == 0:
        return []

    # We want to highlight the selected exports category in the pie chart.
    # We also want to highlight the hovered sector and the corresponding
    # exports category in other pie charts (for easy comparison).
    categories_to_highlight = [selected_category] if selected_category else []
    hover_data = [data for data in hover_data if data]
    if len(hover_data) != 0:
        hovered_category = hover_data[0]['points'][0]['customdata'][0]
        categories_to_highlight.append(hovered_category)

    return dbc.Row([
        dbc.Col(
            dcc.Graph(id={'type': 'exports-breakdown', 'code': state_code},
                      clear_on_unhover=True, config={'displaylogo': False},
                      figure=generate_exports_breakdown(state_code,
                                                        categories_to_highlight)),
            width=6
        ) for state_code in stored_data['selected_state_codes']
    ])

# Returns pie chart showing exports breakdown for the give state code.
def generate_exports_breakdown(state_code, categories_to_highlight):
    dff = df[df['code'] == state_code]

    # Remove aggregated columns. If we kept 'total exports' columns, wouldn't
    # that take 100% of the pie chart?
    dff = dff.drop(['total exports', 'veggies total', 'fruits total'], axis=1)

    # I think px.pie expects a long-form df.
    dff = dff.melt(id_vars=id_cols, var_name='category', value_name='exports')

    # Couldn't find way to tell plotly's pie trace to automatically hide sectors
    # smaller than a certain percentage. Instead of calculating the percentage
    # and filtering accordingly, let's at least remove categories with 0 export.
    dff = dff[dff['exports'] != 0]

    num_categories = dff.shape[0] # the pie chart will have these many sectors

    marker_line_widths = [0] * num_categories
    for idx in dff.index[dff['category'].isin(categories_to_highlight)]:
        marker_line_widths[idx] = 2

    fig = px.pie(dff, 'category', 'exports',
                 color='category', color_discrete_map=ct_col_map,
                 hole=0.5, title=f"Exports breakdown for: {state_code}")
    fig.update_traces(
        textinfo='label+percent',
        marker_line_width=marker_line_widths,
    )
    fig.update_layout(showlegend=False)
    return fig

if __name__ == '__main__':
    app.run(debug=True)
